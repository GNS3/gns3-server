# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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

import sys

from gns3server.utils.interfaces import interfaces, is_interface_up


def test_interfaces():
    # This test should pass on all platforms without crash
    assert isinstance(interfaces(), list)


def test_is_interface_up():
    if sys.platform.startswith("win"):
        # is_interface_up() always returns True on Windows
        pass
    elif sys.platform.startswith("darwin"):
        assert is_interface_up("lo0") is True
    else:
        assert is_interface_up("lo") is True
        assert is_interface_up("fake0") is False
