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

"""
This test suite check /version endpoint
It's also used for unittest the HTTP implementation.
"""

from tests.utils import asyncio_patch
from tests.api.base import server, loop
from gns3server.version import __version__


def test_version_output(server):
    response = server.get('/version', example=True)
    assert response.status == 200
    assert response.json == {'version': __version__}


def test_version_input(server):
    query = {'version': __version__}
    response = server.post('/version', query, example=True)
    assert response.status == 200
    assert response.json == {'version': __version__}


def test_version_invalid_input(server):
    query = {'version': "0.4.2"}
    response = server.post('/version', query)
    assert response.status == 409
    assert response.json == {'message': '409: Invalid version', 'status': 409}


def test_version_invalid_input_schema(server):
    query = {'version': "0.4.2", "bla": "blu"}
    response = server.post('/version', query)
    assert response.status == 400


def test_version_invalid_output_schema(server):
    with asyncio_patch("gns3server.handlers.version_handler.VersionHandler", return_value={}):
        query = {'version': __version__}
        response = server.post('/version', query)
        assert response.status == 400


def test_version_invalid_json(server):
    query = "BOUM"
    response = server.post('/version', query, raw=True)
    assert response.status == 400
