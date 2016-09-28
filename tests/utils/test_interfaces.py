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

from gns3server.utils.interfaces import interfaces, is_interface_up, has_netmask


def test_interfaces():
    # This test should pass on all platforms without crash
    interface_list = interfaces()
    assert isinstance(interface_list, list)
    for interface in interface_list:
        if interface["name"].startswith("vmnet"):
            assert interface["special"]

        assert "id" in interface
        assert "name" in interface
        assert "ip_address" in interface
        assert "mac_address" in interface
        if sys.platform.startswith("win"):
            assert "netcard" in interface
        assert "type" in interface
        assert "netmask" in interface


def test_has_netmask():
    if sys.platform.startswith("win"):
        # No loopback
        pass
    elif sys.platform.startswith("darwin"):
        assert has_netmask("lo0") is True
    else:
        assert has_netmask("lo") is True


def test_is_interface_up():
    if sys.platform.startswith("win"):
        # is_interface_up() always returns True on Windows
        pass
    elif sys.platform.startswith("darwin"):
        assert is_interface_up("lo0") is True
    else:
        assert is_interface_up("lo") is True
        assert is_interface_up("fake0") is False
