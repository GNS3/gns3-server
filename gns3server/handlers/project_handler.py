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
from ..schemas.project import PROJECT_OBJECT_SCHEMA
from ..modules.project_manager import ProjectManager
from aiohttp.web import HTTPConflict


class ProjectHandler:

    @classmethod
    @Route.post(
        r"/project",
        description="Create a project on the server",
        output=PROJECT_OBJECT_SCHEMA,
        input=PROJECT_OBJECT_SCHEMA)
    def create_project(request, response):

        pm = ProjectManager.instance()
        p = pm.create_project(
            location=request.json.get("location"),
            uuid=request.json.get("uuid")
        )
        response.json(p)

    @classmethod
    @Route.post(
        r"/project/{uuid}/commit",
        description="Write changes on disk",
        parameters={
            "uuid": "Project instance UUID",
        },
        status_codes={
            204: "Changes write on disk",
            404: "Project instance doesn't exist"
        })
    def commit(request, response):

        pm = ProjectManager.instance()
        project = pm.get_project(request.match_info["uuid"])
        project.commit()
        response.set_status(204)

    @classmethod
    @Route.delete(
        r"/project/{uuid}",
        description="Delete a project from disk",
        parameters={
            "uuid": "Project instance UUID",
        },
        status_codes={
            204: "Changes write on disk",
            404: "Project instance doesn't exist"
        })
    def delete(request, response):

        pm = ProjectManager.instance()
        project = pm.get_project(request.match_info["uuid"])
        project.delete()
        response.set_status(204)
