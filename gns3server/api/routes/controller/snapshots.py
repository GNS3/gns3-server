#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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
API routes for snapshots.
"""

import logging

log = logging.getLogger()

from fastapi import APIRouter, Depends, Response, status
from typing import List
from uuid import UUID

from gns3server.controller.project import Project
from gns3server import schemas
from gns3server.controller import Controller

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or snapshot"}}

router = APIRouter(responses=responses)


def dep_project(project_id: UUID) -> Project:
    """
    Dependency to retrieve a project.
    """

    project = Controller.instance().get_project(str(project_id))
    return project


@router.post("", status_code=status.HTTP_201_CREATED, response_model=schemas.Snapshot)
async def create_snapshot(
        snapshot_data: schemas.SnapshotCreate,
        project: Project = Depends(dep_project)
) -> schemas.Snapshot:
    """
    Create a new snapshot of a project.
    """

    snapshot = await project.snapshot(snapshot_data.name)
    return snapshot.asdict()


@router.get("", response_model=List[schemas.Snapshot], response_model_exclude_unset=True)
def get_snapshots(project: Project = Depends(dep_project)) -> List[schemas.Snapshot]:
    """
    Return all snapshots belonging to a given project.
    """

    snapshots = [s for s in project.snapshots.values()]
    return [s.asdict() for s in sorted(snapshots, key=lambda s: (s.created_at, s.name))]


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_snapshot(snapshot_id: UUID, project: Project = Depends(dep_project)) -> None:
    """
    Delete a snapshot.
    """

    await project.delete_snapshot(str(snapshot_id))


@router.post("/{snapshot_id}/restore", status_code=status.HTTP_201_CREATED, response_model=schemas.Project)
async def restore_snapshot(snapshot_id: UUID, project: Project = Depends(dep_project)) -> schemas.Project:
    """
    Restore a snapshot.
    """

    snapshot = project.get_snapshot(str(snapshot_id))
    project = await snapshot.restore()
    return project.asdict()
