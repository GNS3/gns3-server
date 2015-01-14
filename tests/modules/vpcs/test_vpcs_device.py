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
from unittest.mock import patch
from gns3server.modules.vpcs.vpcs_device import VPCSDevice
from gns3server.modules.vpcs.vpcs_error import VPCSError

@patch("subprocess.check_output", return_value="Welcome to Virtual PC Simulator, version 0.6".encode("utf-8"))
def test_vm(tmpdir):
    vm = VPCSDevice("test", 42, working_dir=str(tmpdir), path="/bin/test")
    assert vm.name == "test"
    assert vm.id == 42

@patch("subprocess.check_output", return_value="Welcome to Virtual PC Simulator, version 0.1".encode("utf-8"))
def test_vm_invalid_vpcs_version(tmpdir):
    with pytest.raises(VPCSError):
        vm = VPCSDevice("test", 42, working_dir=str(tmpdir), path="/bin/test")
        assert vm.name == "test"
        assert vm.id == 42

def test_vm_invalid_vpcs_path(tmpdir):
    with pytest.raises(VPCSError):
        vm = VPCSDevice("test", 42, working_dir=str(tmpdir), path="/bin/test_fake")
        assert vm.name == "test"
        assert vm.id == 42

