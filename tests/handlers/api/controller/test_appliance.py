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


from gns3server.controller import Controller
from gns3server.controller.appliance import Appliance


@pytest.fixture
def compute(http_controller, async_run):
    compute = MagicMock()
    compute.id = "example.com"
    compute.host = "example.org"
    Controller.instance()._computes = {"example.com": compute}
    return compute


@pytest.fixture
def project(http_controller, async_run):
    return async_run(Controller.instance().add_project(name="Test"))


def test_appliance_list(http_controller, controller):

    id = str(uuid.uuid4())
    controller.load_appliances()
    controller._appliances[id] = Appliance(id, {
        "appliance_type": "qemu",
        "category": 0,
        "name": "test",
        "symbol": "guest.svg",
        "default_name_format": "{name}-{0}",
        "compute_id": "local"
    })
    response = http_controller.get("/appliances", example=True)
    assert response.status == 200
    assert response.route == "/appliances"
    assert len(response.json) > 0


def test_appliance_templates_list(http_controller, controller, async_run):

    controller.load_appliance_templates()
    response = http_controller.get("/appliances/templates", example=True)
    assert response.status == 200
    assert len(response.json) > 0


def test_cr(http_controller, controller, async_run):

    controller.load_appliance_templates()
    response = http_controller.get("/appliances/templates", example=True)
    assert response.status == 200
    assert len(response.json) > 0


def test_appliance_create_without_id(http_controller, controller):

    params = {"base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "appliance_type": "vpcs"}

    response = http_controller.post("/appliances", params, example=True)
    assert response.status == 201
    assert response.route == "/appliances"
    assert response.json["appliance_id"] is not None
    assert len(controller.appliances) == 1


def test_appliance_create_with_id(http_controller, controller):

    params = {"appliance_id": str(uuid.uuid4()),
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "appliance_type": "vpcs"}

    response = http_controller.post("/appliances", params, example=True)
    assert response.status == 201
    assert response.route == "/appliances"
    assert response.json["appliance_id"] is not None
    assert len(controller.appliances) == 1


def test_appliance_get(http_controller, controller):

    appliance_id = str(uuid.uuid4())
    params = {"appliance_id": appliance_id,
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "appliance_type": "vpcs"}

    response = http_controller.post("/appliances", params)
    assert response.status == 201

    response = http_controller.get("/appliances/{}".format(appliance_id), example=True)
    assert response.status == 200
    assert response.json["appliance_id"] == appliance_id


def test_appliance_update(http_controller, controller):

    appliance_id = str(uuid.uuid4())
    params = {"appliance_id": appliance_id,
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "appliance_type": "vpcs"}

    response = http_controller.post("/appliances", params)
    assert response.status == 201

    response = http_controller.get("/appliances/{}".format(appliance_id))
    assert response.status == 200
    assert response.json["appliance_id"] == appliance_id

    params["name"] = "VPCS_TEST_RENAMED"
    response = http_controller.put("/appliances/{}".format(appliance_id), params, example=True)

    assert response.status == 200
    assert response.json["name"] == "VPCS_TEST_RENAMED"


def test_appliance_delete(http_controller, controller):

    appliance_id = str(uuid.uuid4())
    params = {"appliance_id": appliance_id,
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "appliance_type": "vpcs"}

    response = http_controller.post("/appliances", params)
    assert response.status == 201

    response = http_controller.get("/appliances")
    assert len(response.json) == 1
    assert len(controller.appliances) == 1

    response = http_controller.delete("/appliances/{}".format(appliance_id), example=True)
    assert response.status == 204

    response = http_controller.get("/appliances")
    assert len(response.json) == 0
    assert len(controller.appliances) == 0


def test_create_node_from_appliance(http_controller, controller, project, compute):

    id = str(uuid.uuid4())
    controller._appliances = {id: Appliance(id, {
        "appliance_type": "qemu",
        "category": 0,
        "name": "test",
        "symbol": "guest.svg",
        "default_name_format": "{name}-{0}",
        "compute_id": "example.com"
    })}
    with asyncio_patch("gns3server.controller.project.Project.add_node_from_appliance") as mock:
        response = http_controller.post("/projects/{}/appliances/{}".format(project.id, id), {
            "x": 42,
            "y": 12
        })
    mock.assert_called_with(id, x=42, y=12, compute_id=None)
    print(response.body)
    assert response.route == "/projects/{project_id}/appliances/{appliance_id}"
    assert response.status == 201
