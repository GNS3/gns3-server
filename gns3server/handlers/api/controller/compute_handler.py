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

from gns3server.web.route import Route
from gns3server.controller import Controller

from gns3server.schemas.compute import (
    COMPUTE_CREATE_SCHEMA,
    COMPUTE_OBJECT_SCHEMA,
    COMPUTE_UPDATE_SCHEMA,
    COMPUTE_ENDPOINT_OUTPUT_OBJECT_SCHEMA,
    COMPUTE_PORTS_OBJECT_SCHEMA
)

import logging
log = logging.getLogger(__name__)


class ComputeHandler:
    """API entry points for compute management."""

    @Route.post(
        r"/computes",
        description="Register a compute",
        status_codes={
            201: "Compute added"
        },
        input=COMPUTE_CREATE_SCHEMA,
        output=COMPUTE_OBJECT_SCHEMA)
    async def create(request, response):

        compute = await Controller.instance().add_compute(**request.json)
        response.set_status(201)
        response.json(compute)

    @Route.get(
        r"/computes",
        description="List of computes",
        status_codes={
            200: "Computes list returned"
        })
    def list(request, response):

        controller = Controller.instance()
        response.json([c for c in controller.computes.values()])

    @Route.put(
        r"/computes/{compute_id}",
        description="Update a compute",
        status_codes={
            200: "Compute updated",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        input=COMPUTE_UPDATE_SCHEMA,
        output=COMPUTE_OBJECT_SCHEMA)
    async def update(request, response):

        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])

        # Ignore these because we only use them when creating a node
        request.json.pop("compute_id", None)
        await compute.update(**request.json)
        response.set_status(200)
        response.json(compute)

    @Route.get(
        r"/computes/{compute_id}/{emulator}/images",
        parameters={
            "compute_id": "Compute UUID",
            "emulator": "Emulator type"
        },
        status_codes={
            200: "OK",
            404: "Instance doesn't exist"
        },
        description="Return the list of images available on compute for this emulator type")
    async def images(request, response):
        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])
        res = await compute.images(request.match_info["emulator"])
        response.json(res)

    @Route.get(
        r"/computes/endpoint/{compute_id}/{emulator}/{action:.+}",
        parameters={
            "compute_id": "Compute UUID"
        },
        status_codes={
            200: "OK",
            404: "Instance doesn't exist"
        },
        raw=True,
        output=COMPUTE_ENDPOINT_OUTPUT_OBJECT_SCHEMA,
        description="Returns the endpoint for particular `compute` to specific action. "
                    "WARNING: This is experimental feature and may change anytime. Please don't rely on this endpoint.")
    def endpoint(request, response):
        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])

        path = '/{emulator}/{action}'.format(
            emulator=request.match_info['emulator'],
            action=request.match_info['action'])

        endpoint = compute.get_url(path)

        response.set_status(200)
        response.json(dict(
            endpoint=endpoint
        ))

    @Route.get(
        r"/computes/{compute_id}/{emulator}/{action:.+}",
        parameters={
            "compute_id": "Compute UUID"
        },
        status_codes={
            200: "OK",
            404: "Instance doesn't exist"
        },
        description="Forward call specific to compute node. Read the full compute API for available actions")
    async def get_forward(request, response):
        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])
        res = await compute.forward("GET", request.match_info["emulator"], request.match_info["action"])
        response.json(res)

    @Route.post(
        r"/computes/{compute_id}/{emulator}/{action:.+}",
        parameters={
            "compute_id": "Compute UUID"
        },
        status_codes={
            200: "OK",
            404: "Instance doesn't exist"
        },
        raw=True,
        description="Forward call specific to compute node. Read the full compute API for available actions")
    async def post_forward(request, response):
        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])
        res = await compute.forward("POST", request.match_info["emulator"], request.match_info["action"], data=request.content)
        response.json(res)

    @Route.put(
        r"/computes/{compute_id}/{emulator}/{action:.+}",
        parameters={
            "compute_id": "Compute UUID"
        },
        status_codes={
            200: "OK",
            404: "Instance doesn't exist"
        },
        raw=True,
        description="Forward call specific to compute node. Read the full compute API for available actions")
    async def put_forward(request, response):
        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])
        res = await compute.forward("PUT", request.match_info["emulator"], request.match_info["action"], data=request.content)
        response.json(res)

    @Route.get(
        r"/computes/{compute_id}",
        description="Get a compute information",
        status_codes={
            200: "Compute information returned"
        },
        output=COMPUTE_OBJECT_SCHEMA)
    def get(request, response):

        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])
        response.json(compute)

    @Route.delete(
        r"/computes/{compute_id}",
        parameters={
            "compute_id": "Compute UUID"
        },
        status_codes={
            204: "Instance deleted",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        description="Delete a compute instance")
    async def delete(request, response):
        controller = Controller.instance()
        await controller.delete_compute(request.match_info["compute_id"])
        response.set_status(204)

    @Route.post(
        r"/computes/{compute_id}/auto_idlepc",
        parameters={
            "compute_id": "Compute UUID"
        },
        status_codes={
            200: "Idle PC computed",
        },
        description="Compute IDLE PC value")
    async def autoidlepc(request, response):
        controller = Controller.instance()
        res = await controller.autoidlepc(request.match_info["compute_id"], request.json["platform"], request.json["image"], request.json["ram"])
        response.json(res)

    @Route.get(
        r"/computes/{compute_id}/ports",
        parameters={
            "compute_id": "Compute UUID"
        },
        status_codes={
            200: "Ports information returned",
        },
        description="Get ports used by a compute",
        output=COMPUTE_PORTS_OBJECT_SCHEMA)
    async def ports(request, response):
        controller = Controller.instance()
        res = await controller.compute_ports(request.match_info["compute_id"])
        response.json(res)

