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
VirtualBox VM instance.
"""

import sys
import shlex
import re
import os
import tempfile
import json
import socket
import asyncio

from pkg_resources import parse_version
from .virtualbox_error import VirtualBoxError
from ..adapters.ethernet_adapter import EthernetAdapter
from .telnet_server import TelnetServer  # TODO: port TelnetServer to asyncio
from ..base_vm import BaseVM

if sys.platform.startswith('win'):
    import msvcrt
    import win32file

import logging
log = logging.getLogger(__name__)


class VirtualBoxVM(BaseVM):
    """
    VirtualBox VM implementation.
    """

    def __init__(self, name, uuid, project, manager, vmname, linked_clone, adapters=0):

        super().__init__(name, uuid, project, manager)

        self._maximum_adapters = 8
        self._linked_clone = linked_clone
        self._system_properties = {}
        self._telnet_server_thread = None
        self._serial_pipe = None

        # VirtualBox settings
        self._console = None
        self._adapters = adapters
        self._ethernet_adapters = []
        self._headless = False
        self._enable_remote_console = False
        self._vmname = vmname
        self._adapter_start_index = 0
        self._adapter_type = "Intel PRO/1000 MT Desktop (82540EM)"

        if self._console is not None:
            self._console = self._manager.port_manager.reserve_console_port(self._console)
        else:
            self._console = self._manager.port_manager.get_free_console_port()

    def __json__(self):

        return {"name": self.name,
                "uuid": self.uuid,
                "console": self.console,
                "project_uuid": self.project.uuid,
                "vmname": self.vmname,
                "headless": self.headless,
                "enable_remote_console": self.enable_remote_console,
                "adapters": self._adapters,
                "adapter_type": self.adapter_type,
                "adapter_start_index": self.adapter_start_index}

    @asyncio.coroutine
    def _get_system_properties(self):

        properties = yield from self.manager.execute("list", ["systemproperties"])
        for prop in properties:
            try:
                name, value = prop.split(':', 1)
            except ValueError:
                continue
            self._system_properties[name.strip()] = value.strip()

    @asyncio.coroutine
    def _get_vm_state(self):
        """
        Returns the VM state (e.g. running, paused etc.)

        :returns: state (string)
        """

        results = yield from self.manager.execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in results:
            name, value = info.split('=', 1)
            if name == "VMState":
                return value.strip('"')
        raise VirtualBoxError("Could not get VM state for {}".format(self._vmname))

    @asyncio.coroutine
    def _control_vm(self, params):
        """
        Change setting in this VM when running.

        :param params: params to use with sub-command controlvm

        :returns: result of the command.
        """

        args = shlex.split(params)
        result = yield from self.manager.execute("controlvm", [self._vmname] + args)
        return result

    @asyncio.coroutine
    def _modify_vm(self, params):
        """
        Change setting in this VM when not running.

        :param params: params to use with sub-command modifyvm
        """

        args = shlex.split(params)
        yield from self.manager.execute("modifyvm", [self._vmname] + args)

    @asyncio.coroutine
    def create(self):

        yield from self._get_system_properties()
        if parse_version(self._system_properties["API version"]) < parse_version("4_3"):
            raise VirtualBoxError("The VirtualBox API version is lower than 4.3")
        log.info("VirtualBox VM '{name}' [{uuid}] created".format(name=self.name, uuid=self.uuid))

        if self._linked_clone:
            if self.uuid and os.path.isdir(os.path.join(self.working_dir, self._vmname)):
                vbox_file = os.path.join(self.working_dir, self._vmname, self._vmname + ".vbox")
                yield from self.manager.execute("registervm", [vbox_file])
                yield from self._reattach_hdds()
            else:
                yield from self._create_linked_clone()

        if self._adapters:
            yield from self.set_adapters(self._adapters)

    @asyncio.coroutine
    def start(self):
        """
        Starts this VirtualBox VM.
        """

        # resume the VM if it is paused
        vm_state = yield from self._get_vm_state()
        if vm_state == "paused":
            yield from self.resume()
            return

        # VM must be powered off and in saved state to start it
        if vm_state != "poweroff" and vm_state != "saved":
            raise VirtualBoxError("VirtualBox VM not powered off or saved")

        yield from self._set_network_options()
        yield from self._set_serial_console()

        args = [self._vmname]
        if self._headless:
            args.extend(["--type", "headless"])
        result = yield from self.manager.execute("startvm", args)
        log.info("VirtualBox VM '{name}' [{uuid}] started".format(name=self.name, uuid=self.uuid))
        log.debug("Start result: {}".format(result))

        # add a guest property to let the VM know about the GNS3 name
        yield from self.manager.execute("guestproperty", ["set", self._vmname, "NameInGNS3", self.name])
        # add a guest property to let the VM know about the GNS3 project directory
        yield from self.manager.execute("guestproperty", ["set", self._vmname, "ProjectDirInGNS3", self.working_dir])

        if self._enable_remote_console:
            self._start_remote_console()

    @asyncio.coroutine
    def stop(self):
        """
        Stops this VirtualBox VM.
        """

        self._stop_remote_console()
        vm_state = yield from self._get_vm_state()
        if vm_state == "running" or vm_state == "paused" or vm_state == "stuck":
            # power off the VM
            result = yield from self._control_vm("poweroff")
            log.info("VirtualBox VM '{name}' [{uuid}] stopped".format(name=self.name, uuid=self.uuid))
            log.debug("Stop result: {}".format(result))

            yield from asyncio.sleep(0.5)  # give some time for VirtualBox to unlock the VM
            try:
                # deactivate the first serial port
                yield from self._modify_vm("--uart1 off")
            except VirtualBoxError as e:
                log.warn("Could not deactivate the first serial port: {}".format(e))

            for adapter_id in range(0, len(self._ethernet_adapters)):
                if self._ethernet_adapters[adapter_id] is None:
                    continue
                yield from self._modify_vm("--nictrace{} off".format(adapter_id + 1))
                yield from self._modify_vm("--cableconnected{} off".format(adapter_id + 1))
                yield from self._modify_vm("--nic{} null".format(adapter_id + 1))

    @asyncio.coroutine
    def suspend(self):
        """
        Suspends this VirtualBox VM.
        """

        vm_state = yield from self._get_vm_state()
        if vm_state == "running":
            yield from self._control_vm("pause")
            log.info("VirtualBox VM '{name}' [{uuid}] suspended".format(name=self.name, uuid=self.uuid))
        else:
            log.warn("VirtualBox VM '{name}' [{uuid}] cannot be suspended, current state: {state}".format(name=self.name,
                                                                                                          uuid=self.uuid,
                                                                                                          state=vm_state))

    @asyncio.coroutine
    def resume(self):
        """
        Resumes this VirtualBox VM.
        """

        yield from self._control_vm("resume")
        log.info("VirtualBox VM '{name}' [{uuid}] resumed".format(name=self.name, uuid=self.uuid))

    @asyncio.coroutine
    def reload(self):
        """
        Reloads this VirtualBox VM.
        """

        result = yield from self._control_vm("reset")
        log.info("VirtualBox VM '{name}' [{uuid}] reloaded".format(name=self.name, uuid=self.uuid))
        log.debug("Reload result: {}".format(result))

    @property
    def console(self):
        """
        Returns the TCP console port.

        :returns: console port (integer)
        """

        return self._console

    @console.setter
    def console(self, console):
        """
        Sets the TCP console port.

        :param console: console port (integer)
        """

        if self._console:
            self._manager.port_manager.release_console_port(self._console)

        self._console = self._manager.port_manager.reserve_console_port(console)
        log.info("VirtualBox VM '{name}' [{uuid}]: console port set to {port}".format(name=self.name,
                                                                                      uuid=self.uuid,
                                                                                      port=console))

    @asyncio.coroutine
    def _get_all_hdd_files(self):

        hdds = []
        properties = yield from self.manager.execute("list", ["hdds"])
        for prop in properties:
            try:
                name, value = prop.split(':', 1)
            except ValueError:
                continue
            if name.strip() == "Location":
                hdds.append(value.strip())
        return hdds

    @asyncio.coroutine
    def _reattach_hdds(self):

        hdd_info_file = os.path.join(self.working_dir, self._vmname, "hdd_info.json")
        try:
            with open(hdd_info_file, "r") as f:
                hdd_table = json.load(f)
        except OSError as e:
            raise VirtualBoxError("Could not read HDD info file: {}".format(e))

        for hdd_info in hdd_table:
            hdd_file = os.path.join(self.working_dir, self._vmname, "Snapshots", hdd_info["hdd"])
            if os.path.exists(hdd_file):
                log.debug("reattaching hdd {}".format(hdd_file))
                yield from self._storage_attach('--storagectl "{}" --port {} --device {} --type hdd --medium "{}"'.format(hdd_info["controller"],
                                                                                                                          hdd_info["port"],
                                                                                                                          hdd_info["device"],
                                                                                                                          hdd_file))

    @asyncio.coroutine
    def close(self):
        """
        Closes this VirtualBox VM.
        """

        self.stop()

        if self._console:
            self._manager.port_manager.release_console_port(self._console)
            self._console = None

        if self._linked_clone:
            hdd_table = []
            if os.path.exists(self.working_dir):
                hdd_files = yield from self._get_all_hdd_files()
                vm_info = self._get_vm_info()
                for entry, value in vm_info.items():
                    match = re.search("^([\s\w]+)\-(\d)\-(\d)$", entry)
                    if match:
                        controller = match.group(1)
                        port = match.group(2)
                        device = match.group(3)
                        if value in hdd_files:
                            yield from self._storage_attach('--storagectl "{}" --port {} --device {} --type hdd --medium none'.format(controller, port, device))
                            hdd_table.append(
                                {
                                    "hdd": os.path.basename(value),
                                    "controller": controller,
                                    "port": port,
                                    "device": device,
                                }
                            )

            yield from self.manager.execute("unregistervm", [self._vmname])

            if hdd_table:
                try:
                    hdd_info_file = os.path.join(self.working_dir, self._vmname, "hdd_info.json")
                    with open(hdd_info_file, "w") as f:
                        # log.info("saving project: {}".format(path))
                        json.dump(hdd_table, f, indent=4)
                except OSError as e:
                    raise VirtualBoxError("Could not write HDD info file: {}".format(e))

        log.info("VirtualBox VM '{name}' [{uuid}] closed".format(name=self.name,
                                                                 uuid=self.uuid))

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
            log.info("VirtualBox VM '{name}' [{uuid}] has enabled the headless mode".format(name=self.name, uuid=self.uuid))
        else:
            log.info("VirtualBox VM '{name}' [{uuid}] has disabled the headless mode".format(name=self.name, uuid=self.uuid))
        self._headless = headless

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
            log.info("VirtualBox VM '{name}' [{uuid}] has enabled the console".format(name=self.name, uuid=self.uuid))
            self._start_remote_console()
        else:
            log.info("VirtualBox VM '{name}' [{uuid}] has disabled the console".format(name=self.name, uuid=self.uuid))
            self._stop_remote_console()
        self._enable_remote_console = enable_remote_console

    @property
    def vmname(self):
        """
        Returns the VM name associated with this VirtualBox VM.

        :returns: VirtualBox VM name
        """

        return self._vmname

    @vmname.setter
    def vmname(self, vmname):
        """
        Sets the VM name associated with this VirtualBox VM.

        :param vmname: VirtualBox VM name
        """

        log.info("VirtualBox VM '{name}' [{uuid}] has set the VM name to '{vmname}'".format(name=self.name, uuid=self.uuid, vmname=vmname))
        # TODO: test linked clone
        # if self._linked_clone:
        #    yield from self._modify_vm('--name "{}"'.format(vmname))
        self._vmname = vmname

    @asyncio.coroutine
    def set_adapters(self, adapters):
        """
        Sets the number of Ethernet adapters for this VirtualBox VM instance.

        :param adapters: number of adapters
        """

        # check for the maximum adapters supported by the VM
        self._maximum_adapters = yield from self._get_maximum_supported_adapters()
        if len(self._ethernet_adapters) > self._maximum_adapters:
            raise VirtualBoxError("Number of adapters above the maximum supported of {}".format(self._maximum_adapters))

        self._ethernet_adapters.clear()
        for adapter_id in range(0, self._adapter_start_index + adapters):
            if adapter_id < self._adapter_start_index:
                self._ethernet_adapters.append(None)
                continue
            self._ethernet_adapters.append(EthernetAdapter())

        self._adapters = len(self._ethernet_adapters)
        log.info("VirtualBox VM '{name}' [{uuid}]: number of Ethernet adapters changed to {adapters}".format(name=self.name,
                                                                                                             uuid=self.uuid,
                                                                                                             adapters=adapters))

    @property
    def adapter_start_index(self):
        """
        Returns the adapter start index for this VirtualBox VM instance.

        :returns: index
        """

        return self._adapter_start_index

    @adapter_start_index.setter
    def adapter_start_index(self, adapter_start_index):
        """
        Sets the adapter start index for this VirtualBox VM instance.

        :param adapter_start_index: index
        """

        self._adapter_start_index = adapter_start_index
        self.adapters = self.adapters  # this forces to recreate the adapter list with the correct index
        log.info("VirtualBox VM '{name}' [{uuid}]: adapter start index changed to {index}".format(name=self.name,
                                                                                                  uuid=self.uuid,
                                                                                                  index=adapter_start_index))

    @property
    def adapter_type(self):
        """
        Returns the adapter type for this VirtualBox VM instance.

        :returns: adapter type (string)
        """

        return self._adapter_type

    @adapter_type.setter
    def adapter_type(self, adapter_type):
        """
        Sets the adapter type for this VirtualBox VM instance.

        :param adapter_type: adapter type (string)
        """

        self._adapter_type = adapter_type

        log.info("VirtualBox VM '{name}' [{uuid}]: adapter type changed to {adapter_type}".format(name=self.name,
                                                                                                  uuid=self.uuid,
                                                                                                  adapter_type=adapter_type))

    @asyncio.coroutine
    def _get_vm_info(self):
        """
        Returns this VM info.

        :returns: dict of info
        """

        vm_info = {}
        results = yield from self.manager.execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in results:
            try:
                name, value = info.split('=', 1)
            except ValueError:
                continue
            vm_info[name.strip('"')] = value.strip('"')
        return vm_info

    @asyncio.coroutine
    def _get_maximum_supported_adapters(self):
        """
        Returns the maximum adapters supported by this VM.

        :returns: maximum number of supported adapters (int)
        """

        # check the maximum number of adapters supported by the VM
        vm_info = yield from self._get_vm_info()
        chipset = vm_info["chipset"]
        maximum_adapters = 8
        if chipset == "ich9":
            maximum_adapters = int(self._system_properties["Maximum ICH9 Network Adapter count"])
        return maximum_adapters

    def _get_pipe_name(self):
        """
        Returns the pipe name to create a serial connection.

        :returns: pipe path (string)
        """

        p = re.compile('\s+', re.UNICODE)
        pipe_name = p.sub("_", self._vmname)
        if sys.platform.startswith("win"):
            pipe_name = r"\\.\pipe\VBOX\{}".format(pipe_name)
        else:
            pipe_name = os.path.join(tempfile.gettempdir(), "pipe_{}".format(pipe_name))
        return pipe_name

    @asyncio.coroutine
    def _set_serial_console(self):
        """
        Configures the first serial port to allow a serial console connection.
        """

        # activate the first serial port
        yield from self._modify_vm("--uart1 0x3F8 4")

        # set server mode with a pipe on the first serial port
        pipe_name = self._get_pipe_name()
        args = [self._vmname, "--uartmode1", "server", pipe_name]
        yield from self.manager.execute("modifyvm", args)

    @asyncio.coroutine
    def _storage_attach(self, params):
        """
        Change storage medium in this VM.

        :param params: params to use with sub-command storageattach
        """

        args = shlex.split(params)
        yield from self.manager.execute("storageattach", [self._vmname] + args)

    @asyncio.coroutine
    def _get_nic_attachements(self, maximum_adapters):
        """
        Returns NIC attachements.

        :param maximum_adapters: maximum number of supported adapters
        :returns: list of adapters with their Attachment setting (NAT, bridged etc.)
        """

        nics = []
        vm_info = yield from self._get_vm_info()
        for adapter_id in range(0, maximum_adapters):
            entry = "nic{}".format(adapter_id + 1)
            if entry in vm_info:
                value = vm_info[entry]
                nics.append(value)
            else:
                nics.append(None)
        return nics

    @asyncio.coroutine
    def _set_network_options(self):
        """
        Configures network options.
        """

        nic_attachements = yield from self._get_nic_attachements(self._maximum_adapters)
        for adapter_id in range(0, len(self._ethernet_adapters)):
            if self._ethernet_adapters[adapter_id] is None:
                # force enable to avoid any discrepancy in the interface numbering inside the VM
                # e.g. Ethernet2 in GNS3 becoming eth0 inside the VM when using a start index of 2.
                attachement = nic_attachements[adapter_id]
                if attachement:
                    # attachement can be none, null, nat, bridged, intnet, hostonly or generic
                    yield from self._modify_vm("--nic{} {}".format(adapter_id + 1, attachement))
                continue

            vbox_adapter_type = "82540EM"
            if self._adapter_type == "PCnet-PCI II (Am79C970A)":
                vbox_adapter_type = "Am79C970A"
            if self._adapter_type == "PCNet-FAST III (Am79C973)":
                vbox_adapter_type = "Am79C973"
            if self._adapter_type == "Intel PRO/1000 MT Desktop (82540EM)":
                vbox_adapter_type = "82540EM"
            if self._adapter_type == "Intel PRO/1000 T Server (82543GC)":
                vbox_adapter_type = "82543GC"
            if self._adapter_type == "Intel PRO/1000 MT Server (82545EM)":
                vbox_adapter_type = "82545EM"
            if self._adapter_type == "Paravirtualized Network (virtio-net)":
                vbox_adapter_type = "virtio"

            args = [self._vmname, "--nictype{}".format(adapter_id + 1), vbox_adapter_type]
            yield from self.manager.execute("modifyvm", args)

            yield from self._modify_vm("--nictrace{} off".format(adapter_id + 1))
            nio = self._ethernet_adapters[adapter_id].get_nio(0)
            if nio:
                log.debug("setting UDP params on adapter {}".format(adapter_id))
                yield from self._modify_vm("--nic{} generic".format(adapter_id + 1))
                yield from self._modify_vm("--nicgenericdrv{} UDPTunnel".format(adapter_id + 1))
                yield from self._modify_vm("--nicproperty{} sport={}".format(adapter_id + 1, nio.lport))
                yield from self._modify_vm("--nicproperty{} dest={}".format(adapter_id + 1, nio.rhost))
                yield from self._modify_vm("--nicproperty{} dport={}".format(adapter_id + 1, nio.rport))
                yield from self._modify_vm("--cableconnected{} on".format(adapter_id + 1))

                if nio.capturing:
                    yield from self._modify_vm("--nictrace{} on".format(adapter_id + 1))
                    yield from self._modify_vm("--nictracefile{} {}".format(adapter_id + 1, nio.pcap_output_file))
            else:
                # shutting down unused adapters...
                yield from self._modify_vm("--cableconnected{} off".format(adapter_id + 1))
                yield from self._modify_vm("--nic{} null".format(adapter_id + 1))

        for adapter_id in range(len(self._ethernet_adapters), self._maximum_adapters):
            log.debug("disabling remaining adapter {}".format(adapter_id))
            yield from self._modify_vm("--nic{} none".format(adapter_id + 1))

    @asyncio.coroutine
    def _create_linked_clone(self):
        """
        Creates a new linked clone.
        """

        gns3_snapshot_exists = False
        vm_info = yield from self._get_vm_info()
        for entry, value in vm_info.items():
            if entry.startswith("SnapshotName") and value == "GNS3 Linked Base for clones":
                gns3_snapshot_exists = True

        if not gns3_snapshot_exists:
            result = yield from self.manager.execute("snapshot", [self._vmname, "take", "GNS3 Linked Base for clones"])
            log.debug("GNS3 snapshot created: {}".format(result))

        args = [self._vmname,
                "--snapshot",
                "GNS3 Linked Base for clones",
                "--options",
                "link",
                "--name",
                self.name,
                "--basefolder",
                self.working_dir,
                "--register"]

        result = yield from self.manager.execute("clonevm", args)
        log.debug("cloned VirtualBox VM: {}".format(result))

        self._vmname = self._name
        yield from self.manager.execute("setextradata", [self._vmname, "GNS3/Clone", "yes"])

        args = [self._name, "take", "reset"]
        result = yield from self.manager.execute("snapshot", args)
        log.debug("Snapshot reset created: {}".format(result))

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
                raise VirtualBoxError("Could not open the pipe {}: {}".format(pipe_name, e))
            self._telnet_server_thread = TelnetServer(self._vmname, msvcrt.get_osfhandle(self._serial_pipe.fileno()), self._console_host, self._console)
            self._telnet_server_thread.start()
        else:
            try:
                self._serial_pipe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._serial_pipe.connect(pipe_name)
            except OSError as e:
                raise VirtualBoxError("Could not connect to the pipe {}: {}".format(pipe_name, e))
            self._telnet_server_thread = TelnetServer(self._vmname, self._serial_pipe, self._console_host, self._console)
            self._telnet_server_thread.start()

    def _stop_remote_console(self):
        """
        Stops remote console support for this VM.
        """

        if self._telnet_server_thread:
            self._telnet_server_thread.stop()
            self._telnet_server_thread.join(timeout=3)
            if self._telnet_server_thread.isAlive():
                log.warn("Serial pipe thread is still alive!")
            self._telnet_server_thread = None

        if self._serial_pipe:
            if sys.platform.startswith('win'):
                win32file.CloseHandle(msvcrt.get_osfhandle(self._serial_pipe.fileno()))
            else:
                self._serial_pipe.close()
            self._serial_pipe = None

    @asyncio.coroutine
    def port_add_nio_binding(self, adapter_id, nio):
        """
        Adds a port NIO binding.

        :param adapter_id: adapter ID
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise VirtualBoxError("Adapter {adapter_id} doesn't exist on VirtualBox VM '{name}'".format(name=self.name,
                                                                                                        adapter_id=adapter_id))

        vm_state = yield from self._get_vm_state()
        if vm_state == "running":
            # dynamically configure an UDP tunnel on the VirtualBox adapter
            yield from self._control_vm("nic{} generic UDPTunnel".format(adapter_id + 1))
            yield from self._control_vm("nicproperty{} sport={}".format(adapter_id + 1, nio.lport))
            yield from self._control_vm("nicproperty{} dest={}".format(adapter_id + 1, nio.rhost))
            yield from self._control_vm("nicproperty{} dport={}".format(adapter_id + 1, nio.rport))
            yield from self._control_vm("setlinkstate{} on".format(adapter_id + 1))

        adapter.add_nio(0, nio)
        log.info("VirtualBox VM '{name}' [{uuid}]: {nio} added to adapter {adapter_id}".format(name=self.name,
                                                                                               uuid=self.uuid,
                                                                                               nio=nio,
                                                                                               adapter_id=adapter_id))

    @asyncio.coroutine
    def port_remove_nio_binding(self, adapter_id):
        """
        Removes a port NIO binding.

        :param adapter_id: adapter ID

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise VirtualBoxError("Adapter {adapter_id} doesn't exist on VirtualBox VM '{name}'".format(name=self.name,
                                                                                                        adapter_id=adapter_id))

        vm_state = yield from self._get_vm_state()
        if vm_state == "running":
            # dynamically disable the VirtualBox adapter
            yield from self._control_vm("setlinkstate{} off".format(adapter_id + 1))
            yield from self._control_vm("nic{} null".format(adapter_id + 1))

        nio = adapter.get_nio(0)
        if str(nio) == "NIO UDP":
            self.manager.port_manager.release_udp_port(nio.lport)
        adapter.remove_nio(0)

        log.info("VirtualBox VM '{name}' [{uuid}]: {nio} removed from adapter {adapter_id}".format(name=self.name,
                                                                                                   uuid=self.uuid,
                                                                                                   nio=nio,
                                                                                                   adapter_id=adapter_id))
        return nio

    def start_capture(self, adapter_id, output_file):
        """
        Starts a packet capture.

        :param adapter_id: adapter ID
        :param output_file: PCAP destination file for the capture
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise VirtualBoxError("Adapter {adapter_id} doesn't exist on VirtualBox VM '{name}'".format(name=self.name,
                                                                                                        adapter_id=adapter_id))

        nio = adapter.get_nio(0)
        if nio.capturing:
            raise VirtualBoxError("Packet capture is already activated on adapter {adapter_id}".format(adapter_id=adapter_id))

        nio.startPacketCapture(output_file)
        log.info("VirtualBox VM '{name}' [{uuid}]: starting packet capture on adapter {adapter_id}".format(name=self.name,
                                                                                                           uuid=self.uuid,
                                                                                                           adapter_id=adapter_id))

    def stop_capture(self, adapter_id):
        """
        Stops a packet capture.

        :param adapter_id: adapter ID
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise VirtualBoxError("Adapter {adapter_id} doesn't exist on VirtualBox VM '{name}'".format(name=self.name,
                                                                                                        adapter_id=adapter_id))

        nio = adapter.get_nio(0)
        nio.stopPacketCapture()

        log.info("VirtualBox VM '{name}' [{uuid}]: stopping packet capture on adapter {adapter_id}".format(name=self.name,
                                                                                                           uuid=self.uuid,
                                                                                                           adapter_id=adapter_id))
