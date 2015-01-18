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
from ..schemas.vpcs import VPCS_OBJECT_SCHEMA
from ..schemas.vpcs import VPCS_ADD_NIO_SCHEMA
from ..modules.vpcs import VPCS


class VPCSHandler(object):
    """
    API entry points for VPCS.
    """

    @classmethod
    @Route.post(
        r"/vpcs",
        status_codes={
            201: "VPCS instance created",
            409: "Conflict"
        },
        description="Create a new VPCS instance",
        input=VPCS_CREATE_SCHEMA,
        output=VPCS_OBJECT_SCHEMA)
    def create(request, response):

        vpcs = VPCS.instance()
        vm = yield from vpcs.create_vm(request.json["name"])
        response.json({"name": vm.name,
                       "id": vm.id,
                       "console": vm.console})

    @classmethod
    @Route.post(
        r"/vpcs/{id:\d+}/start",
        parameters={
            "id": "VPCS instance ID"
        },
        status_codes={
            204: "VPCS instance started",
        },
        description="Start a VPCS instance")
    def create(request, response):

        vpcs_manager = VPCS.instance()
        yield from vpcs_manager.start_vm(int(request.match_info["id"]))
        response.json({})

    @classmethod
    @Route.post(
        r"/vpcs/{id:\d+}/stop",
        parameters={
            "id": "VPCS instance ID"
        },
        status_codes={
            201: "Success of stopping VPCS",
        },
        description="Stop a VPCS instance")
    def create(request, response):

        vpcs_manager = VPCS.instance()
        yield from vpcs_manager.stop_vm(int(request.match_info["id"]))
        response.json({})

    @classmethod
    @Route.get(
        r"/vpcs/{id:\d+}",
        parameters={
            "id": "VPCS instance ID"
        },
        description="Get information about a VPCS",
        output=VPCS_OBJECT_SCHEMA)
    def show(request, response):

        response.json({'name': "PC 1", "id": 42, "console": 4242})

    @classmethod
    @Route.put(
        r"/vpcs/{id:\d+}",
        parameters={
            "id": "VPCS instance ID"
        },
        description="Update VPCS information",
        input=VPCS_OBJECT_SCHEMA,
        output=VPCS_OBJECT_SCHEMA)
    def update(request, response):

        response.json({'name': "PC 1", "id": 42, "console": 4242})

    @classmethod
    @Route.post(
        r"/vpcs/{id:\d+}/nio",
        parameters={
            "id": "VPCS instance ID"
        },
        status_codes={
            201: "NIO created",
            409: "Conflict"
        },
        description="ADD NIO to a VPCS",
        input=VPCS_ADD_NIO_SCHEMA)
    def create_nio(request, response):

        # TODO: raise 404 if VPCS not found
        response.json({'name': "PC 2", "id": 42, "console": 4242})
