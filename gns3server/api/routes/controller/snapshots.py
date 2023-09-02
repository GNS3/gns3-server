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

from fastapi import APIRouter, Depends, status
from typing import List
from uuid import UUID

from gns3server.controller.project import Project
from gns3server.db.repositories.rbac import RbacRepository
from gns3server import schemas
from gns3server.controller import Controller

from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

responses = {404: {"model": schemas.ErrorMessage, "description": "Could not find project or snapshot"}}

router = APIRouter(responses=responses)


def dep_project(project_id: UUID) -> Project:
    """
    Dependency to retrieve a project.
    """

    project = Controller.instance().get_project(str(project_id))
    return project


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Snapshot,
    dependencies=[Depends(has_privilege("Snapshot.Allocate"))]
)
async def create_snapshot(
        snapshot_data: schemas.SnapshotCreate,
        project: Project = Depends(dep_project)
) -> schemas.Snapshot:
    """
    Create a new snapshot of a project.

    Required privilege: Snapshot.Allocate
    """

    snapshot = await project.snapshot(snapshot_data.name)
    return snapshot.asdict()


@router.get(
    "",
    response_model=List[schemas.Snapshot],
    response_model_exclude_unset=True,
    dependencies=[Depends(has_privilege("Snapshot.Audit"))]
)
def get_snapshots(project: Project = Depends(dep_project)) -> List[schemas.Snapshot]:
    """
    Return all snapshots belonging to a given project.

    Required privilege: Snapshot.Audit
    """

    snapshots = [s for s in project.snapshots.values()]
    return [s.asdict() for s in sorted(snapshots, key=lambda s: (s.created_at, s.name))]


@router.delete(
    "/{snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Snapshot.Allocate"))]
)
async def delete_snapshot(
        snapshot_id: UUID,
        project: Project = Depends(dep_project),
        rbac_repo=Depends(get_repository(RbacRepository))
) -> None:
    """
    Delete a snapshot.

    Required privilege: Snapshot.Allocate
    """

    await project.delete_snapshot(str(snapshot_id))
    await rbac_repo.delete_all_ace_starting_with_path(f"/projects/{project.id}/snapshots/{snapshot_id}")


@router.post(
    "/{snapshot_id}/restore",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Project,
    dependencies=[Depends(has_privilege("Snapshot.Restore"))]
)
async def restore_snapshot(snapshot_id: UUID, project: Project = Depends(dep_project)) -> schemas.Project:
    """
    Restore a snapshot.

    Required privilege: Snapshot.Restore
    """

    snapshot = project.get_snapshot(str(snapshot_id))
    project = await snapshot.restore()
    return project.asdict()
