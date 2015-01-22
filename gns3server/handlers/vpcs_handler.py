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
from ..schemas.vpcs import VPCS_CREATE_SCHEMA
from ..schemas.vpcs import VPCS_UPDATE_SCHEMA
from ..schemas.vpcs import VPCS_OBJECT_SCHEMA
from ..schemas.vpcs import VPCS_NIO_SCHEMA
from ..modules.vpcs import VPCS


class VPCSHandler:

    """
    API entry points for VPCS.
    """

    @classmethod
    @Route.post(
        r"/vpcs",
        status_codes={
            201: "VPCS instance created",
            400: "Invalid project UUID",
            409: "Conflict"
        },
        description="Create a new VPCS instance",
        input=VPCS_CREATE_SCHEMA,
        output=VPCS_OBJECT_SCHEMA)
    def create(request, response):

        vpcs = VPCS.instance()
        vm = yield from vpcs.create_vm(request.json["name"],
                                       request.json["project_uuid"],
                                       request.json.get("uuid"),
                                       console=request.json.get("console"),
                                       script_file=request.json.get("script_file"),
                                       startup_script=request.json.get("startup_script"))
        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.get(
        r"/vpcs/{uuid}",
        parameters={
            "uuid": "VPCS instance UUID"
        },
        status_codes={
            200: "Success",
            404: "VPCS instance doesn't exist"
        },
        description="Get a VPCS instance")
    def show(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_vm(request.match_info["uuid"])
        response.json(vm)

    @classmethod
    @Route.put(
        r"/vpcs/{uuid}",
        status_codes={
            200: "VPCS instance updated",
            404: "VPCS instance doesn't exist",
            409: "Conflict"
        },
        description="Update a VPCS instance",
        input=VPCS_UPDATE_SCHEMA,
        output=VPCS_OBJECT_SCHEMA)
    def update(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_vm(request.match_info["uuid"])
        vm.name = request.json.get("name", vm.name)
        vm.console = request.json.get("console", vm.console)
        vm.script_file = request.json.get("script_file", vm.script_file)
        vm.startup_script = request.json.get("startup_script", vm.startup_script)
        response.json(vm)

    @classmethod
    @Route.delete(
        r"/vpcs/{uuid}",
        status_codes={
            204: "VPCS instance deleted",
            404: "VPCS instance doesn't exist"
        },
        description="Delete a VPCS instance")
    def delete(request, response):

        yield from VPCS.instance().delete_vm(request.match_info["uuid"])
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/vpcs/{uuid}/start",
        parameters={
            "uuid": "VPCS instance UUID"
        },
        status_codes={
            204: "VPCS instance started",
            400: "Invalid VPCS instance UUID",
            404: "VPCS instance doesn't exist"
        },
        description="Start a VPCS instance")
    def start(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_vm(request.match_info["uuid"])
        yield from vm.start()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/vpcs/{uuid}/stop",
        parameters={
            "uuid": "VPCS instance UUID"
        },
        status_codes={
            204: "VPCS instance stopped",
            400: "Invalid VPCS instance UUID",
            404: "VPCS instance doesn't exist"
        },
        description="Stop a VPCS instance")
    def stop(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_vm(request.match_info["uuid"])
        yield from vm.stop()
        response.set_status(204)

    @Route.post(
        r"/vpcs/{uuid}/ports/{port_id}/nio",
        parameters={
            "uuid": "VPCS instance UUID",
            "port_id": "Id of the port where the nio should be add"
        },
        status_codes={
            201: "NIO created",
            400: "Invalid VPCS instance UUID",
            404: "VPCS instance doesn't exist"
        },
        description="Add a NIO to a VPCS",
        input=VPCS_NIO_SCHEMA,
        output=VPCS_NIO_SCHEMA)
    def create_nio(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_vm(request.match_info["uuid"])
        nio = vm.port_add_nio_binding(int(request.match_info["port_id"]), request.json)
        response.set_status(201)
        response.json(nio)

    @classmethod
    @Route.delete(
        r"/vpcs/{uuid}/ports/{port_id}/nio",
        parameters={
            "uuid": "VPCS instance UUID",
            "port_id": "ID of the port where the nio should be removed"
        },
        status_codes={
            204: "NIO deleted",
            400: "Invalid VPCS instance UUID",
            404: "VPCS instance doesn't exist"
        },
        description="Remove a NIO from a VPCS")
    def delete_nio(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_vm(request.match_info["uuid"])
        nio = vm.port_remove_nio_binding(int(request.match_info["port_id"]))
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/vpcs/{uuid}/reload",
        parameters={
            "uuid": "VPCS instance UUID",
        },
        status_codes={
            204: "VPCS reloaded",
            404: "VPCS instance doesn't exist"
        },
        description="Remove a NIO from a VPCS")
    def reload(request, response):

        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_vm(request.match_info["uuid"])
        yield from vm.reload()
        response.set_status(204)
