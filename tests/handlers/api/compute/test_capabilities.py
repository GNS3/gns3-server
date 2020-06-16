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


import sys
import pytest

from gns3server.version import __version__


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_get(compute_api, windows_platform):

    response = await compute_api.get('/capabilities')
    assert response.status == 200
    assert response.json == {'node_types': ['cloud', 'ethernet_hub', 'ethernet_switch', 'nat', 'vpcs', 'virtualbox', 'dynamips', 'frame_relay_switch', 'atm_switch', 'qemu', 'vmware', 'traceng', 'docker', 'iou'], 'version': __version__, 'platform': sys.platform}


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_get_on_gns3vm(compute_api, on_gns3vm):

    response = await compute_api.get('/capabilities')
    assert response.status == 200
    assert response.json == {'node_types': ['cloud', 'ethernet_hub', 'ethernet_switch', 'nat', 'vpcs', 'virtualbox', 'dynamips', 'frame_relay_switch', 'atm_switch', 'qemu', 'vmware', 'traceng', 'docker', 'iou'], 'version': __version__, 'platform': sys.platform}
