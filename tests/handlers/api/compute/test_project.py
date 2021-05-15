# -*- coding: utf-8 -*-
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

import pytest
import uuid
import os

from unittest.mock import patch
from tests.utils import asyncio_patch

from gns3server.handlers.api.compute.project_handler import ProjectHandler
from gns3server.compute.project_manager import ProjectManager


@pytest.fixture
def base_params(tmpdir):
    """Return standard parameters"""

    params = {
        "name": "test",
        "path": str(tmpdir),
        "project_id": str(uuid.uuid4())
    }
    return params


async def test_create_project_with_path(compute_api, base_params):

    with patch("gns3server.compute.project.Project.is_local", return_value=True):
        response = await compute_api.post("/projects", base_params)
        assert response.status == 201
        assert response.json["project_id"] == base_params["project_id"]


async def test_create_project_with_path_and_empty_variables(compute_api, base_params):

    base_params["variables"] = None
    with patch("gns3server.compute.project.Project.is_local", return_value=True):

        response = await compute_api.post("/projects", base_params)
        assert response.status == 201
        assert response.json["project_id"] == base_params["project_id"]


async def test_create_project_without_dir(compute_api, base_params):

    del base_params["path"]
    response = await compute_api.post("/projects", base_params)
    assert response.status == 201
    assert response.json["project_id"] == base_params["project_id"]
    assert response.json["name"] == base_params["name"]


async def test_show_project(compute_api, base_params):

    response = await compute_api.post("/projects", base_params)
    assert response.status == 201
    response = await compute_api.get("/projects/{project_id}".format(project_id=base_params["project_id"]))
    assert len(response.json.keys()) == 3
    assert response.json["project_id"] == base_params["project_id"]
    assert response.json["name"] == base_params["name"]
    assert response.json["variables"] is None


async def test_show_project_invalid_uuid(compute_api):

    response = await compute_api.get("/projects/50010203-0405-0607-0809-0a0b0c0d0e42")
    assert response.status == 404


async def test_list_projects(compute_api):

    ProjectManager.instance()._projects = {}

    params = {"name": "test", "project_id": "51010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = await compute_api.post("/projects", params)
    assert response.status == 201
    params = {"name": "test", "project_id": "52010203-0405-0607-0809-0a0b0c0d0e0b"}
    response = await compute_api.post("/projects", params)
    assert response.status == 201

    response = await compute_api.get("/projects")
    assert response.status == 200
    assert len(response.json) == 2
    assert "51010203-0405-0607-0809-0a0b0c0d0e0f" in [p["project_id"] for p in response.json]


async def test_delete_project(compute_api, compute_project):

    with asyncio_patch("gns3server.compute.project.Project.delete", return_value=True) as mock:
        response = await compute_api.delete("/projects/{project_id}".format(project_id=compute_project.id))
        assert response.status == 204
        assert mock.called


async def test_update_project(compute_api, base_params):

    response = await compute_api.post("/projects", base_params)
    assert response.status == 201

    params = {"variables": [{"name": "TEST1", "value": "VAL1"}]}
    response = await compute_api.put("/projects/{project_id}".format(project_id=base_params["project_id"]), params)
    assert response.status == 200
    assert response.json["variables"] == [{"name": "TEST1", "value": "VAL1"}]


async def test_delete_project_invalid_uuid(compute_api):

    response = await compute_api.delete("/projects/{project_id}".format(project_id=uuid.uuid4()))
    assert response.status == 404


async def test_close_project(compute_api, compute_project):

    with asyncio_patch("gns3server.compute.project.Project.close", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/close".format(project_id=compute_project.id))
        assert response.status == 204
        assert mock.called


async def test_close_project_two_client_connected(compute_api, compute_project):

    ProjectHandler._notifications_listening = {compute_project.id: 2}
    with asyncio_patch("gns3server.compute.project.Project.close", return_value=True) as mock:
        response = await compute_api.post("/projects/{project_id}/close".format(project_id=compute_project.id))
        assert response.status == 204
        assert not mock.called


async def test_close_project_invalid_uuid(compute_api):

    response = await compute_api.post("/projects/{project_id}/close".format(project_id=uuid.uuid4()))
    assert response.status == 404


async def test_get_file(compute_api, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"projects_path": str(tmpdir)}):
        project = ProjectManager.instance().create_project(project_id="01010203-0405-0607-0809-0a0b0c0d0e0b")

    with open(os.path.join(project.path, "hello"), "w+") as f:
        f.write("world")

    response = await compute_api.get("/projects/{project_id}/files/hello".format(project_id=project.id), raw=True)
    assert response.status == 200
    assert response.body == b"world"

    response = await compute_api.get("/projects/{project_id}/files/false".format(project_id=project.id), raw=True)
    assert response.status == 404

    response = await compute_api.get("/projects/{project_id}/files/../hello".format(project_id=project.id), raw=True)
    assert response.status == 404


async def test_write_file(compute_api, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"projects_path": str(tmpdir)}):
        project = ProjectManager.instance().create_project(project_id="01010203-0405-0607-0809-0a0b0c0d0e0b")

    response = await compute_api.post("/projects/{project_id}/files/hello".format(project_id=project.id), body="world", raw=True)
    assert response.status == 201

    with open(os.path.join(project.path, "hello")) as f:
        assert f.read() == "world"

    response = await compute_api.post("/projects/{project_id}/files/../hello".format(project_id=project.id), raw=True)
    assert response.status == 404


async def test_stream_file(compute_api, tmpdir):

    with patch("gns3server.config.Config.get_section_config", return_value={"projects_path": str(tmpdir)}):
        project = ProjectManager.instance().create_project(project_id="01010203-0405-0607-0809-0a0b0c0d0e0b")

    with open(os.path.join(project.path, "hello"), "w+") as f:
        f.write("world")

    response = await compute_api.get("/projects/{project_id}/files/hello".format(project_id=project.id), raw=True)
    assert response.status == 200
    assert response.body == b"world"

    response = await compute_api.get("/projects/{project_id}/files/false".format(project_id=project.id), raw=True)
    assert response.status == 404

    response = await compute_api.get("/projects/{project_id}/files/../hello".format(project_id=project.id), raw=True)
    assert response.status == 404
