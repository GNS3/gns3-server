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

import os
import uuid
import pytest


@pytest.fixture
def project(http_controller, controller):
    u = str(uuid.uuid4())
    query = {"name": "test", "project_id": u}
    response = http_controller.post("/projects", query)
    project = controller.get_project(u)

    return project


@pytest.fixture
def snapshot(project, async_run):
    snapshot = async_run(project.snapshot("test"))
    return snapshot


def test_list_snapshots(http_controller, project, snapshot):
    response = http_controller.get("/projects/{}/snapshots".format(project.id), example=True)
    assert response.status == 200
    assert len(response.json) == 1


def test_delete_snapshot(http_controller, project, snapshot):
    response = http_controller.delete("/projects/{}/snapshots/{}".format(project.id, snapshot.id), example=True)
    assert response.status == 204
    assert not os.path.exists(snapshot.path)


def test_restore_snapshot(http_controller, project, snapshot):
    response = http_controller.post("/projects/{}/snapshots/{}/restore".format(project.id, snapshot.id), example=True)
    assert response.status == 201
    assert response.json["name"] == project.name


def test_create_snapshot(http_controller, project):
    response = http_controller.post("/projects/{}/snapshots".format(project.id), {"name": "snap1"}, example=True)
    assert response.status == 201
    assert len(os.listdir(os.path.join(project.path, "snapshots"))) == 1
