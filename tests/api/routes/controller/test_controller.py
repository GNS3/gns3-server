#!/usr/bin/env python
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
from unittest.mock import MagicMock

from gns3server.config import Config

pytestmark = pytest.mark.asyncio


async def test_shutdown_local(app: FastAPI, client: AsyncClient, config: Config) -> None:

    os.kill = MagicMock()
    config.settings.Server.local = True
    response = await client.post(app.url_path_for("shutdown"))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert os.kill.called


async def test_shutdown_non_local(app: FastAPI, client: AsyncClient, config: Config) -> None:

    response = await client.post(app.url_path_for("shutdown"))
    assert response.status_code == status.HTTP_403_FORBIDDEN


# @pytest.mark.asyncio
# async def test_debug(controller_api, config, tmpdir):
#
#     config._main_config_file = str(tmpdir / "test.conf")
#     config.set("Server", "local", True)
#     response = await controller_api.post('/debug')
#     assert response.status_code == 201
#     debug_dir = os.path.join(config.config_dir, "debug")
#     assert os.path.exists(debug_dir)
#     assert os.path.exists(os.path.join(debug_dir, "controller.txt"))
#
#
# @pytest.mark.asyncio
# async def test_debug_non_local(controller_api, config, tmpdir):
#
#     config._main_config_file = str(tmpdir / "test.conf")
#     config.set("Server", "local", False)
#     response = await controller_api.post('/debug')
#     assert response.status_code == 403


async def test_statistics_output(app: FastAPI, client: AsyncClient) -> None:

    response = await client.get(app.url_path_for("statistics"))
    assert response.status_code == status.HTTP_200_OK
