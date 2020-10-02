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

"""
API endpoints for snapshots.
"""

from fastapi import APIRouter, status
from typing import List
from uuid import UUID

from gns3server.endpoints.schemas.common import ErrorMessage
from gns3server.endpoints import schemas
from gns3server.controller import Controller

router = APIRouter()

import logging
log = logging.getLogger()


@router.post("/projects/{project_id}/snapshots",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.Snapshot,
             responses={404: {"model": ErrorMessage, "description": "Could not find project"}})
async def create_snapshot(project_id: UUID, snapshot_data: schemas.SnapshotCreate):
    """
    Create a new snapshot of the project.
    """

    controller = Controller.instance()
    project = controller.get_project(str(project_id))
    snapshot = await project.snapshot(snapshot_data.name)
    return snapshot.__json__()


@router.get("/projects/{project_id}/snapshots",
            response_model=List[schemas.Snapshot],
            response_description="List of snapshots",
            response_model_exclude_unset=True,
            responses={404: {"model": ErrorMessage, "description": "Could not find project"}})
def list_snapshots(project_id: UUID):
    """
    Return a list of snapshots belonging to the project.
    """

    controller = Controller.instance()
    project = controller.get_project(str(project_id))
    snapshots = [s for s in project.snapshots.values()]
    return [s.__json__() for s in sorted(snapshots, key=lambda s: (s.created_at, s.name))]


@router.delete("/projects/{project_id}/snapshots/{snapshot_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               responses={404: {"model": ErrorMessage, "description": "Could not find project or snapshot"}})
async def delete_snapshot(project_id: UUID, snapshot_id: UUID):
    """
    Delete a snapshot belonging to the project.
    """

    controller = Controller.instance()
    project = controller.get_project(str(project_id))
    await project.delete_snapshot(str(snapshot_id))


@router.post("/projects/{project_id}/snapshots/{snapshot_id}/restore",
             status_code=status.HTTP_201_CREATED,
             response_model=schemas.Project,
             responses={404: {"model": ErrorMessage, "description": "Could not find project or snapshot"}})
async def restore_snapshot(project_id: UUID, snapshot_id: UUID):
    """
    Restore a snapshot from the project.
    """

    controller = Controller.instance()
    project = controller.get_project(str(project_id))
    snapshot = project.get_snapshot(str(snapshot_id))
    project = await snapshot.restore()
    return project.__json__()
