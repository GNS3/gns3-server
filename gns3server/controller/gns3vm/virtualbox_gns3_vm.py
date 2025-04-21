#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import re
import sys
import aiohttp
import logging
import asyncio
import socket
import ipaddress

from .base_gns3_vm import BaseGNS3VM
from .gns3_vm_error import GNS3VMError
from gns3server.utils import parse_version
from gns3server.utils.asyncio import wait_run_in_executor

from ...compute.virtualbox import (
    VirtualBox,
    VirtualBoxError
)

log = logging.getLogger(__name__)


class VirtualBoxGNS3VM(BaseGNS3VM):

    def __init__(self, controller):

        self._engine = "virtualbox"
        super().__init__(controller)
        self._system_properties = {}
        self._virtualbox_manager = VirtualBox()

    async def _execute(self, subcommand, args, timeout=60):

        try:
            result = await self._virtualbox_manager.execute(subcommand, args, timeout)
            return ("\n".join(result))
        except VirtualBoxError as e:
            raise GNS3VMError("Error while executing VBoxManage command: {}".format(e))

    async def _get_state(self):
        """
        Returns the VM state (e.g. running, paused etc.)

        :returns: state (string)
        """

        result = await self._execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in result.splitlines():
            if '=' in info:
                name, value = info.split('=', 1)
                if name == "VMState":
                    return value.strip('"')
        return "unknown"

    async def _get_system_properties(self):
        """
        Returns the VM state (e.g. running, paused etc.)

        :returns: state (string)
        """

        properties = await self._execute("list", ["systemproperties"])
        for prop in properties.splitlines():
            try:
                name, value = prop.split(':', 1)
            except ValueError:
                continue
            self._system_properties[name.strip()] = value.strip()

    async def _check_requirements(self):
        """
        Checks if the GNS3 VM can run on VirtualBox
        """

        if not self._system_properties:
            await self._get_system_properties()
        if "API version" not in self._system_properties:
            raise GNS3VMError("Can't access to VirtualBox API version:\n{}".format(self._system_properties))
        from cpuinfo import get_cpu_info
        cpu_info = await wait_run_in_executor(get_cpu_info)
        vendor_id = cpu_info.get('vendor_id_raw')
        if vendor_id == "GenuineIntel":
            if parse_version(self._system_properties["API version"]) < parse_version("6_1"):
                raise GNS3VMError("VirtualBox version 6.1 or above is required to run the GNS3 VM with nested virtualization enabled on Intel processors")
        elif vendor_id == "AuthenticAMD":
            if parse_version(self._system_properties["API version"]) < parse_version("6_0"):
                raise GNS3VMError("VirtualBox version 6.0 or above is required to run the GNS3 VM with nested virtualization enabled on AMD processors")
        else:
            log.warning("Could not determine CPU vendor: {}".format(vendor_id))

    async def _look_for_interface(self, network_backend):
        """
        Look for an interface with a specific network backend.

        :returns: interface number or -1 if none is found
        """

        result = await self._execute("showvminfo", [self._vmname, "--machinereadable"])
        interface = -1
        for info in result.splitlines():
            if '=' in info:
                name, value = info.split('=', 1)
                if name.startswith("nic") and value.strip('"') == network_backend:
                    try:
                        interface = int(name[3:])
                        break
                    except ValueError:
                        continue
        return interface

    async def _look_for_vboxnet(self, backend_type, interface_number):
        """
        Look for the VirtualBox network name associated with an interface.

        :returns: None or vboxnet name
        """

        result = await self._execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in result.splitlines():
            if '=' in info:
                name, value = info.split('=', 1)
                if name == "{}{}".format(backend_type, interface_number):
                    return value.strip('"')
        return None

    async def _check_dhcp_server(self, vboxnet):
        """
        Check if the DHCP server associated with a vboxnet is enabled.

        :param vboxnet: vboxnet name
        :returns: boolean
        """

        properties = await self._execute("list", ["dhcpservers"])
        flag_dhcp_server_found = False
        for prop in properties.splitlines():
            try:
                name, value = prop.split(':', 1)
            except ValueError:
                continue
            if name.strip() == "NetworkName" and value.strip().endswith(vboxnet):
                flag_dhcp_server_found = True
            if flag_dhcp_server_found and name.strip() == "Enabled":
                if value.strip() == "Yes":
                    return True
        return False

    async def _add_dhcp_server(self, vboxnet):
        """
        Add a DHCP server for vboxnet.

        :param vboxnet: vboxnet name
        """

        hostonlyifs = await self._execute("list", ["hostonlyifs"])
        pattern = r"IPAddress:\s+(\d+\.\d+\.\d+\.\d+)\nNetworkMask:\s+(\d+\.\d+\.\d+\.\d+)"
        match = re.search(pattern, hostonlyifs)

        if match:
            ip_address = match.group(1)
            netmask = match.group(2)
        else:
            raise GNS3VMError("Could not find IP address and netmask for vboxnet {}".format(vboxnet))

        try:
            interface = ipaddress.IPv4Interface(f"{ip_address}/{netmask}")
            subnet = ipaddress.IPv4Network(str(interface.network))
            dhcp_server_ip = str(interface.ip + 1)
            netmask = str(subnet.netmask)
            lower_ip = str(interface.ip + 2)
            upper_ip = str(subnet.network_address + subnet.num_addresses - 2)
        except ValueError:
            raise GNS3VMError("Invalid IP address and netmask for vboxnet {}: {}/{}".format(vboxnet, ip_address, netmask))

        dhcp_server_args = [
            "add",
            "--network=HostInterfaceNetworking-{}".format(vboxnet),
            "--server-ip={}".format(dhcp_server_ip),
            "--netmask={}".format(netmask),
            "--lower-ip={}".format(lower_ip),
            "--upper-ip={}".format(upper_ip),
            "--enable"
        ]
        await self._execute("dhcpserver", dhcp_server_args)

    async def _check_vboxnet_exists(self, vboxnet, vboxnet_type):
        """
        Check if the vboxnet interface exists

        :param vboxnet: vboxnet name
        :returns: boolean
        """

        properties = await self._execute("list", ["{}".format(vboxnet_type)])
        for prop in properties.splitlines():
            try:
                name, value = prop.split(':', 1)
            except ValueError:
                continue
            if name.strip() == "Name" and value.strip() == vboxnet:
                return True
        return False

    async def _find_first_available_vboxnet(self):
        """
        Find the first available vboxnet.
        """

        properties = await self._execute("list", ["hostonlyifs"])
        for prop in properties.splitlines():
            try:
                name, value = prop.split(':', 1)
            except ValueError:
                continue
            if name.strip() == "Name":
                return value.strip()
        return None

    async def _check_vbox_port_forwarding(self):
        """
        Checks if the NAT port forwarding rule exists.

        :returns: boolean
        """

        result = await self._execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in result.splitlines():
            if '=' in info:
                name, value = info.split('=', 1)
                if name.startswith("Forwarding") and value.strip('"').startswith("GNS3VM"):
                    return True
        return False


    async def list(self):
        """
        List all VirtualBox VMs
        """

        try:
            await self._check_requirements()
            return await self._virtualbox_manager.list_vms()
        except VirtualBoxError as e:
            raise GNS3VMError("Could not list VirtualBox VMs: {}".format(str(e)))

    async def start(self):
        """
        Start the GNS3 VM.
        """

        await self._check_requirements()

        # get a NAT interface number
        nat_interface_number = await self._look_for_interface("nat")
        if nat_interface_number < 0 and await self._look_for_interface("natnetwork") < 0:
            raise GNS3VMError('VM "{}" must have a NAT or NAT Network interface configured in order to start'.format(self.vmname))

        if sys.platform.startswith("darwin") and parse_version(self._system_properties["API version"]) >= parse_version("7_0"):
            # VirtualBox 7.0+ on macOS requires a host-only network interface
            backend_type = "hostonly-network"
            backend_description = "host-only network"
            vboxnet_type = "hostonlynets"
            interface_number = await self._look_for_interface("hostonlynetwork")
            if interface_number < 0:
                raise GNS3VMError('VM "{}" must have a network adapter attached to a host-only network in order to start'.format(self.vmname))
        else:
            backend_type = "hostonlyadapter"
            backend_description = "host-only adapter"
            vboxnet_type = "hostonlyifs"
            interface_number = await self._look_for_interface("hostonly")

        if interface_number < 0:
            raise GNS3VMError('VM "{}" must have a network adapter attached to a {} in order to start'.format(self.vmname, backend_description))

        vboxnet = await self._look_for_vboxnet(backend_type, interface_number)
        if vboxnet is None:
            raise GNS3VMError('A VirtualBox host-only network could not be found on network adapter {} for "{}"'.format(interface_number, self._vmname))

        if not (await self._check_vboxnet_exists(vboxnet, vboxnet_type)):
            if sys.platform.startswith("win") and vboxnet == "vboxnet0":
                # The GNS3 VM is configured with vboxnet0 by default which is not available
                # on Windows. Try to patch this with the first available vboxnet we find.
                first_available_vboxnet = await self._find_first_available_vboxnet()
                if first_available_vboxnet is None:
                    raise GNS3VMError('Please add a VirtualBox host-only network with DHCP enabled and attached it to network adapter {} for "{}"'.format(interface_number, self._vmname))
                await self.set_hostonly_network(interface_number, first_available_vboxnet)
                vboxnet = first_available_vboxnet
            else:
                try:
                    await self._execute("hostonlyif", ["create"])
                except GNS3VMError:
                    raise GNS3VMError('VirtualBox host-only network "{}" does not exist and could not be automatically created, please make the sure the network adapter {} configuration is valid for "{}"'.format(
                        vboxnet,
                        interface_number,
                        self._vmname
                    ))

        if backend_type == "hostonlyadapter" and not (await self._check_dhcp_server(vboxnet)):
            try:
                await self._add_dhcp_server(vboxnet)
            except GNS3VMError as e:
                raise GNS3VMError("Could not add DHCP server for vboxnet {}: {}, please configure manually".format(vboxnet, e))

        vm_state = await self._get_state()
        log.info('"{}" state is {}'.format(self._vmname, vm_state))

        if vm_state == "poweroff":
            if self.allocate_vcpus_ram:
                log.info("Update GNS3 VM vCPUs and RAM settings")
                await self.set_vcpus(self.vcpus)
                await self.set_ram(self.ram)

            log.info("Update GNS3 VM Hardware Virtualization setting")
            await self.enable_nested_hw_virt()

        if vm_state in ("poweroff", "saved"):
            # start the VM if it is not running
            args = [self._vmname]
            if self._headless:
                args.extend(["--type", "headless"])
            await self._execute("startvm", args)
        elif vm_state == "paused":
            args = [self._vmname, "resume"]
            await self._execute("controlvm", args)

        log.info("Retrieving IP address from GNS3 VM...")
        ip = await self._get_ip_from_guest_property()
        if ip:
            self.ip_address = ip
        else:
            # if we can't get the IP address from the guest property, we try to get it from the GNS3 server (a NAT interface is required)
            if nat_interface_number < 0:
                raise GNS3VMError("Could not find guest IP address for {}".format(self.vmname))
            log.warning("Could not find IP address from guest property, trying to get it from GNS3 server")
            ip_address = "127.0.0.1"
            try:
                # get a random port on localhost
                with socket.socket() as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind((ip_address, 0))
                    api_port = s.getsockname()[1]
            except OSError as e:
                raise GNS3VMError("Error while getting random port: {}".format(e))

            if await self._check_vbox_port_forwarding():
                # delete the GNS3VM NAT port forwarding rule if it exists
                log.info("Removing GNS3VM NAT port forwarding rule from interface {}".format(nat_interface_number))
                await self._execute("controlvm", [self._vmname, "natpf{}".format(nat_interface_number), "delete", "GNS3VM"])

            # add a GNS3VM NAT port forwarding rule to redirect 127.0.0.1 with random port to the port in the VM
            log.info("Adding GNS3VM NAT port forwarding rule with port {} to interface {}".format(api_port, nat_interface_number))
            await self._execute("controlvm", [self._vmname, "natpf{}".format(nat_interface_number),
                                                   "GNS3VM,tcp,{},{},,{}".format(ip_address, api_port, self.port)])

            self.ip_address = await self._get_ip_from_server(interface_number, api_port)

        log.info("GNS3 VM has been started with IP '{}'".format(self.ip_address))
        self.running = True

    async def _get_ip_from_guest_property(self):
        """
        Get the IP from VirtualBox by retrieving the guest property (Guest Additions must be installed).
        """

        remaining_try = 180  # try for 3 minutes
        while remaining_try > 0:
            result = await self._execute("guestproperty", ["get", self._vmname, "/VirtualBox/GuestInfo/Net/0/V4/IP"])
            for info in result.splitlines():
                if ':' in info:
                    name, value = info.split(':', 1)
                    if name == "Value":
                        return value.strip()
            remaining_try -= 1
            await asyncio.sleep(1)
        return None

    async def _get_ip_from_server(self, hostonly_interface_number, api_port):
        """
        Get the IP from VirtualBox by sending a request to the GNS3 server.

        Due to VirtualBox limitation the only way is to send request each
        second to a GNS3 endpoint in order to get the list of the interfaces and
        their IP and after that match it with VirtualBox host only.
        """

        remaining_try = 180  # try for 3 minutes
        while remaining_try > 0:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get('http://127.0.0.1:{}/v2/compute/network/interfaces'.format(api_port)) as resp:
                        if resp.status < 300:
                            try:
                                json_data = await resp.json()
                                if json_data:
                                    for interface in json_data:
                                        if "name" in interface and interface["name"] == "eth{}".format(
                                                hostonly_interface_number - 1):
                                            if "ip_address" in interface and len(interface["ip_address"]) > 0:
                                                return interface["ip_address"]
                            except ValueError:
                                pass
                except (OSError, aiohttp.ClientError, TimeoutError, asyncio.TimeoutError):
                    pass
            remaining_try -= 1
            await asyncio.sleep(1)
        raise GNS3VMError("Could not find guest IP address for {}".format(self.vmname))

    async def suspend(self):
        """
        Suspend the GNS3 VM.
        """

        await self._execute("controlvm", [self._vmname, "savestate"], timeout=3)
        log.info("GNS3 VM has been suspend")
        self.running = False

    async def stop(self):
        """
        Stops the GNS3 VM.
        """

        vm_state = await self._get_state()
        if vm_state == "poweroff":
            self.running = False
            return

        await self._execute("controlvm", [self._vmname, "acpipowerbutton"], timeout=3)
        trial = 120
        while True:
            try:
                vm_state = await self._get_state()
            # During a small amount of time the command will fail
            except GNS3VMError:
                vm_state = "running"
            if vm_state == "poweroff":
                break
            trial -= 1
            if trial == 0:
                await self._execute("controlvm", [self._vmname, "poweroff"], timeout=3)
                break
            await asyncio.sleep(1)

        log.info("GNS3 VM has been stopped")
        self.running = False

    async def set_vcpus(self, vcpus):
        """
        Set the number of vCPU cores for the GNS3 VM.

        :param vcpus: number of vCPU cores
        """

        await self._execute("modifyvm", [self._vmname, "--cpus", str(vcpus)], timeout=3)
        log.info("GNS3 VM vCPU count set to {}".format(vcpus))

    async def set_ram(self, ram):
        """
        Set the RAM amount for the GNS3 VM.

        :param ram: amount of memory
        """

        await self._execute("modifyvm", [self._vmname, "--memory", str(ram)], timeout=3)
        log.info("GNS3 VM RAM amount set to {}".format(ram))

    async def enable_nested_hw_virt(self):
        """
        Enable nested hardware virtualization for the GNS3 VM.
        """

        await self._execute("modifyvm", [self._vmname, "--nested-hw-virt", "on"], timeout=3)
        log.info("Nested hardware virtualization enabled")

    async def set_hostonly_network(self, adapter_number, hostonly_network_name):
        """
        Set a VirtualBox host-only network on a network adapter for the GNS3 VM.

        :param adapter_number: network adapter number
        :param hostonly_network_name: name of the VirtualBox host-only network
        """

        await self._execute("modifyvm", [self._vmname, "--hostonlyadapter{}".format(adapter_number), hostonly_network_name], timeout=3)
        log.info('VirtualBox host-only network "{}" set on network adapter {} for "{}"'.format(hostonly_network_name,
                                                                                               adapter_number,
                                                                                               self._vmname))
