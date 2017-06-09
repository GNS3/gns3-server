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

import re
import os
import sys
import json
import uuid
import shlex
import shutil
import socket
import asyncio
import tempfile
import xml.etree.ElementTree as ET

from gns3server.utils import parse_version
from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer
from gns3server.utils.asyncio.serial import asyncio_open_serial
from gns3server.utils.asyncio import locked_coroutine
from gns3server.compute.virtualbox.virtualbox_error import VirtualBoxError
from gns3server.compute.nios.nio_udp import NIOUDP
from gns3server.compute.adapters.ethernet_adapter import EthernetAdapter
from gns3server.compute.base_node import BaseNode

if sys.platform.startswith('win'):
    import msvcrt
    import win32file

import logging
log = logging.getLogger(__name__)


class VirtualBoxVM(BaseNode):

    """
    VirtualBox VM implementation.
    """

    def __init__(self, name, node_id, project, manager, vmname, linked_clone=False, console=None, adapters=0):

        super().__init__(name, node_id, project, manager, console=console, linked_clone=linked_clone, console_type="telnet")

        self._maximum_adapters = 8
        self._system_properties = {}
        self._telnet_server = None
        self._local_udp_tunnels = {}

        # VirtualBox settings
        self._adapters = adapters
        self._ethernet_adapters = {}
        self._headless = False
        self._acpi_shutdown = False
        self._vmname = vmname
        self._use_any_adapter = False
        self._ram = 0
        self._adapter_type = "Intel PRO/1000 MT Desktop (82540EM)"

    def __json__(self):

        json = {"name": self.name,
                "node_id": self.id,
                "console": self.console,
                "console_type": self.console_type,
                "project_id": self.project.id,
                "vmname": self.vmname,
                "headless": self.headless,
                "acpi_shutdown": self.acpi_shutdown,
                "adapters": self._adapters,
                "adapter_type": self.adapter_type,
                "ram": self.ram,
                "status": self.status,
                "use_any_adapter": self.use_any_adapter,
                "linked_clone": self.linked_clone}
        if self.linked_clone:
            json["node_directory"] = self.working_dir
        else:
            json["node_directory"] = None
        return json

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
            if '=' in info:
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
                if node != self and node.vmname == self.vmname:
                    found = True
                    if node.project != self.project:
                        if trial >= 30:
                            raise VirtualBoxError("Sorry a node without the linked clone setting enabled can only be used once on your server.\n{} is already used by {} in project {}".format(self.vmname, node.name, self.project.name))
                    else:
                        if trial >= 5:
                            raise VirtualBoxError("Sorry a node without the linked clone setting enabled can only be used once on your server.\n{} is already used by {} in this project".format(self.vmname, node.name))
            if not found:
                return
            trial += 1
            yield from asyncio.sleep(1)

    @asyncio.coroutine
    def create(self):
        if not self.linked_clone:
            yield from self._check_duplicate_linked_clone()

        yield from self._get_system_properties()
        if "API version" not in self._system_properties:
            raise VirtualBoxError("Can't access to VirtualBox API version:\n{}".format(self._system_properties))
        if parse_version(self._system_properties["API version"]) < parse_version("4_3"):
            raise VirtualBoxError("The VirtualBox API version is lower than 4.3")
        log.info("VirtualBox VM '{name}' [{id}] created".format(name=self.name, id=self.id))

        if self.linked_clone:
            if self.id and os.path.isdir(os.path.join(self.working_dir, self._vmname)):
                self._patch_vm_uuid()
                yield from self.manager.execute("registervm", [self._linked_vbox_file()])
                yield from self._reattach_linked_hdds()
            else:
                yield from self._create_linked_clone()

        if self._adapters:
            yield from self.set_adapters(self._adapters)

        vm_info = yield from self._get_vm_info()
        if "memory" in vm_info:
            self._ram = int(vm_info["memory"])

    def _linked_vbox_file(self):
        return os.path.join(self.working_dir, self._vmname, self._vmname + ".vbox")

    def _patch_vm_uuid(self):
        """
        Fix the VM uuid in the case of linked clone
        """
        if os.path.exists(self._linked_vbox_file()):
            try:
                tree = ET.parse(self._linked_vbox_file())
            except ET.ParseError:
                raise VirtualBoxError("Cannot modify VirtualBox linked nodes file. "
                                      "File {} is corrupted.".format(self._linked_vbox_file()))

            machine = tree.getroot().find("{http://www.virtualbox.org/}Machine")
            if machine is not None and machine.get("uuid") != "{" + self.id + "}":

                for image in tree.getroot().findall("{http://www.virtualbox.org/}Image"):
                    currentSnapshot = machine.get("currentSnapshot")
                    if currentSnapshot:
                        newSnapshot = re.sub("\{.*\}", "{" + str(uuid.uuid4()) + "}", currentSnapshot)
                    shutil.move(os.path.join(self.working_dir, self._vmname, "Snapshots", currentSnapshot) + ".vdi",
                                os.path.join(self.working_dir, self._vmname, "Snapshots", newSnapshot) + ".vdi")
                    image.set("uuid", newSnapshot)

                machine.set("uuid", "{" + self.id + "}")
                tree.write(self._linked_vbox_file())

    @asyncio.coroutine
    def check_hw_virtualization(self):
        """
        Returns either hardware virtualization is activated or not.

        :returns: boolean
        """

        vm_info = yield from self._get_vm_info()
        if "hwvirtex" in vm_info and vm_info["hwvirtex"] == "on":
            return True
        return False

    @asyncio.coroutine
    def start(self):
        """
        Starts this VirtualBox VM.
        """

        if self.status == "started":
            return

        # resume the VM if it is paused
        vm_state = yield from self._get_vm_state()
        if vm_state == "paused":
            yield from self.resume()
            return

        # VM must be powered off to start it
        if vm_state != "poweroff":
            raise VirtualBoxError("VirtualBox VM not powered off")

        yield from self._set_network_options()
        yield from self._set_serial_console()

        # check if there is enough RAM to run
        self.check_available_ram(self.ram)

        args = [self._vmname]
        if self._headless:
            args.extend(["--type", "headless"])
        result = yield from self.manager.execute("startvm", args)
        self.status = "started"
        log.info("VirtualBox VM '{name}' [{id}] started".format(name=self.name, id=self.id))
        log.debug("Start result: {}".format(result))

        # add a guest property to let the VM know about the GNS3 name
        yield from self.manager.execute("guestproperty", ["set", self._vmname, "NameInGNS3", self.name])
        # add a guest property to let the VM know about the GNS3 project directory
        yield from self.manager.execute("guestproperty", ["set", self._vmname, "ProjectDirInGNS3", self.working_dir])

        if self.use_ubridge:
            yield from self._start_ubridge()
            for adapter_number in range(0, self._adapters):
                nio = self._ethernet_adapters[adapter_number].get_nio(0)
                if nio:
                    yield from self._add_ubridge_udp_connection("VBOX-{}-{}".format(self._id, adapter_number),
                                                                self._local_udp_tunnels[adapter_number][1],
                                                                nio)

        yield from self._start_console()

        if (yield from self.check_hw_virtualization()):
            self._hw_virtualization = True

    @locked_coroutine
    def stop(self):
        """
        Stops this VirtualBox VM.
        """

        self._hw_virtualization = False
        yield from self._stop_ubridge()
        yield from self._stop_remote_console()
        vm_state = yield from self._get_vm_state()
        if vm_state == "running" or vm_state == "paused" or vm_state == "stuck":
            if self.acpi_shutdown:
                # use ACPI to shutdown the VM
                result = yield from self._control_vm("acpipowerbutton")
                trial = 0
                while True:
                    vm_state = yield from self._get_vm_state()
                    if vm_state == "poweroff":
                        break
                    yield from asyncio.sleep(1)
                    trial += 1
                    if trial >= 120:
                        yield from self._control_vm("poweroff")
                        break
                self.status = "stopped"
                log.debug("ACPI shutdown result: {}".format(result))
            else:
                # power off the VM
                result = yield from self._control_vm("poweroff")
                self.status = "stopped"
                log.debug("Stop result: {}".format(result))

            log.info("VirtualBox VM '{name}' [{id}] stopped".format(name=self.name, id=self.id))
            yield from asyncio.sleep(0.5)  # give some time for VirtualBox to unlock the VM
            try:
                # deactivate the first serial port
                yield from self._modify_vm("--uart1 off")
            except VirtualBoxError as e:
                log.warn("Could not deactivate the first serial port: {}".format(e))

            for adapter_number in range(0, self._adapters):
                nio = self._ethernet_adapters[adapter_number].get_nio(0)
                if nio:
                    yield from self._modify_vm("--nictrace{} off".format(adapter_number + 1))
                    yield from self._modify_vm("--cableconnected{} off".format(adapter_number + 1))
                    yield from self._modify_vm("--nic{} null".format(adapter_number + 1))
        yield from super().stop()

    @asyncio.coroutine
    def suspend(self):
        """
        Suspends this VirtualBox VM.
        """

        vm_state = yield from self._get_vm_state()
        if vm_state == "running":
            yield from self._control_vm("pause")
            self.status = "suspended"
            log.info("VirtualBox VM '{name}' [{id}] suspended".format(name=self.name, id=self.id))
        else:
            log.warn("VirtualBox VM '{name}' [{id}] cannot be suspended, current state: {state}".format(name=self.name,
                                                                                                        id=self.id,
                                                                                                        state=vm_state))

    @asyncio.coroutine
    def resume(self):
        """
        Resumes this VirtualBox VM.
        """

        yield from self._control_vm("resume")
        self.status = "started"
        log.info("VirtualBox VM '{name}' [{id}] resumed".format(name=self.name, id=self.id))

    @asyncio.coroutine
    def reload(self):
        """
        Reloads this VirtualBox VM.
        """

        result = yield from self._control_vm("reset")
        log.info("VirtualBox VM '{name}' [{id}] reloaded".format(name=self.name, id=self.id))
        log.debug("Reload result: {}".format(result))

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
    def _reattach_linked_hdds(self):
        """
        Reattach linked cloned hard disks.
        """

        hdd_info_file = os.path.join(self.working_dir, self._vmname, "hdd_info.json")
        try:
            with open(hdd_info_file, "r", encoding="utf-8") as f:
                hdd_table = json.load(f)
        except (ValueError, OSError) as e:
            # The VM has never be started
            return

        for hdd_info in hdd_table:
            hdd_file = os.path.join(self.working_dir, self._vmname, "Snapshots", hdd_info["hdd"])
            if os.path.exists(hdd_file):
                log.info("VirtualBox VM '{name}' [{id}] attaching HDD {controller} {port} {device} {medium}".format(name=self.name,
                                                                                                                    id=self.id,
                                                                                                                    controller=hdd_info["controller"],
                                                                                                                    port=hdd_info["port"],
                                                                                                                    device=hdd_info["device"],
                                                                                                                    medium=hdd_file))

                try:
                    yield from self._storage_attach('--storagectl "{}" --port {} --device {} --type hdd --medium "{}"'.format(hdd_info["controller"],
                                                                                                                              hdd_info["port"],
                                                                                                                              hdd_info["device"],
                                                                                                                              hdd_file))

                except VirtualBoxError as e:
                    log.warn("VirtualBox VM '{name}' [{id}] error reattaching HDD {controller} {port} {device} {medium}: {error}".format(name=self.name,
                                                                                                                                         id=self.id,
                                                                                                                                         controller=hdd_info["controller"],
                                                                                                                                         port=hdd_info["port"],
                                                                                                                                         device=hdd_info["device"],
                                                                                                                                         medium=hdd_file,
                                                                                                                                         error=e))
                    continue

    @asyncio.coroutine
    def save_linked_hdds_info(self):
        """
        Save linked cloned hard disks information.

        :returns: disk table information
        """

        hdd_table = []
        if self.linked_clone:
            if os.path.exists(self.working_dir):
                hdd_files = yield from self._get_all_hdd_files()
                vm_info = yield from self._get_vm_info()
                for entry, value in vm_info.items():
                    match = re.search("^([\s\w]+)\-(\d)\-(\d)$", entry)  # match Controller-PortNumber-DeviceNumber entry
                    if match:
                        controller = match.group(1)
                        port = match.group(2)
                        device = match.group(3)
                        if value in hdd_files and os.path.exists(os.path.join(self.working_dir, self._vmname, "Snapshots", os.path.basename(value))):
                            log.info("VirtualBox VM '{name}' [{id}] detaching HDD {controller} {port} {device}".format(name=self.name,
                                                                                                                       id=self.id,
                                                                                                                       controller=controller,
                                                                                                                       port=port,
                                                                                                                       device=device))
                            hdd_table.append(
                                {
                                    "hdd": os.path.basename(value),
                                    "controller": controller,
                                    "port": port,
                                    "device": device,
                                }
                            )

            if hdd_table:
                try:
                    hdd_info_file = os.path.join(self.working_dir, self._vmname, "hdd_info.json")
                    with open(hdd_info_file, "w", encoding="utf-8") as f:
                        json.dump(hdd_table, f, indent=4)
                except OSError as e:
                    log.warning("VirtualBox VM '{name}' [{id}] could not write HHD info file: {error}".format(name=self.name,
                                                                                                              id=self.id,
                                                                                                              error=e.strerror))

        return hdd_table

    @asyncio.coroutine
    def close(self):
        """
        Closes this VirtualBox VM.
        """

        if self._closed:
            # VM is already closed
            return

        if not (yield from super().close()):
            return False

        log.debug("VirtualBox VM '{name}' [{id}] is closing".format(name=self.name, id=self.id))
        if self._console:
            self._manager.port_manager.release_tcp_port(self._console, self._project)
            self._console = None

        for adapter in self._ethernet_adapters.values():
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(nio.lport, self._project)

        for udp_tunnel in self._local_udp_tunnels.values():
            self.manager.port_manager.release_udp_port(udp_tunnel[0].lport, self._project)
            self.manager.port_manager.release_udp_port(udp_tunnel[1].lport, self._project)
        self._local_udp_tunnels = {}

        self.acpi_shutdown = False
        yield from self.stop()

        if self.linked_clone:
            hdd_table = yield from self.save_linked_hdds_info()
            for hdd in hdd_table.copy():
                log.info("VirtualBox VM '{name}' [{id}] detaching HDD {controller} {port} {device}".format(name=self.name,
                                                                                                           id=self.id,
                                                                                                           controller=hdd["controller"],
                                                                                                           port=hdd["port"],
                                                                                                           device=hdd["device"]))
                try:
                    yield from self._storage_attach('--storagectl "{}" --port {} --device {} --type hdd --medium none'.format(hdd["controller"],
                                                                                                                              hdd["port"],
                                                                                                                              hdd["device"]))
                except VirtualBoxError as e:
                    log.warn("VirtualBox VM '{name}' [{id}] error detaching HDD {controller} {port} {device}: {error}".format(name=self.name,
                                                                                                                              id=self.id,
                                                                                                                              controller=hdd["controller"],
                                                                                                                              port=hdd["port"],
                                                                                                                              device=hdd["device"],
                                                                                                                              error=e))
                    continue

            log.info("VirtualBox VM '{name}' [{id}] unregistering".format(name=self.name, id=self.id))
            yield from self.manager.execute("unregistervm", [self._name])

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
            log.info("VirtualBox VM '{name}' [{id}] has enabled the headless mode".format(name=self.name, id=self.id))
        else:
            log.info("VirtualBox VM '{name}' [{id}] has disabled the headless mode".format(name=self.name, id=self.id))
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
            log.info("VirtualBox VM '{name}' [{id}] has enabled the ACPI shutdown mode".format(name=self.name, id=self.id))
        else:
            log.info("VirtualBox VM '{name}' [{id}] has disabled the ACPI shutdown mode".format(name=self.name, id=self.id))
        self._acpi_shutdown = acpi_shutdown

    @property
    def ram(self):
        """
        Returns the amount of RAM allocated to this VirtualBox VM.

        :returns: amount RAM in MB (integer)
        """

        return self._ram

    @asyncio.coroutine
    def set_ram(self, ram):
        """
        Set the amount of RAM allocated to this VirtualBox VM.

        :param ram: amount RAM in MB (integer)
        """

        if ram == 0:
            return

        yield from self._modify_vm('--memory {}'.format(ram))

        log.info("VirtualBox VM '{name}' [{id}] has set amount of RAM to {ram}".format(name=self.name, id=self.id, ram=ram))
        self._ram = ram

    @property
    def vmname(self):
        """
        Returns the VirtualBox VM name.

        :returns: VirtualBox VM name
        """

        return self._vmname

    @asyncio.coroutine
    def set_vmname(self, vmname):
        """
        Renames the VirtualBox VM.

        :param vmname: VirtualBox VM name
        """

        if vmname == self._vmname:
            return

        if self.linked_clone:
            if self.status == "started":
                raise VirtualBoxError("You can't change the name of running VM {}".format(self._name))
            # We can't rename a VM to name that already exists
            vms = yield from self.manager.list_vms(allow_clone=True)
            if vmname in [vm["vmname"] for vm in vms]:
                raise VirtualBoxError("You can't change the name to {} it's already use in VirtualBox".format(vmname))
            yield from self._modify_vm('--name "{}"'.format(vmname))

        log.info("VirtualBox VM '{name}' [{id}] has set the VM name to '{vmname}'".format(name=self.name, id=self.id, vmname=vmname))
        self._vmname = vmname

    @property
    def adapters(self):
        """
        Returns the number of adapters configured for this VirtualBox VM.

        :returns: number of adapters
        """

        return self._adapters

    @asyncio.coroutine
    def set_adapters(self, adapters):
        """
        Sets the number of Ethernet adapters for this VirtualBox VM instance.

        :param adapters: number of adapters
        """

        # check for the maximum adapters supported by the VM
        self._maximum_adapters = yield from self._get_maximum_supported_adapters()
        if adapters > self._maximum_adapters:
            raise VirtualBoxError("Number of adapters above the maximum supported of {}".format(self._maximum_adapters))

        self._ethernet_adapters.clear()
        for adapter_number in range(0, adapters):
            self._ethernet_adapters[adapter_number] = EthernetAdapter()

        self._adapters = len(self._ethernet_adapters)
        log.info("VirtualBox VM '{name}' [{id}] has changed the number of Ethernet adapters to {adapters}".format(name=self.name,
                                                                                                                  id=self.id,
                                                                                                                  adapters=adapters))

    @property
    def use_any_adapter(self):
        """
        Returns either GNS3 can use any VirtualBox adapter on this instance.

        :returns: boolean
        """

        return self._use_any_adapter

    @use_any_adapter.setter
    def use_any_adapter(self, use_any_adapter):
        """
        Allows GNS3 to use any VirtualBox adapter on this instance.

        :param use_any_adapter: boolean
        """

        if use_any_adapter:
            log.info("VirtualBox VM '{name}' [{id}] is allowed to use any adapter".format(name=self.name, id=self.id))
        else:
            log.info("VirtualBox VM '{name}' [{id}] is not allowed to use any adapter".format(name=self.name, id=self.id))
        self._use_any_adapter = use_any_adapter

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
        log.info("VirtualBox VM '{name}' [{id}]: adapter type changed to {adapter_type}".format(name=self.name,
                                                                                                id=self.id,
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
        maximum_adapters = 8
        if "chipset" in vm_info:
            chipset = vm_info["chipset"]
            if chipset == "ich9":
                maximum_adapters = int(self._system_properties["Maximum ICH9 Network Adapter count"])
        return maximum_adapters

    def _get_pipe_name(self):
        """
        Returns the pipe name to create a serial connection.

        :returns: pipe path (string)
        """

        if sys.platform.startswith("win"):
            pipe_name = r"\\.\pipe\gns3_vbox\{}".format(self.id)
        else:
            pipe_name = os.path.join(tempfile.gettempdir(), "gns3_vbox", "{}".format(self.id))
            try:
                os.makedirs(os.path.dirname(pipe_name), exist_ok=True)
            except OSError as e:
                raise VirtualBoxError("Could not create the VirtualBox pipe directory: {}".format(e))
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
        for adapter_number in range(0, maximum_adapters):
            entry = "nic{}".format(adapter_number + 1)
            if entry in vm_info:
                value = vm_info[entry]
                nics.append(value.lower())
            else:
                nics.append(None)
        return nics

    @asyncio.coroutine
    def _set_network_options(self):
        """
        Configures network options.
        """

        nic_attachments = yield from self._get_nic_attachements(self._maximum_adapters)
        for adapter_number in range(0, self._adapters):
            attachment = nic_attachments[adapter_number]
            if attachment == "null":
                # disconnect the cable if no backend is attached.
                yield from self._modify_vm("--cableconnected{} off".format(adapter_number + 1))
            if attachment == "none":
                # set the backend to null to avoid a difference in the number of interfaces in the Guest.
                yield from self._modify_vm("--nic{} null".format(adapter_number + 1))
                yield from self._modify_vm("--cableconnected{} off".format(adapter_number + 1))

            if self.use_ubridge:
                # use a local UDP tunnel to connect to uBridge instead
                if adapter_number not in self._local_udp_tunnels:
                    self._local_udp_tunnels[adapter_number] = self._create_local_udp_tunnel()
                nio = self._local_udp_tunnels[adapter_number][0]
            else:
                nio = self._ethernet_adapters[adapter_number].get_nio(0)

            if nio:
                if not self._use_any_adapter and attachment not in ("none", "null", "generic"):
                    raise VirtualBoxError("Attachment ({}) already configured on adapter {}. "
                                          "Please set it to 'Not attached' to allow GNS3 to use it.".format(attachment,
                                                                                                            adapter_number + 1))

                yield from self._modify_vm("--nictrace{} off".format(adapter_number + 1))
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
                args = [self._vmname, "--nictype{}".format(adapter_number + 1), vbox_adapter_type]
                yield from self.manager.execute("modifyvm", args)

                if isinstance(nio, NIOUDP):
                    log.debug("setting UDP params on adapter {}".format(adapter_number))
                    yield from self._modify_vm("--nic{} generic".format(adapter_number + 1))
                    yield from self._modify_vm("--nicgenericdrv{} UDPTunnel".format(adapter_number + 1))
                    yield from self._modify_vm("--nicproperty{} sport={}".format(adapter_number + 1, nio.lport))
                    yield from self._modify_vm("--nicproperty{} dest={}".format(adapter_number + 1, nio.rhost))
                    yield from self._modify_vm("--nicproperty{} dport={}".format(adapter_number + 1, nio.rport))
                    yield from self._modify_vm("--cableconnected{} on".format(adapter_number + 1))

                if nio.capturing:
                    yield from self._modify_vm("--nictrace{} on".format(adapter_number + 1))
                    yield from self._modify_vm('--nictracefile{} "{}"'.format(adapter_number + 1, nio.pcap_output_file))

                if self.use_ubridge and not self._ethernet_adapters[adapter_number].get_nio(0):
                    yield from self._modify_vm("--cableconnected{} off".format(adapter_number + 1))

        for adapter_number in range(self._adapters, self._maximum_adapters):
            log.debug("disabling remaining adapter {}".format(adapter_number))
            yield from self._modify_vm("--nic{} none".format(adapter_number + 1))

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
        log.debug("VirtualBox VM: {} cloned".format(result))

        self._vmname = self._name
        yield from self.manager.execute("setextradata", [self._vmname, "GNS3/Clone", "yes"])

        # We create a reset snapshot in order to simplify life of user who want to rollback their VM
        # Warning: Do not document this it's seem buggy we keep it because Raizo students use it.
        try:
            args = [self._vmname, "take", "reset"]
            result = yield from self.manager.execute("snapshot", args)
            log.debug("Snapshot 'reset' created: {}".format(result))
        # It seem sometimes this failed due to internal race condition of Vbox
        # we have no real explanation of this.
        except VirtualBoxError:
            log.warn("Snapshot 'reset' not created")

        os.makedirs(os.path.join(self.working_dir, self._vmname), exist_ok=True)

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
    def adapter_add_nio_binding(self, adapter_number, nio):
        """
        Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except KeyError:
            raise VirtualBoxError("Adapter {adapter_number} doesn't exist on VirtualBox VM '{name}'".format(name=self.name,
                                                                                                            adapter_number=adapter_number))

        if self.ubridge:
            try:
                yield from self._add_ubridge_udp_connection("VBOX-{}-{}".format(self._id, adapter_number),
                                                            self._local_udp_tunnels[adapter_number][1],
                                                            nio)
            except KeyError:
                raise VirtualBoxError("Adapter {adapter_number} doesn't exist on VirtualBox VM '{name}'".format(name=self.name,
                                                                                                                adapter_number=adapter_number))
            yield from self._control_vm("setlinkstate{} on".format(adapter_number + 1))
        else:
            vm_state = yield from self._get_vm_state()
            if vm_state == "running":
                if isinstance(nio, NIOUDP):
                    # dynamically configure an UDP tunnel on the VirtualBox adapter
                    yield from self._control_vm("nic{} generic UDPTunnel".format(adapter_number + 1))
                    yield from self._control_vm("nicproperty{} sport={}".format(adapter_number + 1, nio.lport))
                    yield from self._control_vm("nicproperty{} dest={}".format(adapter_number + 1, nio.rhost))
                    yield from self._control_vm("nicproperty{} dport={}".format(adapter_number + 1, nio.rport))
                    yield from self._control_vm("setlinkstate{} on".format(adapter_number + 1))

                    # check if the UDP tunnel has been correctly set
                    vm_info = yield from self._get_vm_info()
                    generic_driver_number = "generic{}".format(adapter_number + 1)
                    if generic_driver_number not in vm_info and vm_info[generic_driver_number] != "UDPTunnel":
                        log.warning("UDP tunnel has not been set on nic: {}".format(adapter_number + 1))
                        self.project.emit("log.warning", {"message": "UDP tunnel has not been set on nic: {}".format(adapter_number + 1)})

        adapter.add_nio(0, nio)
        log.info("VirtualBox VM '{name}' [{id}]: {nio} added to adapter {adapter_number}".format(name=self.name,
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
        except KeyError:
            raise VirtualBoxError("Adapter {adapter_number} doesn't exist on VirtualBox VM '{name}'".format(name=self.name,
                                                                                                            adapter_number=adapter_number))

        if self.ubridge:
            yield from self._ubridge_send("bridge delete {name}".format(name="VBOX-{}-{}".format(self._id, adapter_number)))
            vm_state = yield from self._get_vm_state()
            if vm_state == "running":
                yield from self._control_vm("setlinkstate{} off".format(adapter_number + 1))
        else:
            vm_state = yield from self._get_vm_state()
            if vm_state == "running":
                # dynamically disable the VirtualBox adapter
                yield from self._control_vm("setlinkstate{} off".format(adapter_number + 1))
                yield from self._control_vm("nic{} null".format(adapter_number + 1))

        nio = adapter.get_nio(0)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        adapter.remove_nio(0)

        log.info("VirtualBox VM '{name}' [{id}]: {nio} removed from adapter {adapter_number}".format(name=self.name,
                                                                                                     id=self.id,
                                                                                                     nio=nio,
                                                                                                     adapter_number=adapter_number))
        return nio

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
            raise VirtualBoxError("Adapter {adapter_number} doesn't exist on VirtualBox VM '{name}'".format(name=self.name,
                                                                                                            adapter_number=adapter_number))

        if not self.use_ubridge:
            vm_state = yield from self._get_vm_state()
            if vm_state == "running" or vm_state == "paused" or vm_state == "stuck":
                raise VirtualBoxError("Sorry, packet capturing on a started VirtualBox VM is not supported without using uBridge")

        nio = adapter.get_nio(0)

        if not nio:
            raise VirtualBoxError("Adapter {} is not connected".format(adapter_number))

        if nio.capturing:
            raise VirtualBoxError("Packet capture is already activated on adapter {adapter_number}".format(adapter_number=adapter_number))

        nio.startPacketCapture(output_file)

        if self.ubridge:
            yield from self._ubridge_send('bridge start_capture {name} "{output_file}"'.format(name="VBOX-{}-{}".format(self._id, adapter_number),
                                                                                               output_file=output_file))

        log.info("VirtualBox VM '{name}' [{id}]: starting packet capture on adapter {adapter_number}".format(name=self.name,
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
            raise VirtualBoxError("Adapter {adapter_number} doesn't exist on VirtualBox VM '{name}'".format(name=self.name,
                                                                                                            adapter_number=adapter_number))

        nio = adapter.get_nio(0)

        if not nio:
            raise VirtualBoxError("Adapter {} is not connected".format(adapter_number))

        nio.stopPacketCapture()

        if self.ubridge:
            yield from self._ubridge_send('bridge stop_capture {name}'.format(name="VBOX-{}-{}".format(self._id, adapter_number)))

        log.info("VirtualBox VM '{name}' [{id}]: stopping packet capture on adapter {adapter_number}".format(name=self.name,
                                                                                                             id=self.id,
                                                                                                             adapter_number=adapter_number))
