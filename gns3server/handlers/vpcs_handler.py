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
    @classmethod
    @Route.post(
        r"/vpcs",
        status_codes={
            201: "Success of creation of VPCS",
            409: "Conflict"
        },
        description="Create a new VPCS and return it",
        input=VPCS_CREATE_SCHEMA,
        output=VPCS_OBJECT_SCHEMA)
    def create(request, response):
        vpcs = VPCS.instance()
        vm = yield from vpcs.create_vm(request.json['name'])
        response.json({'name': vm.name,
                       "vpcs_id": vm.id,
                       "console": vm.console})

    @classmethod
    @Route.post(
        r"/vpcs/{vpcs_id}/start",
        parameters={
            "vpcs_id": "Id of VPCS instance"
        },
        status_codes={
            201: "Success of creation of VPCS",
        },
        description="Start VPCS",
        )
    def create(request, response):
        vpcs_manager = VPCS.instance()
        vm = yield from vpcs_manager.start_vm(int(request.match_info['vpcs_id']))
        response.json({})

    @classmethod
    @Route.post(
        r"/vpcs/{vpcs_id}/stop",
        parameters={
            "vpcs_id": "Id of VPCS instance"
        },
        status_codes={
            201: "Success of stopping VPCS",
        },
        description="Stop VPCS",
        )
    def create(request, response):
        vpcs_manager = VPCS.instance()
        vm = yield from vpcs_manager.stop_vm(int(request.match_info['vpcs_id']))
        response.json({})

    @classmethod
    @Route.post(
        r"/vpcs/{vpcs_id}/ports/{port_id}/nio",
        parameters={
            "vpcs_id": "Id of VPCS instance"
        },
        status_codes={
            201: "Success of creation of NIO",
            409: "Conflict"
        },
        description="ADD NIO to a VPCS",
        input=VPCS_ADD_NIO_SCHEMA)
    def create_nio(request, response):
        # TODO: raise 404 if VPCS not found GET VM can raise an exeption
        # TODO: response with nio
        vpcs_manager = VPCS.instance()
        vm = vpcs_manager.get_vm(int(request.match_info['vpcs_id']))
        vm.port_add_nio_binding(int(request.match_info['port_id']), request.json)

        response.json({'name': "PC 2", "vpcs_id": 42, "console": 4242})


