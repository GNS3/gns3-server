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

import uuid
import pytest
from unittest.mock import MagicMock
from tests.utils import asyncio_patch

from gns3server.compute.builtin.nodes.nat import Nat
from gns3server.compute.vpcs import VPCS


def test_init(on_gns3vm, project):
    nat1 = Nat("nat1", str(uuid.uuid4()), project, MagicMock())
    nat2 = Nat("nat2", str(uuid.uuid4()), project, MagicMock())
    assert nat1.ports_mapping[0]["interface"] != nat2.ports_mapping[0]["interface"]


def test_json(on_gns3vm, project):
    nat = Nat("nat1", str(uuid.uuid4()), project, MagicMock())
    assert nat.__json__() == {
        "name": "nat1",
        "node_id": nat.id,
        "project_id": project.id,
        "status": "started",
        "ports_mapping": [
            {
                "interface": nat._interface,
                "name": "nat0",
                "port_number": 0,
                "type": "tap"
            }
        ]
    }


def test_add_nio(on_gns3vm, project, async_run):
    nio = VPCS.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
    nat = Nat("nat1", str(uuid.uuid4()), project, MagicMock())
    with asyncio_patch("gns3server.compute.builtin.nodes.cloud.Cloud.add_nio") as cloud_add_nio_mock:
        with asyncio_patch("gns3server.compute.base_node.BaseNode._ubridge_send") as nat_ubridge_send_mock:
            async_run(nat.add_nio(0, nio))
    assert cloud_add_nio_mock.called
    nat_ubridge_send_mock.assert_called_with("brctl addif virbr0 \"{}\"".format(nat._interface))
