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
import urllib.parse

from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller import Controller

pytestmark = pytest.mark.asyncio


async def test_symbols(app: FastAPI, client: AsyncClient) -> None:

    response = await client.get(app.url_path_for("get_symbols"))

    assert response.status_code == status.HTTP_200_OK
    assert {
        'symbol_id': ':/symbols/classic/firewall.svg',
        'filename': 'firewall.svg',
        'builtin': True,
        'theme': 'Classic'
    } in response.json()


async def test_get(app: FastAPI, client: AsyncClient, controller: Controller) -> None:

    controller.symbols.theme = "Classic"
    url = app.url_path_for("get_symbol", symbol_id=urllib.parse.quote(':/symbols/classic/firewall.svg'))
    response = await client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.headers['CONTENT-TYPE'] == 'image/svg+xml'
    assert response.headers['CONTENT-LENGTH'] == '9381'
    assert '</svg>' in response.text

    # Reply with the default symbol
    response = await client.get(app.url_path_for("get_symbol", symbol_id="404.png"))
    assert response.status_code == status.HTTP_200_OK


async def test_upload(app: FastAPI, client: AsyncClient, symbols_dir: str) -> None:

    response = await client.post(app.url_path_for("upload_symbol", symbol_id="test2"), content=b"TEST")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    with open(os.path.join(symbols_dir, "test2")) as f:
        assert f.read() == "TEST"

    response = await client.get(app.url_path_for("get_symbol", symbol_id="test2"))
    assert response.status_code == status.HTTP_200_OK
