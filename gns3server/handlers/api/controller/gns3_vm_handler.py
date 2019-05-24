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

from gns3server.web.route import Route
from gns3server.controller import Controller
from gns3server.schemas.gns3vm import GNS3VM_SETTINGS_SCHEMA

import logging
log = logging.getLogger(__name__)


class GNS3VMHandler:
    """API entry points for GNS3 VM management."""

    @Route.get(
        r"/gns3vm/engines",
        description="Return the list of engines supported for the GNS3VM",
        status_codes={
            200: "OK"
        })
    def list_engines(request, response):

        gns3_vm = Controller().instance().gns3vm
        response.json(gns3_vm.engine_list())

    @Route.get(
        r"/gns3vm/engines/{engine}/vms",
        parameters={
            "engine": "Virtualization engine name"
        },
        status_codes={
            200: "Success",
            400: "Invalid request",
        },
        description="Get all the available VMs for a specific virtualization engine")
    async def get_vms(request, response):

        vms = await Controller.instance().gns3vm.list(request.match_info["engine"])
        response.json(vms)

    @Route.get(
        r"/gns3vm",
        description="Get GNS3 VM settings",
        status_codes={
            200: "GNS3 VM settings returned"
        },
        output_schema=GNS3VM_SETTINGS_SCHEMA)
    def show(request, response):
        response.json(Controller.instance().gns3vm)

    @Route.put(
        r"/gns3vm",
        description="Update GNS3 VM settings",
        input_schema=GNS3VM_SETTINGS_SCHEMA,
        output_schema=GNS3VM_SETTINGS_SCHEMA,
        status_codes={
            201: "GNS3 VM updated"
        })
    async def update(request, response):

        controller = Controller().instance()
        gns3_vm = controller.gns3vm
        await gns3_vm.update_settings(request.json)
        controller.save()
        response.json(gns3_vm)
        response.set_status(201)
