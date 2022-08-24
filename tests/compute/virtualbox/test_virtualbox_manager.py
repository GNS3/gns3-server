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


import pytest
import pytest_asyncio
import tempfile
import os
import stat

from unittest.mock import patch

from gns3server.compute.virtualbox import VirtualBox
from gns3server.compute.virtualbox.virtualbox_error import VirtualBoxError
from tests.utils import asyncio_patch


@pytest_asyncio.fixture
async def manager(port_manager):

    m = VirtualBox.instance()
    m.port_manager = port_manager
    return m


def test_vm_invalid_vboxmanage_path(manager, config):

    config.settings.VirtualBox.vboxmanage_path = "/bin/test_fake"
    with pytest.raises(VirtualBoxError):
        manager.find_vboxmanage()


def test_vm_non_executable_vboxmanage_path(manager, config):

    tmpfile = tempfile.NamedTemporaryFile()
    config.settings.VirtualBox.vboxmanage_path = tmpfile.name
    with pytest.raises(VirtualBoxError):
        manager.find_vboxmanage()


def test_vm_invalid_executable_name_vboxmanage_path(manager, config, tmpdir):

    path = str(tmpdir / "vpcs")
    with open(path, "w+") as f:
        f.write(path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    config.settings.VirtualBox.vboxmanage_path = path
    with pytest.raises(VirtualBoxError):
        manager.find_vboxmanage()


def test_vboxmanage_path(manager, config, tmpdir):

    path = str(tmpdir / "VBoxManage")
    with open(path, "w+") as f:
        f.write(path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    config.settings.VirtualBox.vboxmanage_path = path
    assert manager.find_vboxmanage() == path


@pytest.mark.asyncio
async def test_list_vms(manager):

    vm_list = ['"Windows 8.1" {27b4d095-ff5f-4ac4-bb9d-5f2c7861c1f1}',
               '"Carriage',
               'Return" {27b4d095-ff5f-4ac4-bb9d-5f2c7861c3f3}',
               '',
               '"<inaccessible>" {42b4d095-ff5f-4ac4-bb9d-5f2c7861c1f1}',
               '"Linux Microcore 4.7.1" {ccd8c50b-c172-457d-99fa-dd69371ede0e}']

    async def execute_mock(cmd, args):
        if cmd == "list":
            return vm_list
        else:
            if args[0] == "27b4d095-ff5f-4ac4-bb9d-5f2c7861c1f1":
                return ["memory=512"]
            elif args[0] == "ccd8c50b-c172-457d-99fa-dd69371ede0e":
                return ["memory=256"]
        assert False, "Unknow {} {}".format(cmd, args)

    with asyncio_patch("gns3server.compute.virtualbox.VirtualBox.execute") as mock:
        mock.side_effect = execute_mock
        vms = await manager.list_vms()
    assert vms == [
        {"vmname": "Windows 8.1", "ram": 512},
        {"vmname": "Linux Microcore 4.7.1", "ram": 256}
    ]
