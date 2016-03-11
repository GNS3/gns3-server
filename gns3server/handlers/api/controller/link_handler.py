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

from ....web.route import Route
from ....schemas.link import LINK_OBJECT_SCHEMA
from ....controller.project import Project
from ....controller import Controller


class LinkHandler:
    """
    API entry point for Link
    """

    @classmethod
    @Route.post(
        r"/projects/{project_id}/links",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            201: "Link created",
            400: "Invalid request"
        },
        description="Create a new link instance",
        input=LINK_OBJECT_SCHEMA,
        output=LINK_OBJECT_SCHEMA)
    def create(request, response):

        controller = Controller.instance()
        project = controller.getProject(request.match_info["project_id"])
        link = yield from project.addLink()
        for vm in request.json["vms"]:
            yield from link.addVM(project.getVM(vm["vm_id"]),
                                  vm["adapter_number"],
                                  vm["port_number"])
        response.set_status(201)
        response.json(link)
