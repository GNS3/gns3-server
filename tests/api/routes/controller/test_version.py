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

from gns3server.version import __version__

pytestmark = pytest.mark.asyncio


async def test_version_output(app: FastAPI, client: AsyncClient) -> None:

    response = await client.get(app.url_path_for("get_version"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'controller_host': '127.0.0.1', 'local': False, 'version': __version__}


async def test_version_input(app: FastAPI, client: AsyncClient) -> None:

    params = {'version': __version__}
    response = await client.post(app.url_path_for("check_version"), json=params)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'version': __version__}


async def test_version_invalid_input(app: FastAPI, client: AsyncClient) -> None:

    params = {'version': "0.4.2"}
    response = await client.post(app.url_path_for("check_version"), json=params)
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {'message': 'Client version 0.4.2 is not the same as server version {}'.format(__version__)}


async def test_version_invalid_input_schema(app: FastAPI, client: AsyncClient) -> None:

    params = {'version': "0.4.2", "bla": "blu"}
    response = await client.post(app.url_path_for("check_version"), json=params)
    assert response.status_code == status.HTTP_409_CONFLICT


async def test_version_invalid_json(app: FastAPI, client: AsyncClient) -> None:

    params = "BOUM"
    response = await client.post(app.url_path_for("check_version"), json=params)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
