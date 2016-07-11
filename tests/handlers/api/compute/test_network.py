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
import pytest


def test_udp_allocation(http_compute, project):
    response = http_compute.post('/projects/{}/ports/udp'.format(project.id), {}, example=True)
    assert response.status == 201
    assert response.json['udp_port'] is not None


# Netfifaces is not available on Travis
@pytest.mark.skipif(os.environ.get("TRAVIS", False) is not False, reason="Not supported on Travis")
def test_interfaces(http_compute):
    response = http_compute.get('/network/interfaces', example=True)
    assert response.status == 200
    assert isinstance(response.json, list)
