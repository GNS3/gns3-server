# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
import asyncio
import tempfile

from gns3server.utils.interfaces import interfaces
from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer
from gns3server.utils.asyncio.serial import asyncio_open_serial
from gns3server.utils.asyncio import locked_coroutine
from collections import OrderedDict
from .vmware_error import VMwareError
from ..nios.nio_udp import NIOUDP
from ..adapters.ethernet_adapter import EthernetAdapter
from ..base_node import BaseNode


import logging
log = logging.getLogger(__name__)


class VMwareVM(BaseNode):

    """
    VMware VM implementation.
    """

    def __init__(self, name, node_id, project, manager, vmx_path, linked_clone=False, console=None):

        super().__init__(name, node_id, project, manager, console=console, linked_clone=linked_clone)

        self._vmx_pairs = OrderedDict()
        self._telnet_server = None
        self._vmnets = []
        self._maximum_adapters = 10
        self._started = False
        self._closed = False

        # VMware VM settings
        self._headless = False
        self._vmx_path = vmx_path
        self._acpi_shutdown = False
        self._adapters = 0
        self._ethernet_adapters = {}
        self._adapter_type = "e1000"
        self._use_any_adapter = False

        if not os.path.exists(vmx_path):
            raise VMwareError('VMware VM "{name}" [{id}]: could not find VMX file "{vmx_path}"'.format(name=name, id=node_id, vmx_path=vmx_path))

    def __json__(self):

        json = {"name": self.name,
                "node_id": self.id,
                "console": self.console,
                "console_type": self.console_type,
                "project_id": self.project.id,
                "vmx_path": self.vmx_path,
                "headless": self.headless,
                "acpi_shutdown": self.acpi_shutdown,
                "adapters": self._adapters,
                "adapter_type": self.adapter_type,
                "use_any_adapter": self.use_any_adapter,
                "status": self.status,
                "node_directory": self.working_dir,
                "linked_clone": self.linked_clone}
        return json

    @property
    def vmnets(self):

        return self._vmnets

    @locked_coroutine
    def _control_vm(self, subcommand, *additional_args):

        args = [self._vmx_path]
        args.extend(additional_args)
        result = yield from self.manager.execute(subcommand, args)
        log.debug("Control VM '{}' result: {}".format(subcommand, result))
        return result

    def _read_vmx_file(self):
        """
        Reads from the VMware VMX file corresponding to this VM.
        """

        try:
            self._vmx_pairs = self.manager.parse_vmware_file(self._vmx_path)
        except OSError as e:
            raise VMwareError('Could not read VMware VMX file "{}": {}'.format(self._vmx_path, e))

    def _write_vmx_file(self):
        """
        Writes pairs to the VMware VMX file corresponding to this VM.
        """

        try:
            self.manager.write_vmx_file(self._vmx_path, self._vmx_pairs)
        except OSError as e:
            raise VMwareError('Could not write VMware VMX file "{}": {}'.format(self._vmx_path, e))

    @asyncio.coroutine
    def is_running(self):

        result = yield from self.manager.execute("list", [])
        if self._vmx_path in result:
            return True
        return False

    @asyncio.coroutine
    def _check_duplicate_linked_clone(self):
        """
        Without linked clone two VM using the same image can't run
        at the same time.

        To avoid issue like false detection when a project close
        and another open we try multiple times.
        """
        trial = 0

        while True:
            found = False
            for node in self.manager.nodes:
                if node != self and node.vmx_path == self._vmx_path:
                    found = True
                    if node.project != self.project:
                        if trial >= 30:
                            raise VMwareError("Sorry a node without the linked clone setting enabled can only be used once on your server.\n{} is already used by {} in project {}".format(self.vmx_path, node.name, self.project.name))
                    else:
                        if trial >= 5:
                            raise VMwareError("Sorry a node without the linked clone setting enabled can only be used once on your server.\n{} is already used by {} in this project".format(self.vmx_path, node.name))
            if not found:
                return
            trial += 1
            yield from asyncio.sleep(1)

    @asyncio.coroutine
    def create(self):
        """
        Creates this VM and handle linked clones.
        """
        if not self.linked_clone:
            yield from self._check_duplicate_linked_clone()

        yield from self.manager.check_vmrun_version()
        if self.linked_clone and not os.path.exists(os.path.join(self.working_dir, os.path.basename(self._vmx_path))):
            if self.manager.host_type == "player":
                raise VMwareError("Linked clones are not supported by VMware Player")
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
        """
        Set up VMware networking.
        """

        # first some sanity checks
        for adapter_number in range(0, self._adapters):

            # we want the vmnet interface to be connected when starting the VM
            connected = "ethernet{}.startConnected".format(adapter_number)
            if self._get_vmx_setting(connected):
                del self._vmx_pairs[connected]

        # then configure VMware network adapters
        self.manager.refresh_vmnet_list()
        for adapter_number in range(0, self._adapters):

            # add/update the interface
            if self._adapter_type == "default":
                # force default to e1000 because some guest OS don't detect the adapter (i.e. Windows 2012 server)
                # when 'virtualdev' is not set in the VMX file.
                adapter_type = "e1000"
            else:
                adapter_type = self._adapter_type
            ethernet_adapter = {"ethernet{}.present".format(adapter_number): "TRUE",
                                "ethernet{}.addresstype".format(adapter_number): "generated",
                                "ethernet{}.generatedaddressoffset".format(adapter_number): "0",
                                "ethernet{}.virtualdev".format(adapter_number): adapter_type}
            self._vmx_pairs.update(ethernet_adapter)

            connection_type = "ethernet{}.connectiontype".format(adapter_number)
            if not self._use_any_adapter and connection_type in self._vmx_pairs and self._vmx_pairs[connection_type] in ("nat", "bridged", "hostonly"):
                continue

            self._vmx_pairs["ethernet{}.connectiontype".format(adapter_number)] = "custom"
            # make sure we have a vmnet per adapter if we use uBridge
            allocate_vmnet = False

            # first check if a vmnet is already assigned to the adapter
            vnet = "ethernet{}.vnet".format(adapter_number)
            if vnet in self._vmx_pairs:
                vmnet = os.path.basename(self._vmx_pairs[vnet])
                if self.manager.is_managed_vmnet(vmnet) or vmnet in ("vmnet0", "vmnet1", "vmnet8"):
                    # vmnet already managed, try to allocate a new one
                    allocate_vmnet = True
            else:
                # otherwise allocate a new one
                allocate_vmnet = True

            if allocate_vmnet:
                try:
                    vmnet = self.manager.allocate_vmnet()
                except:
                    # clear everything up in case of error (e.g. no enough vmnets)
                    self._vmnets.clear()
                    raise

            # mark the vmnet managed by us
            if vmnet not in self._vmnets:
                self._vmnets.append(vmnet)
            self._vmx_pairs["ethernet{}.vnet".format(adapter_number)] = vmnet

        # disable remaining network adapters
        for adapter_number in range(self._adapters, self._maximum_adapters):
            if self._get_vmx_setting("ethernet{}.present".format(adapter_number), "TRUE"):
                log.debug("disabling remaining adapter {}".format(adapter_number))
                self._vmx_pairs["ethernet{}.startconnected".format(adapter_number)] = "FALSE"

    @asyncio.coroutine
    def _add_ubridge_connection(self, nio, adapter_number):
        """
        Creates a connection in uBridge.

        :param nio: NIO instance
        :param adapter_number: adapter number
        """

        block_host_traffic = self.manager.config.get_section_config("VMware").getboolean("block_host_traffic", False)
        vnet = "ethernet{}.vnet".format(adapter_number)
        if vnet not in self._vmx_pairs:
            raise VMwareError("vnet {} not in VMX file".format(vnet))
        yield from self._ubridge_send("bridge create {name}".format(name=vnet))
        vmnet_interface = os.path.basename(self._vmx_pairs[vnet])

        if sys.platform.startswith("darwin"):
            # special case on OSX, we cannot bind VMnet interfaces using the libpcap
            yield from self._ubridge_send('bridge add_nio_fusion_vmnet {name} "{interface}"'.format(name=vnet, interface=vmnet_interface))
        else:
            yield from self._add_ubridge_ethernet_connection(vnet, vmnet_interface, block_host_traffic)

        if isinstance(nio, NIOUDP):
            yield from self._ubridge_send('bridge add_nio_udp {name} {lport} {rhost} {rport}'.format(name=vnet,
                                                                                                     lport=nio.lport,
                                                                                                     rhost=nio.rhost,
                                                                                                     rport=nio.rport))

        if nio.capturing:
            yield from self._ubridge_send('bridge start_capture {name} "{pcap_file}"'.format(name=vnet, pcap_file=nio.pcap_output_file))

        yield from self._ubridge_send('bridge start {name}'.format(name=vnet))

        # TODO: this only work when using PCAP (NIO Ethernet): current default on Linux is NIO RAW LINUX
        # source_mac = None
        # for interface in interfaces():
        #     if interface["name"] == vmnet_interface:
        #         source_mac = interface["mac_address"]
        # if source_mac:
        #     yield from self._ubridge_send('bridge set_pcap_filter {name} "not ether src {mac}"'.format(name=vnet, mac=source_mac))

    @asyncio.coroutine
    def _delete_ubridge_connection(self, adapter_number):
        """
        Deletes a connection in uBridge.

        :param adapter_number: adapter number
        """

        vnet = "ethernet{}.vnet".format(adapter_number)
        if vnet not in self._vmx_pairs:
            raise VMwareError("vnet {} not in VMX file".format(vnet))
        yield from self._ubridge_send("bridge delete {name}".format(name=vnet))

    @asyncio.coroutine
    def _start_ubridge_capture(self, adapter_number, output_file):
        """
        Start a packet capture in uBridge.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        vnet = "ethernet{}.vnet".format(adapter_number)
        if vnet not in self._vmx_pairs:
            raise VMwareError("vnet {} not in VMX file".format(vnet))
        if not self._ubridge_hypervisor:
            raise VMwareError("Cannot start the packet capture: uBridge is not running")
        yield from self._ubridge_send('bridge start_capture {name} "{output_file}"'.format(name=vnet,
                                                                                           output_file=output_file))

    @asyncio.coroutine
    def _stop_ubridge_capture(self, adapter_number):
        """
        Stop a packet capture in uBridge.

        :param adapter_number: adapter number
        """

        vnet = "ethernet{}.vnet".format(adapter_number)
        if vnet not in self._vmx_pairs:
            raise VMwareError("vnet {} not in VMX file".format(vnet))
        if not self._ubridge_hypervisor:
            raise VMwareError("Cannot stop the packet capture: uBridge is not running")
        yield from self._ubridge_send("bridge stop_capture {name}".format(name=vnet))

    def check_hw_virtualization(self):
        """
        Returns either hardware virtualization is activated or not.

        :returns: boolean
        """

        self._read_vmx_file()
        if self._get_vmx_setting("vhv.enable", "TRUE"):
            return True
        return False

    @asyncio.coroutine
    def start(self):
        """
        Starts this VMware VM.
        """

        if self.status == "started":
            return

        if (yield from self.is_running()):
            raise VMwareError("The VM is already running in VMware")

        ubridge_path = self.ubridge_path
        if not ubridge_path or not os.path.isfile(ubridge_path):
            raise VMwareError("ubridge is necessary to start a VMware VM")

        yield from self._start_ubridge()
        self._read_vmx_file()
        # check if there is enough RAM to run
        if "memsize" in self._vmx_pairs:
            self.check_available_ram(int(self._vmx_pairs["memsize"]))
        self._set_network_options()
        self._set_serial_console()
        self._write_vmx_file()

        if self._headless:
            yield from self._control_vm("start", "nogui")
        else:
            yield from self._control_vm("start")

        try:
            if self._ubridge_hypervisor:
                for adapter_number in range(0, self._adapters):
                    nio = self._ethernet_adapters[adapter_number].get_nio(0)
                    if nio:
                        yield from self._add_ubridge_connection(nio, adapter_number)

            yield from self._start_console()
        except VMwareError:
            yield from self.stop()
            raise

        if self._get_vmx_setting("vhv.enable", "TRUE"):
            self._hw_virtualization = True

        self._started = True
        self.status = "started"
        log.info("VMware VM '{name}' [{id}] started".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def stop(self):
        """
        Stops this VMware VM.
        """

        self._hw_virtualization = False
        yield from self._stop_remote_console()
        yield from self._stop_ubridge()

        try:
            if (yield from self.is_running()):
                if self.acpi_shutdown:
                    # use ACPI to shutdown the VM
                    yield from self._control_vm("stop", "soft")
                else:
                    yield from self._control_vm("stop")
        finally:
            self._started = False
            self.status = "stopped"

            self._read_vmx_file()
            self._vmnets.clear()
            # remove the adapters managed by GNS3
            for adapter_number in range(0, self._adapters):
                vnet = "ethernet{}.vnet".format(adapter_number)
                if self._get_vmx_setting(vnet) or self._get_vmx_setting("ethernet{}.connectiontype".format(adapter_number)) is None:
                    if vnet in self._vmx_pairs:
                        vmnet = os.path.basename(self._vmx_pairs[vnet])
                        if not self.manager.is_managed_vmnet(vmnet):
                            continue
                    log.debug("removing adapter {}".format(adapter_number))
                    self._vmx_pairs[vnet] = "vmnet1"
                    self._vmx_pairs["ethernet{}.connectiontype".format(adapter_number)] = "custom"

            # re-enable any remaining network adapters
            for adapter_number in range(self._adapters, self._maximum_adapters):
                if self._get_vmx_setting("ethernet{}.present".format(adapter_number), "TRUE"):
                    log.debug("enabling remaining adapter {}".format(adapter_number))
                    self._vmx_pairs["ethernet{}.startconnected".format(adapter_number)] = "TRUE"
            self._write_vmx_file()

        yield from super().stop()
        log.info("VMware VM '{name}' [{id}] stopped".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def suspend(self):
        """
        Suspends this VMware VM.
        """

        if self.manager.host_type != "ws":
            raise VMwareError("Pausing a VM is only supported by VMware Workstation")
        yield from self._control_vm("pause")
        self.status = "suspended"
        log.info("VMware VM '{name}' [{id}] paused".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def resume(self):
        """
        Resumes this VMware VM.
        """

        if self.manager.host_type != "ws":
            raise VMwareError("Unpausing a VM is only supported by VMware Workstation")
        yield from self._control_vm("unpause")
        self.status = "started"
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
        Closes this VMware VM.
        """

        if not (yield from super().close()):
            return False

        for adapter in self._ethernet_adapters.values():
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(nio.lport, self._project)
        try:
            self.acpi_shutdown = False
            yield from self.stop()
        except VMwareError:
            pass

        if self.linked_clone:
            yield from self.manager.remove_from_vmware_inventory(self._vmx_path)

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
    def acpi_shutdown(self):
        """
        Returns either the VM will use ACPI shutdown

        :returns: boolean
        """

        return self._acpi_shutdown

    @acpi_shutdown.setter
    def acpi_shutdown(self, acpi_shutdown):
        """
        Sets either the VM will use ACPI shutdown

        :param acpi_shutdown: boolean
        """

        if acpi_shutdown:
            log.info("VMware VM '{name}' [{id}] has enabled the ACPI shutdown mode".format(name=self.name, id=self.id))
        else:
            log.info("VMware VM '{name}' [{id}] has disabled the ACPI shutdown mode".format(name=self.name, id=self.id))
        self._acpi_shutdown = acpi_shutdown

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

        # VMware VMs are limited to 10 adapters
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

    @asyncio.coroutine
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

        self._read_vmx_file()
        # check if trying to connect to a nat, bridged or host-only adapter
        if not self._use_any_adapter and self._get_vmx_setting("ethernet{}.present".format(adapter_number), "TRUE"):
            # check for the connection type
            connection_type = "ethernet{}.connectiontype".format(adapter_number)
            if connection_type in self._vmx_pairs and self._vmx_pairs[connection_type] in ("nat", "bridged", "hostonly"):
                raise VMwareError("Attachment ({}) already configured on network adapter {}. "
                                  "Please remove it or allow GNS3 to use any adapter.".format(self._vmx_pairs[connection_type],
                                                                                              adapter_number))

        adapter.add_nio(0, nio)
        if self._started and self._ubridge_hypervisor:
            yield from self._add_ubridge_connection(nio, adapter_number)

        log.info("VMware VM '{name}' [{id}]: {nio} added to adapter {adapter_number}".format(name=self.name,
                                                                                             id=self.id,
                                                                                             nio=nio,
                                                                                             adapter_number=adapter_number))

    @asyncio.coroutine
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
        if self._started and self._ubridge_hypervisor:
            yield from self._delete_ubridge_connection(adapter_number)

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
                       "serial0.filetype": "pipe",
                       "serial0.filename": pipe_name,
                       "serial0.pipe.endpoint": "server",
                       "serial0.startconnected": "TRUE"}
        self._vmx_pairs.update(serial_port)

    @asyncio.coroutine
    def _start_console(self):
        """
        Starts remote console support for this VM.
        """
        self._remote_pipe = yield from asyncio_open_serial(self._get_pipe_name())
        server = AsyncioTelnetServer(reader=self._remote_pipe,
                                     writer=self._remote_pipe,
                                     binary=True,
                                     echo=True)
        self._telnet_server = yield from asyncio.start_server(server.run, self._manager.port_manager.console_host, self.console)

    @asyncio.coroutine
    def _stop_remote_console(self):
        """
        Stops remote console support for this VM.
        """
        if self._telnet_server:
            self._telnet_server.close()
            yield from self._telnet_server.wait_closed()
            self._remote_pipe.close()
            self._telnet_server = None

    @asyncio.coroutine
    def start_capture(self, adapter_number, output_file):
        """
        Starts a packet capture.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except KeyError:
            raise VMwareError("Adapter {adapter_number} doesn't exist on VMware VM '{name}'".format(name=self.name,
                                                                                                    adapter_number=adapter_number))

        nio = adapter.get_nio(0)

        if not nio:
            raise VMwareError("Adapter {} is not connected".format(adapter_number))

        if nio.capturing:
            raise VMwareError("Packet capture is already activated on adapter {adapter_number}".format(adapter_number=adapter_number))

        nio.startPacketCapture(output_file)

        if self._started:
            yield from self._start_ubridge_capture(adapter_number, output_file)

        log.info("VMware VM '{name}' [{id}]: starting packet capture on adapter {adapter_number}".format(name=self.name,
                                                                                                         id=self.id,
                                                                                                         adapter_number=adapter_number))

    def stop_capture(self, adapter_number):
        """
        Stops a packet capture.

        :param adapter_number: adapter number
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except KeyError:
            raise VMwareError("Adapter {adapter_number} doesn't exist on VMware VM '{name}'".format(name=self.name,
                                                                                                    adapter_number=adapter_number))

        nio = adapter.get_nio(0)

        if not nio:
            raise VMwareError("Adapter {} is not connected".format(adapter_number))

        nio.stopPacketCapture()

        if self._started:
            yield from self._stop_ubridge_capture(adapter_number)

        log.info("VMware VM '{name}' [{id}]: stopping packet capture on adapter {adapter_number}".format(name=self.name,
                                                                                                         id=self.id,
                                                                                                         adapter_number=adapter_number))
