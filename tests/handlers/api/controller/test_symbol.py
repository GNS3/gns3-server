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
import urllib.parse


async def test_symbols(controller_api):

    response = await controller_api.get('/symbols')

    assert response.status == 200
    assert {
        'symbol_id': ':/symbols/classic/firewall.svg',
        'filename': 'firewall.svg',
        'builtin': True,
        'theme': 'Classic'
    } in response.json


async def test_get(controller_api, controller):

    controller.symbols.theme = "Classic"
    response = await controller_api.get('/symbols/' + urllib.parse.quote(':/symbols/classic/firewall.svg') + '/raw')
    assert response.status == 200
    assert response.headers['CONTENT-TYPE'] == 'image/svg+xml'
    assert response.headers['CONTENT-LENGTH'] == '9381'
    assert '</svg>' in response.html

    # Reply with the default symbol
    response = await controller_api.get('/symbols/404.png/raw')
    assert response.status == 200


async def test_upload(controller_api, symbols_dir):

    response = await controller_api.post("/symbols/test2/raw", body="TEST", raw=True)
    assert response.status == 204

    with open(os.path.join(symbols_dir, "test2")) as f:
        assert f.read() == "TEST"

    response = await controller_api.get('/symbols/test2/raw')
    assert response.status == 200
