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

from tests.utils import asyncio_patch


@asyncio_patch("gns3server.modules.VirtualBox.create_vm", return_value="61d61bdd-aa7d-4912-817f-65a9eb54d3ab")
def test_vbox_create(server):
    response = server.post("/virtualbox", {"name": "VM1"}, example=False)
    assert response.status == 200
    assert response.route == "/virtualbox"
    assert response.json["name"] == "VM1"
    assert response.json["uuid"] == "61d61bdd-aa7d-4912-817f-65a9eb54d3ab"


@asyncio_patch("gns3server.modules.VirtualBox.start_vm", return_value=True)
def test_vbox_start(server):
    response = server.post("/virtualbox/61d61bdd-aa7d-4912-817f-65a9eb54d3ab/start", {}, example=False)
    assert response.status == 204
    assert response.route == "/virtualbox/61d61bdd-aa7d-4912-817f-65a9eb54d3ab/start"


@asyncio_patch("gns3server.modules.VirtualBox.stop_vm", return_value=True)
def test_vbox_stop(server):
    response = server.post("/virtualbox/61d61bdd-aa7d-4912-817f-65a9eb54d3ab/stop", {}, example=False)
    assert response.status == 204
    assert response.route == "/virtualbox/61d61bdd-aa7d-4912-817f-65a9eb54d3ab/stop"
