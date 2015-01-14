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

from tests.api.base import server, loop
from tests.utils import asyncio_patch
from gns3server import modules


def test_vpcs_create(server):
    response = server.post('/vpcs', {'name': 'PC TEST 1'}, example=True)
    assert response.status == 200
    assert response.route == '/vpcs'
    assert response.json['name'] == 'PC TEST 1'
    assert response.json['vpcs_id'] == 42


@asyncio_patch('demoserver.modules.VPCS.create', return_value=84)
def test_vpcs_mock(server, mock):
    response = server.post('/vpcs', {'name': 'PC TEST 1'}, example=False)
    assert response.status == 200
    assert response.route == '/vpcs'
    assert response.json['name'] == 'PC TEST 1'
    assert response.json['vpcs_id'] == 84


def test_vpcs_nio_create(server):
    response = server.post('/vpcs/42/nio', {
        'id': 42,
        'nio': {
            'type': 'nio_unix',
            'local_file': '/tmp/test',
            'remote_file': '/tmp/remote'
        },
        'port': 0,
        'port_id': 0},
        example=True)
    assert response.status == 200
    assert response.route == '/vpcs/{vpcs_id}/nio'
    assert response.json['name'] == 'PC 2'
