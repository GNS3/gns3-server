#!/usr/bin/env python
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

import uuid
from unittest.mock import MagicMock, patch

from gns3server.compute.builtin.nodes.nat import Nat


def test_json_gns3vm(on_gns3vm, compute_project):

    nat = Nat("nat1", str(uuid.uuid4()), compute_project, MagicMock())
    assert nat.asdict() == {
        "name": "nat1",
        "usage": "",
        "node_id": nat.id,
        "project_id": compute_project.id,
        "status": "started",
        "ports_mapping": [
            {
                "interface": "virbr0",
                "name": "nat0",
                "port_number": 0,
                "type": "ethernet"
            }
        ]
    }


def test_json_darwin(darwin_platform, compute_project):

    with patch("gns3server.utils.interfaces.interfaces", return_value=[
            {"name": "eth0", "special": False, "type": "ethernet"},
            {"name": "vmnet8", "special": True, "type": "ethernet"}]):
        nat = Nat("nat1", str(uuid.uuid4()), compute_project, MagicMock())
    assert nat.asdict() == {
        "name": "nat1",
        "usage": "",
        "node_id": nat.id,
        "project_id": compute_project.id,
        "status": "started",
        "ports_mapping": [
            {
                "interface": "vmnet8",
                "name": "nat0",
                "port_number": 0,
                "type": "ethernet"
            }
        ]
    }


def test_json_windows_with_full_name_of_interface(windows_platform, project):
    with patch("gns3server.utils.interfaces.interfaces", return_value=[
            {"name": "VMware Network Adapter VMnet8", "special": True, "type": "ethernet"}]):
        nat = Nat("nat1", str(uuid.uuid4()), project, MagicMock())
    assert nat.asdict() == {
        "name": "nat1",
        "usage": "",
        "node_id": nat.id,
        "project_id": project.id,
        "status": "started",
        "ports_mapping": [
            {
                "interface": "VMware Network Adapter VMnet8",
                "name": "nat0",
                "port_number": 0,
                "type": "ethernet"
            }
        ]
    }
