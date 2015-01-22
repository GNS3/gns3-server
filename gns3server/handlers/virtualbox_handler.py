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

from ..web.route import Route
from ..schemas.virtualbox import VBOX_CREATE_SCHEMA
from ..schemas.virtualbox import VBOX_OBJECT_SCHEMA
from ..modules.virtualbox import VirtualBox


class VirtualBoxHandler:

    """
    API entry points for VirtualBox.
    """

    @classmethod
    @Route.post(
        r"/virtualbox",
        status_codes={
            201: "VirtualBox VM instance created",
            400: "Invalid project UUID",
            409: "Conflict"
        },
        description="Create a new VirtualBox VM instance",
        input=VBOX_CREATE_SCHEMA,
        output=VBOX_OBJECT_SCHEMA)
    def create(request, response):

        vbox_manager = VirtualBox.instance()
        vm = yield from vbox_manager.create_vm(request.json["name"],
                                               request.json["project_uuid"],
                                               request.json.get("uuid"),
                                               request.json["vmname"],
                                               request.json["linked_clone"],
                                               console=request.json.get("console"))
        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.post(
        r"/virtualbox/{uuid}/start",
        parameters={
            "uuid": "VirtualBox VM instance UUID"
        },
        status_codes={
            204: "VirtualBox VM instance started",
            400: "Invalid VirtualBox VM instance UUID",
            404: "VirtualBox VM instance doesn't exist"
        },
        description="Start a VirtualBox VM instance")
    def start(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["uuid"])
        yield from vm.start()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/virtualbox/{uuid}/stop",
        parameters={
            "uuid": "VirtualBox VM instance UUID"
        },
        status_codes={
            204: "VirtualBox VM instance stopped",
            400: "Invalid VirtualBox VM instance UUID",
            404: "VirtualBox VM instance doesn't exist"
        },
        description="Stop a VirtualBox VM instance")
    def stop(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["uuid"])
        yield from vm.stop()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/virtualbox/{uuid}/suspend",
        parameters={
            "uuid": "VirtualBox VM instance UUID"
        },
        status_codes={
            204: "VirtualBox VM instance suspended",
            400: "Invalid VirtualBox VM instance UUID",
            404: "VirtualBox VM instance doesn't exist"
        },
        description="Suspend a VirtualBox VM instance")
    def suspend(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["uuid"])
        yield from vm.suspend()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/virtualbox/{uuid}/resume",
        parameters={
            "uuid": "VirtualBox VM instance UUID"
        },
        status_codes={
            204: "VirtualBox VM instance resumed",
            400: "Invalid VirtualBox VM instance UUID",
            404: "VirtualBox VM instance doesn't exist"
        },
        description="Resume a suspended VirtualBox VM instance")
    def suspend(request, response):

        vbox_manager = VirtualBox.instance()
        vm = vbox_manager.get_vm(request.match_info["uuid"])
        yield from vm.resume()
        response.set_status(204)
