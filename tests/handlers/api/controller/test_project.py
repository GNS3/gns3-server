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
import json


from unittest.mock import patch
from tests.utils import asyncio_patch

from gns3server.handlers.api.controller.project_handler import ProjectHandler
from gns3server.controller import Controller


@pytest.fixture
def project(http_controller, controller):
    u = str(uuid.uuid4())
    query = {"name": "test", "project_id": u}
    response = http_controller.post("/projects", query)
    return controller.get_project(u)


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
    assert response.json["name"] == "test"


def test_create_project_with_uuid(http_controller):
    query = {"name": "test", "project_id": "30010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = http_controller.post("/projects", query)
    assert response.status == 201
    assert response.json["project_id"] == "30010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["name"] == "test"


def test_list_projects(http_controller, tmpdir):
    http_controller.post("/projects", {"name": "test", "path": str(tmpdir), "project_id": "00010203-0405-0607-0809-0a0b0c0d0e0f"})
    response = http_controller.get("/projects", example=True)
    assert response.status == 200
    projects = response.json
    assert projects[0]["name"] == "test"


def test_get_project(http_controller, project):
    response = http_controller.get("/projects/{project_id}".format(project_id=project.id), example=True)
    assert response.status == 200
    assert response.json["name"] == "test"


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


def test_notification(http_controller, project, controller, loop):
    @asyncio.coroutine
    def go(future):
        response = yield from aiohttp.request("GET", http_controller.get_url("/projects/{project_id}/notifications".format(project_id=project.id)))
        response.body = yield from response.content.read(200)
        controller.notification.emit("node.created", {"a": "b"})
        response.body += yield from response.content.read(50)
        response.close()
        future.set_result(response)

    future = asyncio.Future()
    asyncio.async(go(future))
    response = loop.run_until_complete(future)
    assert response.status == 200
    assert b'"action": "ping"' in response.body
    assert b'"cpu_usage_percent"' in response.body
    assert b'{"action": "node.created", "event": {"a": "b"}}\n' in response.body


def test_notification_invalid_id(http_controller):
    response = http_controller.get("/projects/{project_id}/notifications".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_notification_ws(http_controller, controller, project, async_run):
    ws = http_controller.websocket("/projects/{project_id}/notifications/ws".format(project_id=project.id))
    answer = async_run(ws.receive())
    answer = json.loads(answer.data)
    assert answer["action"] == "ping"

    controller.notification.emit("test", {})

    answer = async_run(ws.receive())
    answer = json.loads(answer.data)
    assert answer["action"] == "test"

    async_run(http_controller.close())
