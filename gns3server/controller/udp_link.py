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

import asyncio
import aiohttp


from .link import Link


class UDPLink(Link):

    def __init__(self, project):
        super().__init__(project)
        self._capture_vm = None

    @asyncio.coroutine
    def create(self):
        """
        Create the link on the VMs
        """

        vm1 = self._vms[0]["vm"]
        adapter_number1 = self._vms[0]["adapter_number"]
        port_number1 = self._vms[0]["port_number"]
        vm2 = self._vms[1]["vm"]
        adapter_number2 = self._vms[1]["adapter_number"]
        port_number2 = self._vms[1]["port_number"]

        # Reserve a UDP port on both side
        response = yield from vm1.compute.post("/projects/{}/ports/udp".format(self._project.id))
        self._vm1_port = response.json["udp_port"]
        response = yield from vm2.compute.post("/projects/{}/ports/udp".format(self._project.id))
        self._vm2_port = response.json["udp_port"]

        # Create the tunnel on both side
        data = {
            "lport": self._vm1_port,
            "rhost": vm2.compute.host,
            "rport": self._vm2_port,
            "type": "nio_udp"
        }
        yield from vm1.post("/adapters/{adapter_number}/ports/{port_number}/nio".format(adapter_number=adapter_number1, port_number=port_number1), data=data)

        data = {
            "lport": self._vm2_port,
            "rhost": vm1.compute.host,
            "rport": self._vm1_port,
            "type": "nio_udp"
        }
        yield from vm2.post("/adapters/{adapter_number}/ports/{port_number}/nio".format(adapter_number=adapter_number2, port_number=port_number2), data=data)

    @asyncio.coroutine
    def delete(self):
        """
        Delete the link and free the ressources
        """
        vm1 = self._vms[0]["vm"]
        adapter_number1 = self._vms[0]["adapter_number"]
        port_number1 = self._vms[0]["port_number"]
        vm2 = self._vms[1]["vm"]
        adapter_number2 = self._vms[1]["adapter_number"]
        port_number2 = self._vms[1]["port_number"]

        yield from vm1.delete("/adapters/{adapter_number}/ports/{port_number}/nio".format(adapter_number=adapter_number1, port_number=port_number1))
        yield from vm2.delete("/adapters/{adapter_number}/ports/{port_number}/nio".format(adapter_number=adapter_number2, port_number=port_number2))

    @asyncio.coroutine
    def start_capture(self, data_link_type="DLT_EN10MB"):
        """
        Start capture on a link
        """
        self._capture_vm = self._choose_capture_side()
        data = {
            "capture_file_name": self.capture_file_name(),
            "data_link_type": data_link_type
        }
        yield from self._capture_vm["vm"].post("/adapters/{adapter_number}/ports/{port_number}/start_capture".format(adapter_number=self._capture_vm["adapter_number"], port_number=self._capture_vm["port_number"]), data=data)

    @asyncio.coroutine
    def stop_capture(self):
        """
        Stop capture on a link
        """
        if self._capture_vm:
            yield from self._capture_vm["vm"].post("/adapters/{adapter_number}/ports/{port_number}/stop_capture".format(adapter_number=self._capture_vm["adapter_number"], port_number=self._capture_vm["port_number"]))
            self._capture_vm = None

    def _choose_capture_side(self):
        """
        Run capture on the best candidate.

        The ideal candidate is a node who support capture on controller
        server

        :returns: VM where the capture should run
        """

        # For saving bandwith we use the local node first
        for vm in self._vms:
            if vm["vm"].compute.id == "local" and vm["vm"].vm_type not in ["qemu", "vpcs"]:
                return vm

        for vm in self._vms:
            if vm["vm"].vm_type not in ["qemu", "vpcs"]:
                return vm

        raise aiohttp.web.HTTPConflict(text="Capture is not supported for this link")
