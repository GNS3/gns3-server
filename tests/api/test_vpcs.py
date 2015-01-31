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

import pytest
import os
from tests.utils import asyncio_patch
from unittest.mock import patch


@pytest.fixture(scope="module")
def vm(server, project):
    response = server.post("/vpcs", {"name": "PC TEST 1", "project_uuid": project.uuid})
    assert response.status == 201
    return response.json


def test_vpcs_create(server, project):
    response = server.post("/vpcs", {"name": "PC TEST 1", "project_uuid": project.uuid}, example=True)
    assert response.status == 201
    assert response.route == "/vpcs"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_uuid"] == project.uuid
    assert response.json["script_file"] is None


def test_vpcs_get(server, project, vm):
    response = server.get("/vpcs/{}".format(vm["uuid"]), example=True)
    assert response.status == 200
    assert response.route == "/vpcs/{uuid}"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_uuid"] == project.uuid


def test_vpcs_create_script_file(server, project, tmpdir):
    path = os.path.join(str(tmpdir), "test")
    with open(path, 'w+') as f:
        f.write("ip 192.168.1.2")
    response = server.post("/vpcs", {"name": "PC TEST 1", "project_uuid": project.uuid, "script_file": path})
    assert response.status == 201
    assert response.route == "/vpcs"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_uuid"] == project.uuid
    assert response.json["script_file"] == path


def test_vpcs_create_startup_script(server, project):
    response = server.post("/vpcs", {"name": "PC TEST 1", "project_uuid": project.uuid, "startup_script": "ip 192.168.1.2\necho TEST"})
    assert response.status == 201
    assert response.route == "/vpcs"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_uuid"] == project.uuid
    assert response.json["startup_script"] == "ip 192.168.1.2\necho TEST"


def test_vpcs_create_port(server, project, free_console_port):
    response = server.post("/vpcs", {"name": "PC TEST 1", "project_uuid": project.uuid, "console": free_console_port})
    assert response.status == 201
    assert response.route == "/vpcs"
    assert response.json["name"] == "PC TEST 1"
    assert response.json["project_uuid"] == project.uuid
    assert response.json["console"] == free_console_port


def test_vpcs_nio_create_udp(server, vm):
    response = server.post("/vpcs/{}/ports/0/nio".format(vm["uuid"]), {"type": "nio_udp",
                                                                       "lport": 4242,
                                                                       "rport": 4343,
                                                                       "rhost": "127.0.0.1"},
                           example=True)
    assert response.status == 201
    assert response.route == "/vpcs/{uuid}/ports/{port_number:\d+}/nio"
    assert response.json["type"] == "nio_udp"


def test_vpcs_nio_create_tap(server, vm):
    with patch("gns3server.modules.base_manager.BaseManager._has_privileged_access", return_value=True):
        response = server.post("/vpcs/{}/ports/0/nio".format(vm["uuid"]), {"type": "nio_tap",
                                                                           "tap_device": "test"})
        assert response.status == 201
        assert response.route == "/vpcs/{uuid}/ports/{port_number:\d+}/nio"
        assert response.json["type"] == "nio_tap"


def test_vpcs_delete_nio(server, vm):
    server.post("/vpcs/{}/ports/0/nio".format(vm["uuid"]), {"type": "nio_udp",
                                                            "lport": 4242,
                                                            "rport": 4343,
                                                            "rhost": "127.0.0.1"})
    response = server.delete("/vpcs/{}/ports/0/nio".format(vm["uuid"]), example=True)
    assert response.status == 204
    assert response.route == "/vpcs/{uuid}/ports/{port_number:\d+}/nio"


def test_vpcs_start(server, vm):
    with asyncio_patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM.start", return_value=True) as mock:
        response = server.post("/vpcs/{}/start".format(vm["uuid"]))
        assert mock.called
        assert response.status == 204


def test_vpcs_stop(server, vm):
    with asyncio_patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM.stop", return_value=True) as mock:
        response = server.post("/vpcs/{}/stop".format(vm["uuid"]))
        assert mock.called
        assert response.status == 204


def test_vpcs_reload(server, vm):
    with asyncio_patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM.reload", return_value=True) as mock:
        response = server.post("/vpcs/{}/reload".format(vm["uuid"]))
        assert mock.called
        assert response.status == 204


def test_vpcs_delete(server, vm):
    with asyncio_patch("gns3server.modules.vpcs.VPCS.delete_vm", return_value=True) as mock:
        response = server.delete("/vpcs/{}".format(vm["uuid"]))
        assert mock.called
        assert response.status == 204


def test_vpcs_update(server, vm, tmpdir, free_console_port):
    path = os.path.join(str(tmpdir), 'startup2.vpcs')
    with open(path, 'w+') as f:
        f.write(path)
    response = server.put("/vpcs/{}".format(vm["uuid"]), {"name": "test",
                                                          "console": free_console_port,
                                                          "script_file": path,
                                                          "startup_script": "ip 192.168.1.1"})
    assert response.status == 200
    assert response.json["name"] == "test"
    assert response.json["console"] == free_console_port
    assert response.json["script_file"] == path
    assert response.json["startup_script"] == "ip 192.168.1.1"
