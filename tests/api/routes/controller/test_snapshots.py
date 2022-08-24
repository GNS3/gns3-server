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

import os
import uuid
import pytest
import pytest_asyncio

from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller import Controller
from gns3server.controller.project import Project
from gns3server.controller.snapshot import Snapshot

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def project(app: FastAPI, client: AsyncClient, controller: Controller) -> Project:

    u = str(uuid.uuid4())
    params = {"name": "test", "project_id": u}
    await client.post(app.url_path_for("create_project"), json=params)
    project = controller.get_project(u)
    return project


@pytest_asyncio.fixture
async def snapshot(project: Project):

    snapshot = await project.snapshot("test")
    return snapshot


async def test_list_snapshots(app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot) -> None:

    assert snapshot.name == "test"
    response = await client.get(app.url_path_for("get_snapshots", project_id=project.id))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1


async def test_delete_snapshot(app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot) -> None:

    response = await client.delete(app.url_path_for("delete_snapshot", project_id=project.id, snapshot_id=snapshot.id))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not os.path.exists(snapshot.path)


async def test_restore_snapshot(app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot) -> None:

    response = await client.post(app.url_path_for("restore_snapshot", project_id=project.id, snapshot_id=snapshot.id))
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["name"] == project.name


async def test_create_snapshot(app: FastAPI, client: AsyncClient, project: Project) -> None:

    response = await client.post(app.url_path_for("create_snapshot", project_id=project.id), json={"name": "snap1"})
    assert response.status_code == status.HTTP_201_CREATED
    assert len(os.listdir(os.path.join(project.path, "snapshots"))) == 1
