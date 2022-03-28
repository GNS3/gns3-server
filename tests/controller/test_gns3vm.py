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

import pytest
import sys
from tests.utils import asyncio_patch, AsyncioMagicMock

from gns3server.controller.gns3vm import GNS3VM
from gns3server.controller.gns3vm.gns3_vm_error import GNS3VMError
from pydantic import SecretStr


@pytest.fixture
def dummy_engine():

    engine = AsyncioMagicMock()
    engine.running = False
    engine.ip_address = "vm.local"
    engine.protocol = "https"
    engine.port = 8442
    engine.user = "hello"
    engine.password = SecretStr("world")
    return engine


@pytest.fixture
def dummy_gns3vm(controller, dummy_engine):

    vm = GNS3VM(controller)
    vm._settings["engine"] = "dummy"
    vm._settings["vmname"] = "Test VM"
    vm._settings["enable"] = True
    vm._engines["dummy"] = dummy_engine
    return vm


@pytest.mark.asyncio
async def test_list(controller):

    vm = GNS3VM(controller)
    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.list", return_value=[{"vmname": "test", "vmx_path": "test"}]):
        res = await vm.list("vmware")
        assert res == [{"vmname": "test"}]  # Information specific to VMware is stripped
    with asyncio_patch("gns3server.controller.gns3vm.virtualbox_gns3_vm.VirtualBoxGNS3VM.list", return_value=[{"vmname": "test"}]):
        res = await vm.list("virtualbox")
        assert res == [{"vmname": "test"}]
    with pytest.raises(NotImplementedError):
        await vm.list("hyperv")


@pytest.mark.asyncio
async def test_json(controller):

    vm = GNS3VM(controller)
    assert vm.asdict() == vm._settings


@pytest.mark.asyncio
async def test_update_settings(controller):

    vm = GNS3VM(controller)
    vm.settings = {
        "enable": True,
        "engine": "vmware",
        "vmname": "GNS3 VM"
    }

    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.start"):
        with asyncio_patch("gns3server.controller.gns3vm.GNS3VM._check_network"):
            await vm.auto_start_vm()
    assert "vm" in controller.computes
    await vm.update_settings({"enable": False})
    assert "vm" not in controller.computes


@pytest.mark.asyncio
async def test_auto_start(controller, dummy_gns3vm, dummy_engine):
    """
    When start the compute should be add to the controller
    """

    with asyncio_patch("gns3server.controller.gns3vm.GNS3VM._check_network"):
        await dummy_gns3vm.auto_start_vm()
    assert dummy_engine.start.called
    assert controller.computes["vm"].name == "GNS3 VM (Test VM)"
    assert controller.computes["vm"].host == "vm.local"
    assert controller.computes["vm"].port == 80
    assert controller.computes["vm"].protocol == "https"
    assert controller.computes["vm"].user == "hello"
    assert controller.computes["vm"].password.get_secret_value() == "world"


@pytest.mark.asyncio
async def test_auto_start_with_error(controller, dummy_gns3vm, dummy_engine):

    dummy_engine.start.side_effect = GNS3VMError("Dummy error")
    await dummy_gns3vm.auto_start_vm()
    assert dummy_engine.start.called
    assert controller.computes["vm"].name == "GNS3 VM (Test VM)"
