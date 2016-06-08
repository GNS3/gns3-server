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
    COMPUTE_UPDATE_SCHEMA
)

import logging
log = logging.getLogger(__name__)


class ComputeHandler:
    """API entry points for compute server management."""

    @Route.post(
        r"/computes",
        description="Register a compute server",
        status_codes={
            201: "Compute server added"
        },
        input=COMPUTE_CREATE_SCHEMA,
        output=COMPUTE_OBJECT_SCHEMA)
    def create(request, response):

        compute = yield from Controller.instance().add_compute(**request.json)
        response.set_status(201)
        response.json(compute)

    @Route.get(
        r"/computes",
        description="List of compute servers",
        status_codes={
            200: "Compute servers list returned"
        })
    def list(request, response):

        controller = Controller.instance()
        response.json([c for c in controller.computes.values()])

    @Route.put(
        r"/computes/{compute_id}",
        description="Get a compute server information",
        status_codes={
            200: "Compute server updated",
            400: "Invalid request",
            404: "Instance doesn't exist"
        },
        input=COMPUTE_UPDATE_SCHEMA,
        output=COMPUTE_OBJECT_SCHEMA)
    def update(request, response):

        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])

        # Ignore these because we only use them when creating a node
        request.json.pop("compute_id", None)
        yield from compute.update(**request.json)
        response.set_status(200)
        response.json(compute)

    @Route.get(
        r"/computes/{compute_id}/{emulator}/images",
        parameters={
            "compute_id": "Compute UUID"
        },
        status_codes={
            200: "OK",
            404: "Instance doesn't exist"
        },
        description="Return the list of images available on compute and controller for this emulator type")
    def images(request, response):
        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])
        res = yield from compute.images(request.match_info["emulator"])
        response.json(res)

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
    def get_forward(request, response):
        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])
        res = yield from compute.forward("GET", request.match_info["emulator"], request.match_info["action"])
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
    def post_forward(request, response):
        controller = Controller.instance()
        compute = controller.get_compute(request.match_info["compute_id"])
        res = yield from compute.forward("POST", request.match_info["emulator"], request.match_info["action"], data=request.content)
        response.json(res)

    @Route.get(
        r"/computes/{compute_id}",
        description="Get a compute server information",
        status_codes={
            200: "Compute server information returned"
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
    def delete(request, response):
        controller = Controller.instance()
        yield from controller.delete_compute(request.match_info["compute_id"])
        response.set_status(204)
