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

from unittest.mock import patch

from gns3server.version import __version__
from gns3server.controller import Controller
from gns3server.utils.get_resource import get_resource


def get_static(filename):

    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.abspath(os.path.join(current_dir, '../..', '..', 'gns3server', 'static')), filename)


@pytest.mark.asyncio
async def test_debug(http_client):

    async with http_client as client:
        response = await client.get('/debug')
        assert response.status_code == 200
        html = response.text
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


@pytest.mark.asyncio
async def test_web_ui(http_client):

    async with http_client as client:
        response = await client.get('/static/web-ui/index.html')
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_web_ui_not_found(http_client, tmpdir):

    with patch('gns3server.utils.get_resource.get_resource') as mock:
        mock.return_value = str(tmpdir)
        async with http_client as client:
            response = await client.get('/static/web-ui/not-found.txt')
            # should serve web-ui/index.html
            assert response.status_code == 200
