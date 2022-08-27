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

from gns3server.compute.vmware import VMware


@pytest.fixture
async def manager(port_manager):

    m = VMware.instance()
    m.port_manager = port_manager
    return m


def test_parse_vmware_file(tmpdir):

    path = str(tmpdir / "test.vmx")
    with open(path, "w+") as f:
        f.write('displayname = "GNS3 VM"\nguestOS = "ubuntu-64"')

    vmx = VMware.parse_vmware_file(path)
    assert vmx["displayname"] == "GNS3 VM"
    assert vmx["guestos"] == "ubuntu-64"
