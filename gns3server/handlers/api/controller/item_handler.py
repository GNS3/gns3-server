# -*- coding: utf-8 -*-
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

import aiohttp

from gns3server.web.route import Route
from gns3server.controller import Controller

from gns3server.schemas.item import (
    ITEM_OBJECT_SCHEMA,
)


class ItemHandler:
    """
    API entry point for Item
    """

    @Route.get(
        r"/projects/{project_id}/items",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            200: "List of items returned",
        },
        description="List items of a project")
    def list_items(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        response.json([v for v in project.items.values()])

    @Route.post(
        r"/projects/{project_id}/items",
        parameters={
            "project_id": "Project UUID"
        },
        status_codes={
            201: "Item created",
            400: "Invalid request"
        },
        description="Create a new item instance",
        input=ITEM_OBJECT_SCHEMA,
        output=ITEM_OBJECT_SCHEMA)
    def create(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        item = yield from project.add_item(**request.json)
        response.set_status(201)
        response.json(item)

    @Route.put(
        r"/projects/{project_id}/items/{item_id}",
        parameters={
            "project_id": "Project UUID",
            "item_id": "Item UUID"
        },
        status_codes={
            201: "Item updated",
            400: "Invalid request"
        },
        description="Create a new item instance",
        input=ITEM_OBJECT_SCHEMA,
        output=ITEM_OBJECT_SCHEMA)
    def update(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        item = project.get_item(request.match_info["item_id"])
        yield from item.update(**request.json)
        response.set_status(201)
        response.json(item)

    @Route.delete(
        r"/projects/{project_id}/items/{item_id}",
        parameters={
            "project_id": "Project UUID",
            "item_id": "Item UUID"
        },
        status_codes={
            204: "Item deleted",
            400: "Invalid request"
        },
        description="Delete a item instance")
    def delete(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        yield from project.delete_item(request.match_info["item_id"])
        response.set_status(204)

