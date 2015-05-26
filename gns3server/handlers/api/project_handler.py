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

from ...web.route import Route
from ...schemas.project import PROJECT_OBJECT_SCHEMA, PROJECT_CREATE_SCHEMA, PROJECT_UPDATE_SCHEMA
from ...modules.project_manager import ProjectManager
from ...modules import MODULES


class ProjectHandler:

    @classmethod
    @Route.post(
        r"/projects",
        description="Create a new project on the server",
        status_codes={
            201: "Project created",
            409: "Project already created"
        },
        output=PROJECT_OBJECT_SCHEMA,
        input=PROJECT_CREATE_SCHEMA)
    def create_project(request, response):

        pm = ProjectManager.instance()
        p = pm.create_project(
            name=request.json.get("name"),
            path=request.json.get("path"),
            project_id=request.json.get("project_id"),
            temporary=request.json.get("temporary", False)
        )
        response.set_status(201)
        response.json(p)

    @classmethod
    @Route.get(
        r"/projects/{project_id}",
        description="Get project information",
        parameters={
            "project_id": "The UUID of the project",
        },
        status_codes={
            200: "Success",
            404: "The project doesn't exist"
        },
        output=PROJECT_OBJECT_SCHEMA)
    def show(request, response):

        pm = ProjectManager.instance()
        project = pm.get_project(request.match_info["project_id"])
        response.json(project)

    @classmethod
    @Route.put(
        r"/projects/{project_id}",
        description="Update a project",
        parameters={
            "project_id": "The UUID of the project",
        },
        status_codes={
            200: "The project has been updated",
            403: "You are not allowed to modify this property",
            404: "The project doesn't exist"
        },
        output=PROJECT_OBJECT_SCHEMA,
        input=PROJECT_UPDATE_SCHEMA)
    def update(request, response):

        pm = ProjectManager.instance()
        project = pm.get_project(request.match_info["project_id"])
        project.name = request.json.get("name", project.name)
        project_path = request.json.get("path", project.path)
        if project_path != project.path:
            old_path = project.path
            project.path = project_path
            for module in MODULES:
                yield from module.instance().project_moved(project)
            yield from project.clean_old_path(old_path)
        # Very important we need to remove temporary flag after moving the project
        project.temporary = request.json.get("temporary", project.temporary)
        response.json(project)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/commit",
        description="Write changes on disk",
        parameters={
            "project_id": "The UUID of the project",
        },
        status_codes={
            204: "Changes have been written on disk",
            404: "The project doesn't exist"
        })
    def commit(request, response):

        pm = ProjectManager.instance()
        project = pm.get_project(request.match_info["project_id"])
        yield from project.commit()
        response.set_status(204)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/close",
        description="Close a project",
        parameters={
            "project_id": "The UUID of the project",
        },
        status_codes={
            204: "The project has been closed",
            404: "The project doesn't exist"
        })
    def close(request, response):

        pm = ProjectManager.instance()
        project = pm.get_project(request.match_info["project_id"])
        yield from project.close()
        pm.remove_project(project.id)
        response.set_status(204)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}",
        description="Delete a project from disk",
        parameters={
            "project_id": "The UUID of the project",
        },
        status_codes={
            204: "Changes have been written on disk",
            404: "The project doesn't exist"
        })
    def delete(request, response):

        pm = ProjectManager.instance()
        project = pm.get_project(request.match_info["project_id"])
        yield from project.delete()
        pm.remove_project(project.id)
        response.set_status(204)
