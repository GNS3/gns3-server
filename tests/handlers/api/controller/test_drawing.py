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


from gns3server.controller.drawing import Drawing


async def test_create_drawing(controller_api, project):

    params = {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }

    response = await controller_api.post("/projects/{}/drawings".format(project.id), params)
    assert response.status == 201
    assert response.json["drawing_id"] is not None


async def test_get_drawing(controller_api, project):

    params = {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }

    response = await controller_api.post("/projects/{}/drawings".format(project.id), params)
    response = await controller_api.get("/projects/{}/drawings/{}".format(project.id, response.json["drawing_id"]))
    assert response.status == 200
    assert response.json["x"] == 10


async def test_update_drawing(controller_api, project):

    params = {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }

    response = await controller_api.post("/projects/{}/drawings".format(project.id), params)
    response = await controller_api.put("/projects/{}/drawings/{}".format(project.id, response.json["drawing_id"]), {"x": 42})
    assert response.status == 201
    assert response.json["x"] == 42


async def test_list_drawing(controller_api, project):

    params = {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }

    await controller_api.post("/projects/{}/drawings".format(project.id), params)
    response = await controller_api.get("/projects/{}/drawings".format(project.id))
    assert response.status == 200
    assert len(response.json) == 1


async def test_delete_drawing(controller_api, project):

    drawing = Drawing(project)
    project._drawings = {drawing.id: drawing}
    response = await controller_api.delete("/projects/{}/drawings/{}".format(project.id, drawing.id))
    assert response.status == 204
    assert drawing.id not in project.drawings
