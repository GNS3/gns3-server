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

import pytest
from tests.utils import asyncio_patch

from gns3server.controller.gns3vm import GNS3VM


def test_list(async_run, controller):
    vm = GNS3VM(controller)

    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.list", return_value=[{"vmname": "test", "vmx_path": "test"}]):
        res = async_run(vm.list("vmware"))
        assert res == [{"vmname": "test"}]  # Informations specific to vmware are stripped
    with asyncio_patch("gns3server.controller.gns3vm.virtualbox_gns3_vm.VirtualBoxGNS3VM.list", return_value=[{"vmname": "test"}]):
        res = async_run(vm.list("virtualbox"))
        assert res == [{"vmname": "test"}]
    with pytest.raises(NotImplementedError):
        async_run(vm.list("hyperv"))


def test_json(controller):
    vm = GNS3VM(controller)
    assert vm.__json__() == vm._settings


def test_update_settings(controller, async_run):
    vm = GNS3VM(controller)
    vm.settings = {
        "enable": True,
        "engine": "vmware"
    }
    with asyncio_patch("gns3server.controller.gns3vm.vmware_gns3_vm.VMwareGNS3VM.start"):
        async_run(vm.auto_start_vm())
    assert "vm" in controller.computes
    async_run(vm.update_settings({"enable": False}))
    assert "vm" not in controller.computes
