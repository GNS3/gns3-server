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

from gns3server.version import __version__


def test_index(server):
    response = server.get('/', api_version=None)
    assert response.status == 200
    html = response.html
    assert "Website" in html
    assert __version__ in html


def test_status(server):
    response = server.get('/status', api_version=None)
    assert response.status == 200
