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
import sys
import pytest

from gns3server.config import Config

from gns3server.version import __version__


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_get(http_compute, windows_platform):
    """
    Nat, is supported outside linux
    """
    response = http_compute.get('/capabilities', example=True)
    assert response.status == 200
    assert response.json == {'node_types': ['cloud', 'ethernet_hub', 'ethernet_switch', 'vpcs', 'virtualbox', 'dynamips', 'frame_relay_switch', 'atm_switch', 'qemu', 'vmware', 'docker', 'iou'], 'version': __version__, 'platform': sys.platform}


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
def test_get_on_gns3vm(http_compute, on_gns3vm):
    response = http_compute.get('/capabilities', example=True)
    assert response.status == 200
    assert response.json == {'node_types': ['cloud', 'ethernet_hub', 'ethernet_switch', 'nat', 'vpcs', 'virtualbox', 'dynamips', 'frame_relay_switch', 'atm_switch', 'qemu', 'vmware', 'docker', 'iou'], 'version': __version__, 'platform': sys.platform}
