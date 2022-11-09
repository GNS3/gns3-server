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
import platform

from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer
from gns3server.utils.asyncio.serial import asyncio_open_serial
from gns3server.utils import parse_version
from gns3server.utils.asyncio import locking
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

    def __init__(
        self, name, node_id, project, manager, vmx_path, linked_clone=False, console=None, console_type="telnet"
    ):

        super().__init__(
            name, node_id, project, manager, console=console, console_type=console_type, linked_clone=linked_clone
        )

        self._vmx_pairs = OrderedDict()
        self._telnet_server = None
        self._vmnets = []
        self._maximum_adapters = 10
        self._started = False
        self._closed = False

        # VMware VM settings
        self._headless = False
        self._vmx_path = vmx_path
        self._on_close = "power_off"
        self._adapters = 0
        self._ethernet_adapters = {}
        self._adapter_type = "e1000"
        self._use_any_adapter = False

        if not os.path.exists(vmx_path):
            raise VMwareError(f'VMware VM "{name}" [{node_id}]: could not find VMX file "{vmx_path}"')

    @property
    def ethernet_adapters(self):
        return self._ethernet_adapters

    def asdict(self):

        json = {
            "name": self.name,
            "usage": self.usage,
            "node_id": self.id,
            "console": self.console,
            "console_type": self.console_type,
            "project_id": self.project.id,
            "vmx_path": self.vmx_path,
            "headless": self.headless,
            "on_close": self.on_close,
            "adapters": self._adapters,
            "adapter_type": self.adapter_type,
            "use_any_adapter": self.use_any_adapter,
            "status": self.status,
            "node_directory": self.working_path,
            "linked_clone": self.linked_clone,
        }
        return json

    @property
    def vmnets(self):

        return self._vmnets

    @locking
    async def _control_vm(self, subcommand, *additional_args):

        args = [self._vmx_path]
        args.extend(additional_args)
        result = await self.manager.execute(subcommand, args)
        log.debug(f"Control VM '{subcommand}' result: {result}")
        return result

    def _read_vmx_file(self):
        """
        Reads from the VMware VMX file corresponding to this VM.
        """

        try:
            self._vmx_pairs = self.manager.parse_vmware_file(self._vmx_path)
        except OSError as e:
            raise VMwareError(f'Could not read VMware VMX file "{self._vmx_path}": {e}')

    def _write_vmx_file(self):
        """
        Writes pairs to the VMware VMX file corresponding to this VM.
        """

        try:
            self.manager.write_vmx_file(self._vmx_path, self._vmx_pairs)
        except OSError as e:
            raise VMwareError(f'Could not write VMware VMX file "{self._vmx_path}": {e}')

    async def is_running(self):

        result = await self.manager.execute("list", [])
        if self._vmx_path in result:
            return True
        return False

    async def _check_duplicate_linked_clone(self):
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
                            raise VMwareError(
                                f"Sorry a node without the linked clone setting enabled can only be used once on your server.\n{self.vmx_path} is already used by {node.name} in project {self.project.name}"
                            )
                    else:
                        if trial >= 5:
                            raise VMwareError(
                                f"Sorry a node without the linked clone setting enabled can only be used once on your server.\n{self.vmx_path} is already used by {node.name} in this project"
                            )
            if not found:
                return
            trial += 1
            await asyncio.sleep(1)

    async def create(self):
        """
        Creates this VM and handle linked clones.
        """
        if not self.linked_clone:
            await self._check_duplicate_linked_clone()

        await self.manager.check_vmrun_version()
        if self.linked_clone and not os.path.exists(os.path.join(self.working_dir, os.path.basename(self._vmx_path))):
            if self.manager.host_type == "player":
                raise VMwareError("Linked clones are not supported by VMware Player")
            # create the base snapshot for linked clones
            base_snapshot_name = "GNS3 Linked Base for clones"
            vmsd_path = os.path.splitext(self._vmx_path)[0] + ".vmsd"
            if not os.path.exists(vmsd_path):
                raise VMwareError(f"{vmsd_path} doesn't not exist")
            try:
                vmsd_pairs = self.manager.parse_vmware_file(vmsd_path)
            except OSError as e:
                raise VMwareError(f'Could not read VMware VMSD file "{vmsd_path}": {e}')
            gns3_snapshot_exists = False
            for value in vmsd_pairs.values():
                if value == base_snapshot_name:
                    gns3_snapshot_exists = True
                    break
            if not gns3_snapshot_exists:
                log.info(f"Creating snapshot '{base_snapshot_name}'")
                await self._control_vm("snapshot", base_snapshot_name)

            # create the linked clone based on the base snapshot
            new_vmx_path = os.path.join(self.working_dir, self.name + ".vmx")
            await self._control_vm(
                "clone", new_vmx_path, "linked", f"-snapshot={base_snapshot_name}", f"-cloneName={self.name}"
            )

            try:
                vmsd_pairs = self.manager.parse_vmware_file(vmsd_path)
            except OSError as e:
                raise VMwareError(f'Could not read VMware VMSD file "{vmsd_path}": {e}')

            snapshot_name = None
            for name, value in vmsd_pairs.items():
                if value == base_snapshot_name:
                    snapshot_name = name.split(".", 1)[0]
                    break

            if snapshot_name is None:
                raise VMwareError(f"Could not find the linked base snapshot in {vmsd_path}")

            num_clones_entry = f"{snapshot_name}.numClones"
            if num_clones_entry in vmsd_pairs:
                try:
                    nb_of_clones = int(vmsd_pairs[num_clones_entry])
                except ValueError:
                    raise VMwareError(f"Value of {num_clones_entry} in {vmsd_path} is not a number")
                vmsd_pairs[num_clones_entry] = str(nb_of_clones - 1)

                for clone_nb in range(0, nb_of_clones):
                    clone_entry = f"{snapshot_name}.clone{clone_nb}"
                    if clone_entry in vmsd_pairs:
                        del vmsd_pairs[clone_entry]

                try:
                    self.manager.write_vmware_file(vmsd_path, vmsd_pairs)
                except OSError as e:
                    raise VMwareError(f'Could not write VMware VMSD file "{vmsd_path}": {e}')

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
            connected = f"ethernet{adapter_number}.startConnected"
            if self._get_vmx_setting(connected):
                del self._vmx_pairs[connected]

        use_ubridge = True
        # use alternative method to find vmnet interfaces on macOS >= 11.0 (BigSur)
        # because "bridge" interfaces are used instead and they are only created on the VM starts
        if sys.platform.startswith("darwin") and parse_version(platform.mac_ver()[0]) >= parse_version("11.0.0"):
            use_ubridge = False
        self.manager.refresh_vmnet_list(ubridge=use_ubridge)
        # then configure VMware network adapters
        for adapter_number in range(0, self._adapters):

            custom_adapter = self._get_custom_adapter_settings(adapter_number)
            adapter_type = custom_adapter.get("adapter_type", self._adapter_type)

            # add/update the interface
            if adapter_type == "default":
                # force default to e1000 because some guest OS don't detect the adapter (i.e. Windows 2012 server)
                # when 'virtualdev' is not set in the VMX file.
                vmware_adapter_type = "e1000"
            else:
                vmware_adapter_type = adapter_type
            ethernet_adapter = {
                f"ethernet{adapter_number}.present": "TRUE",
                f"ethernet{adapter_number}.addresstype": "generated",
                f"ethernet{adapter_number}.generatedaddressoffset": "0",
                f"ethernet{adapter_number}.virtualdev": vmware_adapter_type,
            }
            self._vmx_pairs.update(ethernet_adapter)

            connection_type = f"ethernet{adapter_number}.connectiontype"
            if (
                not self._use_any_adapter
                and connection_type in self._vmx_pairs
                and self._vmx_pairs[connection_type] in ("nat", "bridged", "hostonly")
            ):
                continue

            self._vmx_pairs[f"ethernet{adapter_number}.connectiontype"] = "custom"

            # make sure we have a vmnet per adapter if we use uBridge
            allocate_vmnet = False

            # first check if a vmnet is already assigned to the adapter
            vnet = f"ethernet{adapter_number}.vnet"
            if vnet in self._vmx_pairs:
                vmnet = os.path.basename(self._vmx_pairs[vnet])
                if self.manager.is_managed_vmnet(vmnet) or vmnet in ("vmnet0", "vmnet1", "vmnet8"):
                    # vmnet already managed or a special vmnet, try to allocate a new one
                    allocate_vmnet = True
            else:
                # otherwise allocate a new one
                allocate_vmnet = True

            if allocate_vmnet:
                try:
                    vmnet = self.manager.allocate_vmnet()
                except BaseException:
                    # clear everything up in case of error (e.g. no enough vmnets)
                    self._vmnets.clear()
                    raise

            # mark the vmnet as managed by us
            if vmnet not in self._vmnets:
                self._vmnets.append(vmnet)
            self._vmx_pairs[f"ethernet{adapter_number}.vnet"] = vmnet

        # disable remaining network adapters
        for adapter_number in range(self._adapters, self._maximum_adapters):
            if self._get_vmx_setting(f"ethernet{adapter_number}.present", "TRUE"):
                log.debug(f"disabling remaining adapter {adapter_number}")
                self._vmx_pairs[f"ethernet{adapter_number}.startconnected"] = "FALSE"

    def _get_vnet(self, adapter_number):
        """
        Return the vnet will use in ubridge
        """
        vnet = f"ethernet{adapter_number}.vnet"
        if vnet not in self._vmx_pairs:
            raise VMwareError(f"vnet {vnet} not in VMX file")
        return vnet

    async def _add_ubridge_connection(self, nio, adapter_number):
        """
        Creates a connection in uBridge.

        :param nio: NIO instance
        :param adapter_number: adapter number
        """

        vnet = self._get_vnet(adapter_number)
        await self._ubridge_send(f"bridge create {vnet}")
        vmnet_interface = os.path.basename(self._vmx_pairs[vnet])

        if sys.platform.startswith("darwin"):
            if parse_version(platform.mac_ver()[0]) >= parse_version("11.0.0"):
                # a bridge interface (bridge100, bridge101 etc.) is used instead of a vmnet interface
                # on macOS >= 11.0 (Big Sur)
                vmnet_interface = self.manager.find_bridge_interface(vmnet_interface)
                if not vmnet_interface:
                    raise VMwareError(f"Could not find bridge interface linked with {vmnet_interface}")
                block_host_traffic = self.manager.config.get_section_config("VMware").getboolean("block_host_traffic", False)
                await self._add_ubridge_ethernet_connection(vnet, vmnet_interface, block_host_traffic)
            else:
                # special case on macOS, we cannot bind VMnet interfaces using the libpcap
                await self._ubridge_send('bridge add_nio_fusion_vmnet {name} "{interface}"'.format(name=vnet, interface=vmnet_interface))
        else:
            block_host_traffic = self.manager.config.VMware.block_host_traffic
            await self._add_ubridge_ethernet_connection(vnet, vmnet_interface, block_host_traffic)

        if isinstance(nio, NIOUDP):
            await self._ubridge_send(
                "bridge add_nio_udp {name} {lport} {rhost} {rport}".format(
                    name=vnet, lport=nio.lport, rhost=nio.rhost, rport=nio.rport
                )
            )

        if nio.capturing:
            await self._ubridge_send(f'bridge start_capture {vnet} "{nio.pcap_output_file}"')

        await self._ubridge_send(f"bridge start {vnet}")
        await self._ubridge_apply_filters(vnet, nio.filters)

    async def _update_ubridge_connection(self, adapter_number, nio):
        """
        Update a connection in uBridge.

        :param nio: NIO instance
        :param adapter_number: adapter number
        """
        try:
            bridge_name = self._get_vnet(adapter_number)
        except VMwareError:
            return  # vnet not yet available
        await self._ubridge_apply_filters(bridge_name, nio.filters)

    async def _delete_ubridge_connection(self, adapter_number):
        """
        Deletes a connection in uBridge.

        :param adapter_number: adapter number
        """

        vnet = f"ethernet{adapter_number}.vnet"
        if vnet not in self._vmx_pairs:
            raise VMwareError(f"vnet {vnet} not in VMX file")
        await self._ubridge_send(f"bridge delete {vnet}")

    async def _start_ubridge_capture(self, adapter_number, output_file):
        """
        Start a packet capture in uBridge.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        vnet = f"ethernet{adapter_number}.vnet"
        if vnet not in self._vmx_pairs:
            raise VMwareError(f"vnet {vnet} not in VMX file")
        if not self._ubridge_hypervisor:
            raise VMwareError("Cannot start the packet capture: uBridge is not running")
        await self._ubridge_send(
            'bridge start_capture {name} "{output_file}"'.format(name=vnet, output_file=output_file)
        )

    async def _stop_ubridge_capture(self, adapter_number):
        """
        Stop a packet capture in uBridge.

        :param adapter_number: adapter number
        """

        vnet = f"ethernet{adapter_number}.vnet"
        if vnet not in self._vmx_pairs:
            raise VMwareError(f"vnet {vnet} not in VMX file")
        if not self._ubridge_hypervisor:
            raise VMwareError("Cannot stop the packet capture: uBridge is not running")
        await self._ubridge_send(f"bridge stop_capture {vnet}")

    def check_hw_virtualization(self):
        """
        Returns either hardware virtualization is activated or not.

        :returns: boolean
        """

        self._read_vmx_file()
        if self._get_vmx_setting("vhv.enable", "TRUE"):
            return True
        return False

    async def start(self):
        """
        Starts this VMware VM.
        """

        if self.status == "started":
            return

        if await self.is_running():
            raise VMwareError("The VM is already running in VMware")

        ubridge_path = self.ubridge_path
        if not ubridge_path or not os.path.isfile(ubridge_path):
            raise VMwareError("ubridge is necessary to start a VMware VM")

        await self._start_ubridge(require_privileged_access=True)
        self._read_vmx_file()
        # check if there is enough RAM to run
        if "memsize" in self._vmx_pairs:
            self.check_available_ram(int(self._vmx_pairs["memsize"]))
        self._set_network_options()
        self._set_serial_console()
        self._write_vmx_file()

        if self._headless:
            await self._control_vm("start", "nogui")
        else:
            await self._control_vm("start")

        try:
            if self._ubridge_hypervisor:
                if parse_version(platform.mac_ver()[0]) >= parse_version("11.0.0"):
                    # give VMware some time to create the bridge interfaces, so they can be found
                    # by psutil and used by uBridge
                    await asyncio.sleep(1)
                for adapter_number in range(0, self._adapters):
                    nio = self._ethernet_adapters[adapter_number].get_nio(0)
                    if nio:
                        await self._add_ubridge_connection(nio, adapter_number)

            await self._start_console()
        except VMwareError:
            await self.stop()
            raise

        if self._get_vmx_setting("vhv.enable", "TRUE"):
            self._hw_virtualization = True

        self._started = True
        self.status = "started"
        log.info(f"VMware VM '{self.name}' [{self.id}] started")

    async def stop(self):
        """
        Stops this VMware VM.
        """

        self._hw_virtualization = False
        await self._stop_remote_console()
        await self._stop_ubridge()

        try:
            if await self.is_running():
                if self.on_close == "save_vm_state":
                    await self._control_vm("suspend")
                elif self.on_close == "shutdown_signal":
                    # use ACPI to shutdown the VM
                    await self._control_vm("stop", "soft")
                else:
                    await self._control_vm("stop")
        finally:
            self._started = False
            self.status = "stopped"

            self._read_vmx_file()
            self._vmnets.clear()
            # remove the adapters managed by GNS3
            for adapter_number in range(0, self._adapters):
                vnet = f"ethernet{adapter_number}.vnet"
                if (
                    self._get_vmx_setting(vnet)
                    or self._get_vmx_setting(f"ethernet{adapter_number}.connectiontype") is None
                ):
                    if vnet in self._vmx_pairs:
                        vmnet = os.path.basename(self._vmx_pairs[vnet])
                        if not self.manager.is_managed_vmnet(vmnet):
                            continue
                    log.debug(f"removing adapter {adapter_number}")
                    self._vmx_pairs[vnet] = "vmnet1"
                    self._vmx_pairs[f"ethernet{adapter_number}.connectiontype"] = "custom"

            # re-enable any remaining network adapters
            for adapter_number in range(self._adapters, self._maximum_adapters):
                if self._get_vmx_setting(f"ethernet{adapter_number}.present", "TRUE"):
                    log.debug(f"enabling remaining adapter {adapter_number}")
                    self._vmx_pairs[f"ethernet{adapter_number}.startconnected"] = "TRUE"
            self._write_vmx_file()

        await super().stop()
        log.info(f"VMware VM '{self.name}' [{self.id}] stopped")

    async def suspend(self):
        """
        Suspends this VMware VM.
        """

        if self.manager.host_type != "ws":
            raise VMwareError("Pausing a VM is only supported by VMware Workstation")
        await self._control_vm("pause")
        self.status = "suspended"
        log.info(f"VMware VM '{self.name}' [{self.id}] paused")

    async def resume(self):
        """
        Resumes this VMware VM.
        """

        if self.manager.host_type != "ws":
            raise VMwareError("Unpausing a VM is only supported by VMware Workstation")
        await self._control_vm("unpause")
        self.status = "started"
        log.info(f"VMware VM '{self.name}' [{self.id}] resumed")

    async def reload(self):
        """
        Reloads this VMware VM.
        """

        await self._control_vm("reset")
        log.info(f"VMware VM '{self.name}' [{self.id}] reloaded")

    async def close(self):
        """
        Closes this VMware VM.
        """

        if not (await super().close()):
            return False

        for adapter in self._ethernet_adapters.values():
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(nio.lport, self._project)
        try:
            self.on_close = "power_off"
            await self.stop()
        except VMwareError:
            pass

        if self.linked_clone:
            await self.manager.remove_from_vmware_inventory(self._vmx_path)

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
            log.info(f"VMware VM '{self.name}' [{self.id}] has enabled the headless mode")
        else:
            log.info(f"VMware VM '{self.name}' [{self.id}] has disabled the headless mode")
        self._headless = headless

    @property
    def on_close(self):
        """
        Returns the action to execute when the VM is stopped/closed

        :returns: string
        """

        return self._on_close

    @on_close.setter
    def on_close(self, on_close):
        """
        Sets the action to execute when the VM is stopped/closed

        :param on_close: string
        """

        log.info(f'VMware VM "{self._name}" [{self._id}] set the close action to "{on_close}"')
        self._on_close = on_close

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

        log.info(f"VMware VM '{self.name}' [{self.id}] has set the vmx file path to '{vmx_path}'")
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
        log.info(
            "VMware VM '{name}' [{id}] has changed the number of Ethernet adapters to {adapters}".format(
                name=self.name, id=self.id, adapters=adapters
            )
        )

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
        log.info(
            "VMware VM '{name}' [{id}]: adapter type changed to {adapter_type}".format(
                name=self.name, id=self.id, adapter_type=adapter_type
            )
        )

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
            log.info(f"VMware VM '{self.name}' [{self.id}] is allowed to use any adapter")
        else:
            log.info(f"VMware VM '{self.name}' [{self.id}] is not allowed to use any adapter")
        self._use_any_adapter = use_any_adapter

    async def adapter_add_nio_binding(self, adapter_number, nio):
        """
        Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise VMwareError(
                "Adapter {adapter_number} doesn't exist on VMware VM '{name}'".format(
                    name=self.name, adapter_number=adapter_number
                )
            )

        self._read_vmx_file()
        # check if trying to connect to a nat, bridged or host-only adapter
        if self._get_vmx_setting(f"ethernet{adapter_number}.present", "TRUE"):
            # check for the connection type
            connection_type = f"ethernet{adapter_number}.connectiontype"
            if (
                not self._use_any_adapter
                and connection_type in self._vmx_pairs
                and self._vmx_pairs[connection_type] in ("nat", "bridged", "hostonly")
            ):
                if await self.is_running():
                    raise VMwareError(
                        "Attachment '{attachment}' is configured on network adapter {adapter_number}. "
                        "Please stop VMware VM '{name}' to link to this adapter and allow GNS3 to change the attachment type.".format(
                            attachment=self._vmx_pairs[connection_type], adapter_number=adapter_number, name=self.name
                        )
                    )
                else:
                    raise VMwareError(
                        "Attachment '{attachment}' is already configured on network adapter {adapter_number}. "
                        "Please remove it or allow VMware VM '{name}' to use any adapter.".format(
                            attachment=self._vmx_pairs[connection_type], adapter_number=adapter_number, name=self.name
                        )
                    )

        adapter.add_nio(0, nio)
        if self._started and self._ubridge_hypervisor:
            await self._add_ubridge_connection(nio, adapter_number)

        log.info(
            "VMware VM '{name}' [{id}]: {nio} added to adapter {adapter_number}".format(
                name=self.name, id=self.id, nio=nio, adapter_number=adapter_number
            )
        )

    async def adapter_update_nio_binding(self, adapter_number, nio):
        """
        Updates an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to update on the adapter
        """

        if self._ubridge_hypervisor:
            try:
                await self._update_ubridge_connection(adapter_number, nio)
            except IndexError:
                raise VMwareError(
                    'Adapter {adapter_number} does not exist on VMware VM "{name}"'.format(
                        name=self._name, adapter_number=adapter_number
                    )
                )

    async def adapter_remove_nio_binding(self, adapter_number):
        """
        Removes an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise VMwareError(
                "Adapter {adapter_number} doesn't exist on VMware VM '{name}'".format(
                    name=self.name, adapter_number=adapter_number
                )
            )

        await self.stop_capture(adapter_number)
        nio = adapter.get_nio(0)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        adapter.remove_nio(0)
        if self._started and self._ubridge_hypervisor:
            await self._delete_ubridge_connection(adapter_number)

        log.info(
            "VMware VM '{name}' [{id}]: {nio} removed from adapter {adapter_number}".format(
                name=self.name, id=self.id, nio=nio, adapter_number=adapter_number
            )
        )

        return nio

    def get_nio(self, adapter_number):
        """
        Gets an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """

        try:
            adapter = self.ethernet_adapters[adapter_number]
        except KeyError:
            raise VMwareError(
                "Adapter {adapter_number} doesn't exist on VMware VM '{name}'".format(
                    name=self.name, adapter_number=adapter_number
                )
            )

        nio = adapter.get_nio(0)
        if not nio:
            raise VMwareError(f"Adapter {adapter_number} is not connected")

        return nio

    def _get_pipe_name(self):
        """
        Returns the pipe name to create a serial connection.

        :returns: pipe path (string)
        """

        pipe_name = os.path.join(tempfile.gettempdir(), "gns3_vmware", f"{self.id}")
        try:
            os.makedirs(os.path.dirname(pipe_name), exist_ok=True)
        except OSError as e:
            raise VMwareError(f"Could not create the VMware pipe directory: {e}")
        return pipe_name

    def _set_serial_console(self):
        """
        Configures the first serial port to allow a serial console connection.
        """

        pipe_name = self._get_pipe_name()
        serial_port = {
            "serial0.present": "TRUE",
            "serial0.filetype": "pipe",
            "serial0.filename": pipe_name,
            "serial0.pipe.endpoint": "server",
            "serial0.startconnected": "TRUE",
        }
        self._vmx_pairs.update(serial_port)

    async def _start_console(self):
        """
        Starts remote console support for this VM.
        """

        if self.console and self.console_type == "telnet":
            pipe_name = self._get_pipe_name()
            try:
                self._remote_pipe = await asyncio_open_serial(self._get_pipe_name())
            except OSError as e:
                raise VMwareError(f"Could not open serial pipe '{pipe_name}': {e}")
            server = AsyncioTelnetServer(reader=self._remote_pipe, writer=self._remote_pipe, binary=True, echo=True)
            try:
                self._telnet_server = await asyncio.start_server(
                    server.run, self._manager.port_manager.console_host, self.console
                )
            except OSError as e:
                self.project.emit(
                    "log.warning",
                    {
                        "message": f"Could not start Telnet server on socket {self._manager.port_manager.console_host}:{self.console}: {e}"
                    },
                )

    async def _stop_remote_console(self):
        """
        Stops remote console support for this VM.
        """
        if self._telnet_server:
            self._telnet_server.close()
            await self._telnet_server.wait_closed()
            self._remote_pipe.close()
            self._telnet_server = None

    async def reset_console(self):
        """
        Reset the console.
        """

        await self._stop_remote_console()
        await self._start_console()

    @BaseNode.console_type.setter
    def console_type(self, new_console_type):
        """
        Sets the console type for this VMware VM.

        :param new_console_type: console type (string)
        """

        if self._started and self.console_type != new_console_type:
            raise VMwareError(f'"{self._name}" must be stopped to change the console type to {new_console_type}')

        super(VMwareVM, VMwareVM).console_type.__set__(self, new_console_type)

    async def start_capture(self, adapter_number, output_file):
        """
        Starts a packet capture.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        nio = self.get_nio(adapter_number)
        if nio.capturing:
            raise VMwareError(f"Packet capture is already activated on adapter {adapter_number}")

        nio.start_packet_capture(output_file)
        if self._started:
            await self._start_ubridge_capture(adapter_number, output_file)

        log.info(
            "VMware VM '{name}' [{id}]: starting packet capture on adapter {adapter_number}".format(
                name=self.name, id=self.id, adapter_number=adapter_number
            )
        )

    async def stop_capture(self, adapter_number):
        """
        Stops a packet capture.

        :param adapter_number: adapter number
        """

        nio = self.get_nio(adapter_number)
        if not nio.capturing:
            return

        nio.stop_packet_capture()
        if self._started:
            await self._stop_ubridge_capture(adapter_number)

        log.info(
            "VMware VM '{name}' [{id}]: stopping packet capture on adapter {adapter_number}".format(
                name=self.name, id=self.id, adapter_number=adapter_number
            )
        )
