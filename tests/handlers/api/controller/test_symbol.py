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

import os
import sys
import urllib.parse

from gns3server.config import Config


def test_symbols(http_controller):
    response = http_controller.get('/symbols', example=True)
    assert response.status == 200
    assert {
        'symbol_id': ':/symbols/firewall.svg',
        'filename': 'firewall.svg',
        'builtin': True
    } in response.json


def test_get(http_controller):
    response = http_controller.get('/symbols/' + urllib.parse.quote(':/symbols/firewall.svg') + '/raw')
    assert response.status == 200
    assert response.headers['CONTENT-LENGTH'] == '9381'
    assert response.headers['CONTENT-TYPE'] == 'image/svg+xml'
    assert '</svg>' in response.html

    # Reply by the default symbol
    response = http_controller.get('/symbols/404.png/raw')
    assert response.status == 200


def test_upload(http_controller, symbols_dir):
    response = http_controller.post("/symbols/test2/raw", body="TEST", raw=True)
    assert response.status == 204

    with open(os.path.join(symbols_dir, "test2")) as f:
        assert f.read() == "TEST"

    response = http_controller.get('/symbols/test2/raw')
    assert response.status == 200
