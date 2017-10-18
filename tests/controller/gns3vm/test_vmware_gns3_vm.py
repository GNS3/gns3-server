#!/usr/bin/env python
#
# Copyright (C) 2017 GNS3 Technologies Inc.
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

from gns3server.controller.gns3vm.vmware_gns3_vm import VMwareGNS3VM


@pytest.fixture
def gns3vm(controller):
    vm = VMwareGNS3VM(controller)
    vm.vmname = "GNS3 VM"
    return vm


@pytest.fixture
def tmx_path(tmpdir):
    return str(tmpdir / "vmware.tmx")


def test_set_extra_options(gns3vm, async_run, tmx_path):
    gns3vm._vmx_path = tmx_path

    # when there is not an entry, we modify it
    with open(tmx_path, 'w') as f:
        f.write("")

    async_run(gns3vm._set_extra_options())

    with open(tmx_path, 'r') as f:
        assert f.read() == 'vhv.enable = "TRUE"\n'

    # when there is an entry, we don't modify it
    with open(tmx_path, 'w') as f:
        f.write('vhv.enable = "FALSE"\n')

    async_run(gns3vm._set_extra_options())

    with open(tmx_path, 'r') as f:
        assert f.read() == 'vhv.enable = "FALSE"\n'

