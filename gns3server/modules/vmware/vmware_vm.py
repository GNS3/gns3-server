# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
VMware VM instance.
"""

import sys
import os
import socket
import subprocess
import configparser
import shutil
import asyncio
import tempfile

from gns3server.utils.asyncio import wait_for_process_termination
from gns3server.utils.asyncio import monitor_process
from gns3server.utils.telnet_server import TelnetServer
from collections import OrderedDict
from .vmware_error import VMwareError
from ..nios.nio_udp import NIOUDP
from ..adapters.ethernet_adapter import EthernetAdapter
from ..base_vm import BaseVM

if sys.platform.startswith('win'):
    import msvcrt
    import win32file

import logging
log = logging.getLogger(__name__)


class VMwareVM(BaseVM):

    """
    VMware VM implementation.
    """

    def __init__(self, name, vm_id, project, manager, vmx_path, linked_clone, console=None):

        super().__init__(name, vm_id, project, manager, console=console)

        self._linked_clone = linked_clone
        self._vmx_pairs = OrderedDict()
        self._ubridge_process = None
        self._ubridge_stdout_file = ""
        self._telnet_server_thread = None
        self._serial_pipe = None
        self._vmnets = []
        self._maximum_adapters = 10
        self._started = False
        self._closed = False

        # VMware VM settings
        self._headless = False
        self._vmx_path = vmx_path
        self._enable_remote_console = False
        self._adapters = 0
        self._ethernet_adapters = {}
        self._adapter_type = "e1000"
        self._use_any_adapter = False

        if not os.path.exists(vmx_path):
            raise VMwareError('VMware VM "{name}" [{id}]: could not find VMX file "{}"'.format(name, vmx_path))

    def __json__(self):

        return {"name": self.name,
                "vm_id": self.id,
                "console": self.console,
                "project_id": self.project.id,
                "vmx_path": self.vmx_path,
                "headless": self.headless,
                "enable_remote_console": self.enable_remote_console,
                "adapters": self._adapters,
                "adapter_type": self.adapter_type,
                "use_any_adapter": self.use_any_adapter}

    @property
    def vmnets(self):

        return self._vmnets

    @asyncio.coroutine
    def _control_vm(self, subcommand, *additional_args):

        args = [self._vmx_path]
        args.extend(additional_args)
        result = yield from self.manager.execute(subcommand, args)
        log.debug("Control VM '{}' result: {}".format(subcommand, result))
        return result

    @asyncio.coroutine
    def create(self):

        if self._linked_clone and not os.path.exists(os.path.join(self.working_dir, os.path.basename(self._vmx_path))):
            # create the base snapshot for linked clones
            base_snapshot_name = "GNS3 Linked Base for clones"
            vmsd_path = os.path.splitext(self._vmx_path)[0] + ".vmsd"
            if not os.path.exists(vmsd_path):
                raise VMwareError("{} doesn't not exist".format(vmsd_path))
            try:
                vmsd_pairs = self.manager.parse_vmware_file(vmsd_path)
            except OSError as e:
                raise VMwareError('Could not read VMware VMSD file "{}": {}'.format(vmsd_path, e))
            gns3_snapshot_exists = False
            for value in vmsd_pairs.values():
                if value == base_snapshot_name:
                    gns3_snapshot_exists = True
                    break
            if not gns3_snapshot_exists:
                log.info("Creating snapshot '{}'".format(base_snapshot_name))
                yield from self._control_vm("snapshot", base_snapshot_name)

            # create the linked clone based on the base snapshot
            new_vmx_path = os.path.join(self.working_dir, self.name + ".vmx")
            yield from self._control_vm("clone",
                                        new_vmx_path,
                                        "linked",
                                        "-snapshot={}".format(base_snapshot_name),
                                        "-cloneName={}".format(self.name))

            try:
                vmsd_pairs = self.manager.parse_vmware_file(vmsd_path)
            except OSError as e:
                raise VMwareError('Could not read VMware VMSD file "{}": {}'.format(vmsd_path, e))

            snapshot_name = None
            for name, value in vmsd_pairs.items():
                if value == base_snapshot_name:
                    snapshot_name = name.split(".", 1)[0]
                    break

            if snapshot_name is None:
                raise VMwareError("Could not find the linked base snapshot in {}".format(vmsd_path))

            num_clones_entry = "{}.numClones".format(snapshot_name)
            if num_clones_entry in vmsd_pairs:
                try:
                    nb_of_clones = int(vmsd_pairs[num_clones_entry])
                except ValueError:
                    raise VMwareError("Value of {} in {} is not a number".format(num_clones_entry, vmsd_path))
                vmsd_pairs[num_clones_entry] = str(nb_of_clones - 1)

                for clone_nb in range(0, nb_of_clones):
                    clone_entry = "{}.clone{}".format(snapshot_name, clone_nb)
                    if clone_entry in vmsd_pairs:
                        del vmsd_pairs[clone_entry]

                try:
                    self.manager.write_vmware_file(vmsd_path, vmsd_pairs)
                except OSError as e:
                    raise VMwareError('Could not write VMware VMSD file "{}": {}'.format(vmsd_path, e))

            # update the VMX file path
            self._vmx_path = new_vmx_path

    def _get_vmx_setting(self, name, value=None):

        if name in self._vmx_pairs:
            if value is not None:
                if self._vmx_pairs[name] == value:
                    return value
            else:
                return self._vmx_pairs[name]
        return None

    def _set_network_options(self):

        # first do some sanity checks
        for adapter_number in range(0, self._adapters):
            connected = "ethernet{}.startConnected".format(adapter_number)
            if self._get_vmx_setting(connected):
                del self._vmx_pairs[connected]

            # check if any vmnet interface managed by GNS3 is being used on existing VMware adapters
            if self._get_vmx_setting("ethernet{}.present".format(adapter_number), "TRUE"):
                connection_type = "ethernet{}.connectionType".format(adapter_number)
                if self._vmx_pairs[connection_type] in ("hostonly", "custom"):
                    vnet = "ethernet{}.vnet".format(adapter_number)
                    if vnet in self._vmx_pairs:
                        vmnet = os.path.basename(self._vmx_pairs[vnet])
                        if self.manager.is_managed_vmnet(vmnet):
                            raise VMwareError("Network adapter {} is already associated with VMnet interface {} which is managed by GNS3, please remove".format(adapter_number, vmnet))

            # check for adapter type
            if self._adapter_type != "default":
                adapter_type = "ethernet{}.virtualDev".format(adapter_number)
                if adapter_type in self._vmx_pairs and self._vmx_pairs[adapter_type] != self._adapter_type:
                    raise VMwareError("Network adapter {} is not of type {}, please fix or remove it".format(self._adapter_type))

            # check if connected to an adapter configured for nat or bridge
            if self._ethernet_adapters[adapter_number].get_nio(0) and not self._use_any_adapter:
                if self._get_vmx_setting("ethernet{}.present".format(adapter_number), "TRUE"):
                    # check for the connection type
                    connection_type = "ethernet{}.connectionType".format(adapter_number)
                    if connection_type in self._vmx_pairs:
                        if self._vmx_pairs[connection_type] in ("nat", "bridged", "hostonly"):
                            raise VMwareError("Attachment ({}) already configured on network adapter {}. "
                                              "Please remove it or allow GNS3 to use any adapter.".format(self._vmx_pairs[connection_type],
                                                                                                          adapter_number))

        # now configure VMware network adapters
        self.manager.refresh_vmnet_list()
        for adapter_number in range(0, self._adapters):
            ethernet_adapter = {"ethernet{}.present".format(adapter_number): "TRUE",
                                "ethernet{}.addressType".format(adapter_number): "generated",
                                "ethernet{}.generatedAddressOffset".format(adapter_number): "0"}
            self._vmx_pairs.update(ethernet_adapter)
            if self._adapter_type != "default":
                self._vmx_pairs["ethernet{}.virtualDev".format(adapter_number)] = self._adapter_type

            connection_type = "ethernet{}.connectionType".format(adapter_number)
            if not self._use_any_adapter and connection_type in self._vmx_pairs and self._vmx_pairs[connection_type] in ("nat", "bridged", "hostonly"):
                continue

            vnet = "ethernet{}.vnet".format(adapter_number)
            if vnet in self._vmx_pairs:
                vmnet = os.path.basename(self._vmx_pairs[vnet])
            else:
                try:
                    vmnet = self.manager.allocate_vmnet()
                finally:
                    self._vmnets.clear()
            self._vmnets.append(vmnet)
            self._vmx_pairs["ethernet{}.connectionType".format(adapter_number)] = "custom"
            self._vmx_pairs["ethernet{}.vnet".format(adapter_number)] = vmnet

        # disable remaining network adapters
        for adapter_number in range(self._adapters, self._maximum_adapters):
            if self._get_vmx_setting("ethernet{}.present".format(adapter_number), "TRUE"):
                log.debug("disabling remaining adapter {}".format(adapter_number))
                self._vmx_pairs["ethernet{}.startConnected".format(adapter_number)] = "FALSE"

        self._update_ubridge_config()

    def _update_ubridge_config(self):
        """
        Updates the ubrige.ini file.
        """

        ubridge_ini = os.path.join(self.working_dir, "ubridge.ini")
        config = configparser.ConfigParser()
        for adapter_number in range(0, self._adapters):
            nio = self._ethernet_adapters[adapter_number].get_nio(0)
            if nio:
                bridge_name = "bridge{}".format(adapter_number)

                vnet = "ethernet{}.vnet".format(adapter_number)
                if not vnet in self._vmx_pairs:
                    continue

                vmnet_interface = os.path.basename(self._vmx_pairs[vnet])
                if sys.platform.startswith("linux"):
                    config[bridge_name] = {"source_linux_raw": vmnet_interface}
                elif sys.platform.startswith("win"):
                    windows_interfaces = self.manager.get_vmnet_interfaces()
                    npf = None
                    for interface in windows_interfaces:
                        if "netcard" in interface and vmnet_interface in interface["netcard"]:
                            npf = interface["id"]
                        elif vmnet_interface in interface["name"]:
                            npf = interface["id"]
                    if npf:
                        config[bridge_name] = {"source_ethernet": npf}
                    else:
                        raise VMwareError("Could not find NPF id for VMnet interface {}".format(vmnet_interface))
                else:
                    config[bridge_name] = {"source_ethernet": vmnet_interface}

                if isinstance(nio, NIOUDP):
                    udp_tunnel_info = {"destination_udp": "{lport}:{rhost}:{rport}".format(lport=nio.lport,
                                                                                           rhost=nio.rhost,
                                                                                           rport=nio.rport)}
                    config[bridge_name].update(udp_tunnel_info)

                if nio.capturing:
                    capture_info = {"pcap_file": "{pcap_file}".format(pcap_file=nio.pcap_output_file)}
                    config[bridge_name].update(capture_info)

        try:
            with open(ubridge_ini, "w", encoding="utf-8") as config_file:
                config.write(config_file)
            log.info('VMware VM "{name}" [id={id}]: ubridge.ini updated'.format(name=self._name,
                                                                                id=self._id))
        except OSError as e:
            raise VMwareError("Could not create {}: {}".format(ubridge_ini, e))

    @property
    def ubridge_path(self):
        """
        Returns the uBridge executable path.

        :returns: path to uBridge
        """

        path = self._manager.config.get_section_config("Server").get("ubridge_path", "ubridge")
        if path == "ubridge":
            path = shutil.which("ubridge")
        return path

    @asyncio.coroutine
    def _start_ubridge(self):
        """
        Starts uBridge (handles connections to and from this VMware VM).
        """

        try:
            #self._update_ubridge_config()
            command = [self.ubridge_path]
            log.info("starting ubridge: {}".format(command))
            self._ubridge_stdout_file = os.path.join(self.working_dir, "ubridge.log")
            log.info("logging to {}".format(self._ubridge_stdout_file))
            with open(self._ubridge_stdout_file, "w", encoding="utf-8") as fd:
                self._ubridge_process = yield from asyncio.create_subprocess_exec(*command,
                                                                                  stdout=fd,
                                                                                  stderr=subprocess.STDOUT,
                                                                                  cwd=self.working_dir)

                monitor_process(self._ubridge_process, self._termination_callback)
            log.info("ubridge started PID={}".format(self._ubridge_process.pid))
        except (OSError, subprocess.SubprocessError) as e:
            ubridge_stdout = self.read_ubridge_stdout()
            log.error("Could not start ubridge: {}\n{}".format(e, ubridge_stdout))
            raise VMwareError("Could not start ubridge: {}\n{}".format(e, ubridge_stdout))

    def _termination_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        log.info("uBridge process has stopped, return code: %d", returncode)

    def is_ubridge_running(self):
        """
        Checks if the ubridge process is running

        :returns: True or False
        """

        if self._ubridge_process and self._ubridge_process.returncode is None:
            return True
        return False

    def read_ubridge_stdout(self):
        """
        Reads the standard output of the uBridge process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._ubridge_stdout_file:
            try:
                with open(self._ubridge_stdout_file, "rb") as file:
                    output = file.read().decode("utf-8", errors="replace")
            except OSError as e:
                log.warn("could not read {}: {}".format(self._ubridge_stdout_file, e))
        return output

    def _terminate_process_ubridge(self):
        """
        Terminate the ubridge process if running.
        """

        if self._ubridge_process:
            log.info('Stopping uBridge process for VMware VM "{}" PID={}'.format(self.name, self._ubridge_process.pid))
            try:
                self._ubridge_process.terminate()
            # Sometime the process can already be dead when we garbage collect
            except ProcessLookupError:
                pass

    @asyncio.coroutine
    def start(self):
        """
        Starts this VMware VM.
        """

        if os.path.exists(self._vmx_path + ".lck"):
            raise VMwareError("VM locked, it is either running or being edited in VMware")

        ubridge_path = self.ubridge_path
        if not ubridge_path or not os.path.isfile(ubridge_path):
            raise VMwareError("ubridge is necessary to start a VMware VM")

        try:
            self._vmx_pairs = self.manager.parse_vmware_file(self._vmx_path)
        except OSError as e:
            raise VMwareError('Could not read VMware VMX file "{}": {}'.format(self._vmx_path, e))

        self._set_network_options()
        self._set_serial_console()

        try:
            self.manager.write_vmx_file(self._vmx_path, self._vmx_pairs)
        except OSError as e:
            raise VMwareError('Could not write VMware VMX file "{}": {}'.format(self._vmx_path, e))

        yield from self._start_ubridge()
        if self._headless:
            yield from self._control_vm("start", "nogui")
        else:
            yield from self._control_vm("start")

        if self._enable_remote_console and self._console is not None:
            yield from asyncio.sleep(1)  # give some time to VMware to create the pipe file.
            self._start_remote_console()

        self._started = True
        log.info("VMware VM '{name}' [{id}] started".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def stop(self):
        """
        Stops this VMware VM.
        """

        self._stop_remote_console()
        if self.is_ubridge_running():
            self._terminate_process_ubridge()
            try:
                yield from wait_for_process_termination(self._ubridge_process, timeout=3)
            except asyncio.TimeoutError:
                if self._ubridge_process.returncode is None:
                    log.warn("uBridge process {} is still running... killing it".format(self._ubridge_process.pid))
                    self._ubridge_process.kill()
            self._ubridge_process = None

        try:
            yield from self._control_vm("stop")
        finally:
            self._started = False
            self._vmnets.clear()
            try:
                self._vmx_pairs = self.manager.parse_vmware_file(self._vmx_path)
            except OSError as e:
                raise VMwareError('Could not read VMware VMX file "{}": {}'.format(self._vmx_path, e))

            # remove the adapters managed by GNS3
            for adapter_number in range(0, self._adapters):
                if self._get_vmx_setting("ethernet{}.vnet".format(adapter_number)) or \
                   self._get_vmx_setting("ethernet{}.connectionType".format(adapter_number)) is None:
                    vnet = "ethernet{}.vnet".format(adapter_number)
                    if vnet in self._vmx_pairs:
                        vmnet = os.path.basename(self._vmx_pairs[vnet])
                        if not self.manager.is_managed_vmnet(vmnet):
                            continue
                    log.debug("removing adapter {}".format(adapter_number))
                    for key in self._vmx_pairs.keys():
                        if key.startswith("ethernet{}.".format(adapter_number)):
                            del self._vmx_pairs[key]

            # re-enable any remaining network adapters
            for adapter_number in range(self._adapters, self._maximum_adapters):
                if self._get_vmx_setting("ethernet{}.present".format(adapter_number), "TRUE"):
                    log.debug("enabling remaining adapter {}".format(adapter_number))
                    self._vmx_pairs["ethernet{}.startConnected".format(adapter_number)] = "TRUE"

            self.manager.write_vmx_file(self._vmx_path, self._vmx_pairs)

        log.info("VMware VM '{name}' [{id}] stopped".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def suspend(self):
        """
        Suspends this VMware VM.
        """

        if self.manager.host_type != "ws":
            raise VMwareError("Pausing a VM is only supported by VMware Workstation")
        yield from self._control_vm("pause")
        log.info("VMware VM '{name}' [{id}] paused".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def resume(self):
        """
        Resumes this VMware VM.
        """

        if self.manager.host_type != "ws":
            raise VMwareError("Unpausing a VM is only supported by VMware Workstation")
        yield from self._control_vm("unpause")
        log.info("VMware VM '{name}' [{id}] resumed".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def reload(self):
        """
        Reloads this VMware VM.
        """

        yield from self._control_vm("reset")
        log.info("VMware VM '{name}' [{id}] reloaded".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def close(self):
        """
        Closes this VirtualBox VM.
        """

        if self._closed:
            # VM is already closed
            return

        log.debug("VMware VM '{name}' [{id}] is closing".format(name=self.name, id=self.id))
        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
            self._console = None

        for adapter in self._ethernet_adapters.values():
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(nio.lport, self._project)

        try:
            yield from self.stop()
        except VMwareError:
            pass

        if self._linked_clone:
            # clean the VMware inventory path from this linked clone
            inventory_path = self.manager.get_vmware_inventory_path()
            if os.path.exists(inventory_path):
                try:
                    inventory_pairs = self.manager.parse_vmware_file(inventory_path)
                except OSError as e:
                    log.warning('Could not read VMware inventory file "{}": {}'.format(inventory_path, e))

                vmlist_entry = None
                for name, value in inventory_pairs.items():
                    if value == self._vmx_path:
                        vmlist_entry = name.split(".", 1)[0]
                        break

                if vmlist_entry is not None:
                    for name in inventory_pairs.keys():
                        if name.startswith(vmlist_entry):
                            del inventory_pairs[name]

            try:
                self.manager.write_vmware_file(inventory_path, inventory_pairs)
            except OSError as e:
                raise VMwareError('Could not write VMware inventory file "{}": {}'.format(inventory_path, e))

        log.info("VirtualBox VM '{name}' [{id}] closed".format(name=self.name, id=self.id))
        self._closed = True

    @property
    def headless(self):
        """
        Returns either the VM will start in headless mode

        :returns: boolean
        """

        return self._headless

    @headless.setter
    def headless(self, headless):
        """
        Sets either the VM will start in headless mode

        :param headless: boolean
        """

        if headless:
            log.info("VMware VM '{name}' [{id}] has enabled the headless mode".format(name=self.name, id=self.id))
        else:
            log.info("VMware VM '{name}' [{id}] has disabled the headless mode".format(name=self.name, id=self.id))
        self._headless = headless

    @property
    def vmx_path(self):
        """
        Returns the path to the vmx file.

        :returns: VMware vmx file
        """

        return self._vmx_path

    @vmx_path.setter
    def vmx_path(self, vmx_path):
        """
        Sets the path to the vmx file.

        :param vmx_path: VMware vmx file
        """

        log.info("VMware VM '{name}' [{id}] has set the vmx file path to '{vmx}'".format(name=self.name, id=self.id, vmx=vmx_path))
        self._vmx_path = vmx_path

    @property
    def enable_remote_console(self):
        """
        Returns either the remote console is enabled or not

        :returns: boolean
        """

        return self._enable_remote_console

    @enable_remote_console.setter
    def enable_remote_console(self, enable_remote_console):
        """
        Sets either the console is enabled or not

        :param enable_remote_console: boolean
        """

        if enable_remote_console:
            log.info("VMware VM '{name}' [{id}] has enabled the console".format(name=self.name, id=self.id))
            if self._started:
                self._start_remote_console()
        else:
            log.info("VMware VM '{name}' [{id}] has disabled the console".format(name=self.name, id=self.id))
            self._stop_remote_console()
        self._enable_remote_console = enable_remote_console

    @property
    def adapters(self):
        """
        Returns the number of adapters configured for this VMware VM.

        :returns: number of adapters
        """

        return self._adapters

    @adapters.setter
    def adapters(self, adapters):
        """
        Sets the number of Ethernet adapters for this VMware VM instance.

        :param adapters: number of adapters
        """

        # VMware VMs are limit to 10 adapters
        if adapters > 10:
            raise VMwareError("Number of adapters above the maximum supported of 10")

        self._ethernet_adapters.clear()
        for adapter_number in range(0, adapters):
            self._ethernet_adapters[adapter_number] = EthernetAdapter()

        self._adapters = len(self._ethernet_adapters)
        log.info("VMware VM '{name}' [{id}] has changed the number of Ethernet adapters to {adapters}".format(name=self.name,
                                                                                                              id=self.id,
                                                                                                              adapters=adapters))

    @property
    def adapter_type(self):
        """
        Returns the adapter type for this VMware VM instance.

        :returns: adapter type (string)
        """

        return self._adapter_type

    @adapter_type.setter
    def adapter_type(self, adapter_type):
        """
        Sets the adapter type for this VMware VM instance.

        :param adapter_type: adapter type (string)
        """

        self._adapter_type = adapter_type
        log.info("VMware VM '{name}' [{id}]: adapter type changed to {adapter_type}".format(name=self.name,
                                                                                            id=self.id,
                                                                                            adapter_type=adapter_type))

    @property
    def use_any_adapter(self):
        """
        Returns either GNS3 can use any VMware adapter on this instance.

        :returns: boolean
        """

        return self._use_any_adapter

    @use_any_adapter.setter
    def use_any_adapter(self, use_any_adapter):
        """
        Allows GNS3 to use any VMware adapter on this instance.

        :param use_any_adapter: boolean
        """

        if use_any_adapter:
            log.info("VMware VM '{name}' [{id}] is allowed to use any adapter".format(name=self.name, id=self.id))
        else:
            log.info("VMware VM '{name}' [{id}] is not allowed to use any adapter".format(name=self.name, id=self.id))
        self._use_any_adapter = use_any_adapter

    def adapter_add_nio_binding(self, adapter_number, nio):
        """
        Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise VMwareError("Adapter {adapter_number} doesn't exist on VMware VM '{name}'".format(name=self.name,
                                                                                                    adapter_number=adapter_number))

        adapter.add_nio(0, nio)
        log.info("VMware VM '{name}' [{id}]: {nio} added to adapter {adapter_number}".format(name=self.name,
                                                                                             id=self.id,
                                                                                             nio=nio,
                                                                                             adapter_number=adapter_number))

    def adapter_remove_nio_binding(self, adapter_number):
        """
        Removes an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise VMwareError("Adapter {adapter_number} doesn't exist on VMware VM '{name}'".format(name=self.name,
                                                                                                    adapter_number=adapter_number))

        nio = adapter.get_nio(0)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        adapter.remove_nio(0)

        log.info("VMware VM '{name}' [{id}]: {nio} removed from adapter {adapter_number}".format(name=self.name,
                                                                                                 id=self.id,
                                                                                                 nio=nio,
                                                                                                 adapter_number=adapter_number))
        return nio

    def _get_pipe_name(self):
        """
        Returns the pipe name to create a serial connection.

        :returns: pipe path (string)
        """

        if sys.platform.startswith("win"):
            pipe_name = r"\\.\pipe\gns3_vmware\{}".format(self.id)
        else:
            pipe_name = os.path.join(tempfile.gettempdir(), "gns3_vmware", "{}".format(self.id))
            try:
                os.makedirs(os.path.dirname(pipe_name), exist_ok=True)
            except OSError as e:
                raise VMwareError("Could not create the VMware pipe directory: {}".format(e))
        return pipe_name

    def _set_serial_console(self):
        """
        Configures the first serial port to allow a serial console connection.
        """

        pipe_name = self._get_pipe_name()
        serial_port = {"serial0.present": "TRUE",
                       "serial0.fileType": "pipe",
                       "serial0.fileName": pipe_name,
                       "serial0.pipe.endPoint": "server"}
        self._vmx_pairs.update(serial_port)

    def _start_remote_console(self):
        """
        Starts remote console support for this VM.
        """

        # starts the Telnet to pipe thread
        pipe_name = self._get_pipe_name()
        if sys.platform.startswith("win"):
            try:
                self._serial_pipe = open(pipe_name, "a+b")
            except OSError as e:
                raise VMwareError("Could not open the pipe {}: {}".format(pipe_name, e))
            try:
                self._telnet_server_thread = TelnetServer(self.name, msvcrt.get_osfhandle(self._serial_pipe.fileno()), self._manager.port_manager.console_host, self._console)
            except OSError as e:
                raise VMwareError("Unable to create Telnet server: {}".format(e))
            self._telnet_server_thread.start()
        else:
            try:
                self._serial_pipe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._serial_pipe.connect(pipe_name)
            except OSError as e:
                raise VMwareError("Could not connect to the pipe {}: {}".format(pipe_name, e))
            try:
                self._telnet_server_thread = TelnetServer(self.name, self._serial_pipe, self._manager.port_manager.console_host, self._console)
            except OSError as e:
                raise VMwareError("Unable to create Telnet server: {}".format(e))
            self._telnet_server_thread.start()

    def _stop_remote_console(self):
        """
        Stops remote console support for this VM.
        """

        if self._telnet_server_thread:
            if self._telnet_server_thread.is_alive():
                self._telnet_server_thread.stop()
                self._telnet_server_thread.join(timeout=3)
            if self._telnet_server_thread.is_alive():
                log.warn("Serial pipe thread is still alive!")
            self._telnet_server_thread = None

        if self._serial_pipe:
            if sys.platform.startswith("win"):
                win32file.CloseHandle(msvcrt.get_osfhandle(self._serial_pipe.fileno()))
            else:
                self._serial_pipe.close()
            self._serial_pipe = None
