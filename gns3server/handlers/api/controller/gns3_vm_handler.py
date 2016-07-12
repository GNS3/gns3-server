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

from aiohttp.web import HTTPConflict
from gns3server.web.route import Route
from gns3server.controller.vmware_gns3_vm import VMwareGNS3VM
from gns3server.controller.virtualbox_gns3_vm import VirtualBoxGNS3VM

import logging
log = logging.getLogger(__name__)


class GNS3VMHandler:
    """API entry points for GNS3 VM management."""

    @Route.get(
        r"/gns3vm/{engine}/vms",
        parameters={
            "engine": "Virtualization engine name"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
        },
        description="Get all the available VMs for a specific virtualization engine")
    def get_vms(request, response):

        engine = request.match_info["engine"]
        if engine == "vmware":
            engine_instance = VMwareGNS3VM.instance()
        elif engine == "virtualbox":
            engine_instance = VirtualBoxGNS3VM.instance()
        else:
            raise HTTPConflict(text="Unknown engine: '{}'".format(engine))
        vms = yield from engine_instance.list()
        response.json(vms)

    @Route.get(
        r"/gns3vm",
        description="Get GNS3 VM settings",
        status_codes={
            200: "GNS3 VM settings returned"
        })
    def show(request, response):

        gns3_vm = VMwareGNS3VM.instance()
        response.json(gns3_vm)

    @Route.put(
        r"/gns3vm",
        description="Update GNS3 VM settings",
        #input=GNS3VM_UPDATE_SCHEMA,  # TODO: validate settings
        status_codes={
            200: "GNS3 VM updated"
        })
    def update(request, response):

        gns3_vm = VMwareGNS3VM.instance()
        for name, value in request.json.items():
            if hasattr(gns3_vm, name) and getattr(gns3_vm, name) != value:
                setattr(gns3_vm, name, value)
        gns3_vm.save()
        response.json(gns3_vm)

    @Route.post(
        r"/gns3vm/start",
        status_codes={
            200: "Instance started",
            400: "Invalid request",
        },
        description="Start the GNS3 VM"
    )
    def start(request, response):

        gns3_vm = VMwareGNS3VM.instance()
        yield from gns3_vm.start()
        response.json(gns3_vm)

    @Route.post(
        r"/gns3vm/stop",
        status_codes={
            204: "Instance stopped",
            400: "Invalid request",
        },
        description="Stop the GNS3 VM")
    def stop(request, response):

        gns3_vm = VMwareGNS3VM.instance()
        yield from gns3_vm.stop()
        response.set_status(204)
