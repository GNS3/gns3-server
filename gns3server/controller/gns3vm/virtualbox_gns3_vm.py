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

import json.decoder
import aiohttp
import logging
import asyncio
import socket

from .base_gns3_vm import BaseGNS3VM
from .gns3_vm_error import GNS3VMError

from ...compute.virtualbox import (
    VirtualBox,
    VirtualBoxError
)

log = logging.getLogger(__name__)


class VirtualBoxGNS3VM(BaseGNS3VM):

    def __init__(self, controller):

        self._engine = "virtualbox"
        super().__init__(controller)
        self._virtualbox_manager = VirtualBox()

    @asyncio.coroutine
    def _execute(self, subcommand, args, timeout=60):

        try:
            result = yield from self._virtualbox_manager.execute(subcommand, args, timeout)
            return ("\n".join(result))
        except VirtualBoxError as e:
            raise GNS3VMError("Error while executing VBoxManage command: {}".format(e))

    @asyncio.coroutine
    def _get_state(self):
        """
        Returns the VM state (e.g. running, paused etc.)

        :returns: state (string)
        """

        result = yield from self._execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in result.splitlines():
            if '=' in info:
                name, value = info.split('=', 1)
                if name == "VMState":
                    return value.strip('"')
        return "unknown"

    @asyncio.coroutine
    def _look_for_interface(self, network_backend):
        """
        Look for an interface with a specific network backend.

        :returns: interface number or -1 if none is found
        """

        result = yield from self._execute("showvminfo", [self._vmname, "--machinereadable"])
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

    @asyncio.coroutine
    def _look_for_vboxnet(self, interface_number):
        """
        Look for the VirtualBox network name associated with a host only interface.

        :returns: None or vboxnet name
        """

        result = yield from self._execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in result.splitlines():
            if '=' in info:
                name, value = info.split('=', 1)
                if name == "hostonlyadapter{}".format(interface_number):
                    return value.strip('"')
        return None

    @asyncio.coroutine
    def _check_dhcp_server(self, vboxnet):
        """
        Check if the DHCP server associated with a vboxnet is enabled.

        :param vboxnet: vboxnet name

        :returns: boolean
        """

        properties = yield from self._execute("list", ["dhcpservers"])
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

    @asyncio.coroutine
    def _check_vbox_port_forwarding(self):
        """
        Checks if the NAT port forwarding rule exists.

        :returns: boolean
        """

        result = yield from self._execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in result.splitlines():
            if '=' in info:
                name, value = info.split('=', 1)
                if name.startswith("Forwarding") and value.strip('"').startswith("GNS3VM"):
                    return True
        return False

    @asyncio.coroutine
    def list(self):
        """
        List all VirtualBox VMs
        """

        return (yield from self._virtualbox_manager.list_vms())

    @asyncio.coroutine
    def start(self):
        """
        Start the GNS3 VM.
        """

        # get a NAT interface number
        nat_interface_number = yield from self._look_for_interface("nat")
        if nat_interface_number < 0:
            raise GNS3VMError("The GNS3 VM: {} must have a NAT interface configured in order to start".format(self.vmname))

        hostonly_interface_number = yield from self._look_for_interface("hostonly")
        if hostonly_interface_number < 0:
            raise GNS3VMError("The GNS3 VM: {} must have a host only interface configured in order to start".format(self.vmname))

        vboxnet = yield from self._look_for_vboxnet(hostonly_interface_number)
        if vboxnet is None:
            raise GNS3VMError("VirtualBox host-only network could not be found for interface {} on GNS3 VM".format(hostonly_interface_number))

        if not (yield from self._check_dhcp_server(vboxnet)):
            raise GNS3VMError("DHCP must be enabled on VirtualBox host-only network: {} for GNS3 VM".format(vboxnet))

        vm_state = yield from self._get_state()
        log.info('"{}" state is {}'.format(self._vmname, vm_state))

        if vm_state == "poweroff":
            yield from self.set_vcpus(self.vpcus)
            yield from self.set_ram(self.ram)

        if vm_state in ("poweroff", "saved"):
            # start the VM if it is not running
            args = [self._vmname]
            if self._headless:
                args.extend(["--type", "headless"])
            yield from self._execute("startvm", args)
        elif vm_state == "paused":
            args = [self._vmname, "resume"]
            yield from self._execute("controlvm", args)
        ip_address = "127.0.0.1"
        try:
            # get a random port on localhost
            with socket.socket() as s:
                s.bind((ip_address, 0))
                api_port = s.getsockname()[1]
        except OSError as e:
            raise GNS3VMError("Error while getting random port: {}".format(e))

        if (yield from self._check_vbox_port_forwarding()):
            # delete the GNS3VM NAT port forwarding rule if it exists
            log.info("Removing GNS3VM NAT port forwarding rule from interface {}".format(nat_interface_number))
            yield from self._execute("controlvm", [self._vmname, "natpf{}".format(nat_interface_number), "delete", "GNS3VM"])

        # add a GNS3VM NAT port forwarding rule to redirect 127.0.0.1 with random port to port 3080 in the VM
        log.info("Adding GNS3VM NAT port forwarding rule with port {} to interface {}".format(api_port, nat_interface_number))
        yield from self._execute("controlvm", [self._vmname, "natpf{}".format(nat_interface_number),
                                               "GNS3VM,tcp,{},{},,3080".format(ip_address, api_port)])

        self.ip_address = yield from self._get_ip(hostonly_interface_number, api_port)
        self.port = 3080
        log.info("GNS3 VM has been started with IP {}".format(self.ip_address))
        self.running = True

    @asyncio.coroutine
    def _get_ip(self, hostonly_interface_number, api_port):
        """
        Get the IP from VirtualBox.

        Due to VirtualBox limitation the only way is to send request each
        second to a GNS3 endpoint in order to get the list of the interfaces and
        their IP and after that match it with VirtualBox host only.
        """
        remaining_try = 300
        while remaining_try > 0:
            json_data = None
            session = aiohttp.ClientSession()
            try:
                resp = None
                resp = yield from session.get('http://127.0.0.1:{}/v2/compute/network/interfaces'.format(api_port))
            except (OSError, aiohttp.errors.ClientHttpProcessingError, TimeoutError, asyncio.TimeoutError):
                pass

            if resp:
                try:
                    json_data = yield from resp.json()
                except ValueError:
                    pass
                resp.close()

            session.close()

            if json_data:
                for interface in json_data:
                    if "name" in interface and interface["name"] == "eth{}".format(hostonly_interface_number - 1):
                        if "ip_address" in interface and len(interface["ip_address"]) > 0:
                            return interface["ip_address"]
            remaining_try -= 1
            yield from asyncio.sleep(1)
        raise GNS3VMError("Could not get the GNS3 VM ip make sure the VM receive an IP from VirtualBox")

    @asyncio.coroutine
    def suspend(self):
        """
        Suspend the GNS3 VM.
        """

        yield from self._execute("controlvm", [self._vmname, "savestate"], timeout=3)
        log.info("GNS3 VM has been suspend")
        self.running = False

    @asyncio.coroutine
    def stop(self):
        """
        Stops the GNS3 VM.
        """

        vm_state = yield from self._get_state()
        if vm_state == "poweroff":
            self.running = False
            return

        yield from self._execute("controlvm", [self._vmname, "acpipowerbutton"], timeout=3)
        trial = 120
        while True:
            try:
                vm_state = yield from self._get_state()
            # During a small amount of time the command will fail
            except GNS3VMError:
                vm_state = "running"
            if vm_state == "poweroff":
                break
            trial -= 1
            if trial == 0:
                yield from self._execute("controlvm", [self._vmname, "poweroff"], timeout=3)
                break
            yield from asyncio.sleep(1)

        log.info("GNS3 VM has been stopped")
        self.running = False

    @asyncio.coroutine
    def set_vcpus(self, vcpus):
        """
        Set the number of vCPU cores for the GNS3 VM.

        :param vcpus: number of vCPU cores
        """

        yield from self._execute("modifyvm", [self._vmname, "--cpus", str(vcpus)], timeout=3)
        log.info("GNS3 VM vCPU count set to {}".format(vcpus))

    @asyncio.coroutine
    def set_ram(self, ram):
        """
        Set the RAM amount for the GNS3 VM.

        :param ram: amount of memory
        """

        yield from self._execute("modifyvm", [self._vmname, "--memory", str(ram)], timeout=3)
        log.info("GNS3 VM RAM amount set to {}".format(ram))
