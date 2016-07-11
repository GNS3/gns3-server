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


from tests.utils import asyncio_patch

from gns3server.handlers.api.controller.project_handler import ProjectHandler
from gns3server.controller import Controller
from gns3server.controller.drawing import Drawing


@pytest.fixture
def project(http_controller, async_run):
    return async_run(Controller.instance().add_project(name="Test"))


def test_create_drawing(http_controller, tmpdir, project, async_run):

    response = http_controller.post("/projects/{}/drawings".format(project.id), {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }, example=True)
    assert response.status == 201
    assert response.json["drawing_id"] is not None


def test_update_drawing(http_controller, tmpdir, project, async_run):

    response = http_controller.post("/projects/{}/drawings".format(project.id), {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    },)
    response = http_controller.put("/projects/{}/drawings/{}".format(project.id, response.json["drawing_id"]), {
        "x": 42,
    }, example=True)
    assert response.status == 201
    assert response.json["x"] == 42


def test_list_drawing(http_controller, tmpdir, project, async_run):
    response = http_controller.post("/projects/{}/drawings".format(project.id), {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }, example=False)
    response = http_controller.get("/projects/{}/drawings".format(project.id), example=True)
    assert response.status == 200
    assert len(response.json) == 1


def test_delete_drawing(http_controller, tmpdir, project, async_run):

    drawing = Drawing(project)
    project._drawings = {drawing.id: drawing}
    response = http_controller.delete("/projects/{}/drawings/{}".format(project.id, drawing.id), example=True)
    assert response.status == 204
    assert drawing.id not in project._drawings
