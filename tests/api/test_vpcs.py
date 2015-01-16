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

from unittest.mock import patch
from tests.api.base import server, loop, port_manager
from tests.utils import asyncio_patch
from gns3server import modules


@asyncio_patch('gns3server.modules.VPCS.create_vm', return_value=84)
def test_vpcs_create(server):
    response = server.post('/vpcs', {'name': 'PC TEST 1'}, example=False)
    assert response.status == 200
    assert response.route == '/vpcs'
    assert response.json['name'] == 'PC TEST 1'
    assert response.json['vpcs_id'] == 84


def test_vpcs_nio_create_udp(server):
    vm = server.post('/vpcs', {'name': 'PC TEST 1'})
    response = server.post('/vpcs/{}/ports/0/nio'.format(vm.json["vpcs_id"]), {
            'type': 'nio_udp',
            'lport': 4242,
            'rport': 4343,
            'rhost': '127.0.0.1'
        },
        example=True)
    assert response.status == 200
    assert response.route == '/vpcs/{vpcs_id}/ports/{port_id}/nio'
    assert response.json['type'] == 'nio_udp'

@patch("gns3server.modules.vpcs.vpcs_device.has_privileged_access", return_value=True)
def test_vpcs_nio_create_tap(mock, server):
    vm = server.post('/vpcs', {'name': 'PC TEST 1'})
    response = server.post('/vpcs/{}/ports/0/nio'.format(vm.json["vpcs_id"]), {
            'type': 'nio_tap',
            'tap_device': 'test',
        })
    assert response.status == 200
    assert response.route == '/vpcs/{vpcs_id}/ports/{port_id}/nio'
    assert response.json['type'] == 'nio_tap'

def test_vpcs_delete_nio(server):
    vm = server.post('/vpcs', {'name': 'PC TEST 1'})
    response = server.post('/vpcs/{}/ports/0/nio'.format(vm.json["vpcs_id"]), {
            'type': 'nio_udp',
            'lport': 4242,
            'rport': 4343,
            'rhost': '127.0.0.1'
        },
        )
    response = server.delete('/vpcs/{}/ports/0/nio'.format(vm.json["vpcs_id"]))
    assert response.status == 200
    assert response.route == '/vpcs/{vpcs_id}/ports/{port_id}/nio'


