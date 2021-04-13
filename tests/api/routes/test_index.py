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
import os

from fastapi import FastAPI, status
from httpx import AsyncClient
from unittest.mock import patch

from gns3server.version import __version__
from gns3server.controller import Controller
from gns3server.utils.get_resource import get_resource

pytestmark = pytest.mark.asyncio


def get_static(filename):

    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.abspath(os.path.join(current_dir, '../..', '..', 'gns3server', 'static')), filename)


async def test_debug(app: FastAPI, client: AsyncClient) -> None:

    response = await client.get(app.url_path_for("debug"))
    assert response.status_code == status.HTTP_200_OK
    html = response.read().decode()
    assert "Website" in html
    assert __version__ in html


# @pytest.mark.asyncio
# async def test_controller(http_client, controller):
#
#     await controller.add_project(name="test")
#     response = await http_client.get('/controller')
#     assert "test" in await response.text()
#     assert response.status_code == 200
#
#
# @pytest.mark.asyncio
# async def test_compute(http_client):
#
#     response = await http_client.get('/compute')
#     assert response.status_code == 200


# @pytest.mark.asyncio
# async def test_project(http_client, controller):
#
#     project = await controller.add_project(name="test")
#     response = await http_client.get('/projects/{}'.format(project.id))
#     assert response.status_code == 200


async def test_web_ui(app: FastAPI, client: AsyncClient) -> None:

    response = await client.get(app.url_path_for("web_ui", file_path="index.html"))
    assert response.status_code == status.HTTP_200_OK


async def test_web_ui_not_found(app: FastAPI, client: AsyncClient, tmpdir: str) -> None:

    with patch('gns3server.utils.get_resource.get_resource') as mock:
        mock.return_value = str(tmpdir)
        response = await client.get(app.url_path_for("web_ui", file_path="not-found.txt"))
        # should serve web-ui/index.html
        assert response.status_code == status.HTTP_200_OK
