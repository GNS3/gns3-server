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

from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller.drawing import Drawing
from gns3server.controller.project import Project

pytestmark = pytest.mark.asyncio


async def test_create_drawing(app: FastAPI, client: AsyncClient, project: Project) -> None:

    params = {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }

    response = await client.post(app.url_path_for("create_drawing", project_id=project.id), json=params)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["drawing_id"] is not None


async def test_get_drawing(app: FastAPI, client: AsyncClient, project: Project) -> None:

    params = {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }

    response = await client.post(app.url_path_for("create_drawing", project_id=project.id), json=params)
    response = await client.get(app.url_path_for(
        "get_drawing",
        project_id=project.id,
        drawing_id=response.json()["drawing_id"])
    )
    assert response.status_code == 200
    assert response.json()["x"] == 10


async def test_update_drawing(app: FastAPI, client: AsyncClient, project: Project) -> None:

    params = {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }

    response = await client.post(app.url_path_for("create_drawing", project_id=project.id), json=params)
    response = await client.put(app.url_path_for(
        "update_drawing",
        project_id=project.id,
        drawing_id=response.json()["drawing_id"]),
        json={"x": 42}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["x"] == 42


async def test_all_drawings(app: FastAPI, client: AsyncClient, project: Project) -> None:

    params = {
        "svg": '<svg height="210" width="500"><line x1="0" y1="0" x2="200" y2="200" style="stroke:rgb(255,0,0);stroke-width:2" /></svg>',
        "x": 10,
        "y": 20,
        "z": 0
    }

    await client.post(app.url_path_for("create_drawing", project_id=project.id), json=params)
    response = await client.get(app.url_path_for("get_drawings", project_id=project.id))
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 1


async def test_delete_drawing(app: FastAPI, client: AsyncClient, project: Project) -> None:

    drawing = Drawing(project)
    project._drawings = {drawing.id: drawing}
    response = await client.delete(app.url_path_for(
        "delete_drawing",
        project_id=project.id,
        drawing_id=drawing.id)
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert drawing.id not in project.drawings
