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

import os
import pytest

from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.version import __version__
from gns3server.compute.project import Project

pytestmark = pytest.mark.asyncio


async def test_udp_allocation(app: FastAPI, compute_client: AsyncClient, compute_project: Project) -> None:

    response = await compute_client.post(app.url_path_for("compute:allocate_udp_port", project_id=compute_project.id), json={})
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['udp_port'] is not None


async def test_interfaces(app: FastAPI, compute_client: AsyncClient) -> None:

    response = await compute_client.get(app.url_path_for("compute:network_interfaces"))
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.json(), list)


async def test_version_output(app: FastAPI, compute_client: AsyncClient) -> None:

    response = await compute_client.get(app.url_path_for("compute:compute_version"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'version': __version__}


async def test_compute_authentication(app: FastAPI, compute_client: AsyncClient) -> None:

    response = await compute_client.get(app.url_path_for("compute:compute_version"), auth=("admin", "invalid_password"))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# @pytest.mark.asyncio
# async def test_debug_output(compute_api):
#
#     response = await compute_api.get('/debug')
#     assert response.status_code == 200


async def test_statistics_output(app: FastAPI, compute_client: AsyncClient) -> None:

    response = await compute_client.get(app.url_path_for("compute:compute_statistics"))
    assert response.status_code == status.HTTP_200_OK
