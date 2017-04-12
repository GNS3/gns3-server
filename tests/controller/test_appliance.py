#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

from gns3server.controller.appliance import Appliance


def test_appliance_json():
    a = Appliance(None, {
        "node_type": "qemu",
        "name": "Test",
        "default_name_format": "{name}-{0}",
        "category": 0,
        "symbol": "qemu.svg",
        "server": "local"
    })
    assert a.__json__() == {
        "appliance_id": a.id,
        "node_type": "qemu",
        "builtin": False,
        "name": "Test",
        "default_name_format": "{name}-{0}",
        "category": "router",
        "symbol": "qemu.svg",
        "compute_id": "local"
    }
