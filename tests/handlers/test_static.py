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


import aiohttp
import os
from unittest.mock import patch


def test_get(http_root):
    response = http_root.get('/static/builtin_symbols/firewall.svg')
    assert response.status == 200
    assert response.headers['CONTENT-LENGTH'] == '9381'
    assert response.headers['CONTENT-TYPE'] == 'image/svg+xml'
    assert '</svg>' in response.html

    response = http_root.get('/static/builtin_symbols/../main.py')
    assert response.status == 404

    response = http_root.get('/static/builtin_symbols/404.png')
    assert response.status == 404
