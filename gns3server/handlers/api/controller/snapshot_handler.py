#!/usr/bin/env python
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


import logging
log = logging.getLogger()

from gns3server.web.route import Route
from gns3server.controller import Controller

from gns3server.schemas.snapshot import (
    SNAPSHOT_OBJECT_SCHEMA,
    SNAPSHOT_CREATE_SCHEMA
)
from gns3server.schemas.project import PROJECT_OBJECT_SCHEMA


class SnapshotHandler:

    @Route.post(
        r"/projects/{project_id}/snapshots",
        description="Create snapshot of a project",
        parameters={
            "project_id": "Project UUID",
        },
        input=SNAPSHOT_CREATE_SCHEMA,
        output=SNAPSHOT_OBJECT_SCHEMA,
        status_codes={
            201: "Snapshot created",
            404: "The project doesn't exist"
        })
    async def create(request, response):
        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        snapshot = await project.snapshot(request.json["name"])
        response.json(snapshot)
        response.set_status(201)

    @Route.get(
        r"/projects/{project_id}/snapshots",
        description="List snapshots of a project",
        parameters={
            "project_id": "Project UUID",
        },
        status_codes={
            200: "Snapshot list returned",
            404: "The project doesn't exist"
        })
    def list(request, response):
        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        snapshots = [s for s in project.snapshots.values()]
        response.json(sorted(snapshots, key=lambda s: (s.created_at, s.name)))

    @Route.delete(
        r"/projects/{project_id}/snapshots/{snapshot_id}",
        description="Delete a snapshot from disk",
        parameters={
            "project_id": "Project UUID",
            "snapshot_id": "Snapshot UUID"
        },
        status_codes={
            204: "Changes have been written on disk",
            404: "The project or snapshot doesn't exist"
        })
    async def delete(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        await project.delete_snapshot(request.match_info["snapshot_id"])
        response.set_status(204)

    @Route.post(
        r"/projects/{project_id}/snapshots/{snapshot_id}/restore",
        description="Restore a snapshot from disk",
        parameters={
            "project_id": "Project UUID",
            "snapshot_id": "Snapshot UUID"
        },
        output=PROJECT_OBJECT_SCHEMA,
        status_codes={
            201: "The snapshot has been restored",
            404: "The project or snapshot doesn't exist"
        })
    async def restore(request, response):

        controller = Controller.instance()
        project = controller.get_project(request.match_info["project_id"])
        snapshot = project.get_snapshot(request.match_info["snapshot_id"])
        project = await snapshot.restore()
        response.set_status(201)
        response.json(project)
