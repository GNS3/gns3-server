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

"""
This test suite check /project endpoint
"""

import uuid
import os
import asyncio
import aiohttp
import pytest


from unittest.mock import patch
from tests.utils import asyncio_patch

from gns3server.handlers.api.controller.project_handler import ProjectHandler
from gns3server.controller import Controller


@pytest.fixture
def project(http_controller):
    u = str(uuid.uuid4())
    query = {"name": "test", "project_id": u}
    response = http_controller.post("/projects", query)
    return Controller.instance().getProject(u)


def test_create_project_with_path(http_controller, tmpdir):
    response = http_controller.post("/projects", {"name": "test", "path": str(tmpdir), "project_id": "00010203-0405-0607-0809-0a0b0c0d0e0f"})
    assert response.status == 201
    assert response.json["name"] == "test"
    assert response.json["project_id"] == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_create_project_without_dir(http_controller):
    query = {"name": "test", "project_id": "10010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = http_controller.post("/projects", query, example=True)
    assert response.status == 201
    assert response.json["project_id"] == "10010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["temporary"] is False
    assert response.json["name"] == "test"


def test_create_temporary_project(http_controller):
    query = {"name": "test", "temporary": True, "project_id": "20010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = http_controller.post("/projects", query)
    assert response.status == 201
    assert response.json["project_id"] == "20010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["temporary"] is True
    assert response.json["name"] == "test"


def test_create_project_with_uuid(http_controller):
    query = {"name": "test", "project_id": "30010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = http_controller.post("/projects", query)
    assert response.status == 201
    assert response.json["project_id"] == "30010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["name"] == "test"


def test_commit_project(http_controller, project):
    with asyncio_patch("gns3server.controller.project.Project.commit", return_value=True) as mock:
        response = http_controller.post("/projects/{project_id}/commit".format(project_id=project.id), example=True)
    assert response.status == 204
    assert mock.called


def test_commit_project_invalid_uuid(http_controller):
    response = http_controller.post("/projects/{project_id}/commit".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_delete_project(http_controller, project):
    with asyncio_patch("gns3server.controller.project.Project.delete", return_value=True) as mock:
        response = http_controller.delete("/projects/{project_id}".format(project_id=project.id), example=True)
        assert response.status == 204
        assert mock.called
        assert project not in Controller.instance().projects


def test_delete_project_invalid_uuid(http_controller):
    response = http_controller.delete("/projects/{project_id}".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_close_project(http_controller, project):
    with asyncio_patch("gns3server.controller.project.Project.close", return_value=True) as mock:
        response = http_controller.post("/projects/{project_id}/close".format(project_id=project.id), example=True)
        assert response.status == 204
        assert mock.called
        assert project not in Controller.instance().projects
