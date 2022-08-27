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


@pytest.fixture
async def project(controller_api, controller):

    u = str(uuid.uuid4())
    params = {"name": "test", "project_id": u}
    await controller_api.post("/projects", params)
    project = controller.get_project(u)
    return project


@pytest.fixture
async def snapshot(project):

    snapshot = await project.snapshot("test")
    return snapshot


async def test_list_snapshots(controller_api, project, snapshot):

    assert snapshot.name == "test"
    response = await controller_api.get("/projects/{}/snapshots".format(project.id))
    assert response.status == 200
    assert len(response.json) == 1


async def test_delete_snapshot(controller_api, project, snapshot):

    response = await controller_api.delete("/projects/{}/snapshots/{}".format(project.id, snapshot.id))
    assert response.status == 204
    assert not os.path.exists(snapshot.path)


async def test_restore_snapshot(controller_api, project, snapshot):

    response = await controller_api.post("/projects/{}/snapshots/{}/restore".format(project.id, snapshot.id))
    assert response.status == 201
    assert response.json["name"] == project.name


async def test_create_snapshot(controller_api, project):

    response = await controller_api.post("/projects/{}/snapshots".format(project.id), {"name": "snap1"})
    assert response.status == 201
    assert len(os.listdir(os.path.join(project.path, "snapshots"))) == 1
