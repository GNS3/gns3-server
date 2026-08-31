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
import socket
import collections
from unittest.mock import patch

import psutil

from gns3server.utils.interfaces import interfaces, is_interface_up, has_netmask


# psutil returns snicaddr namedtuples; mirror that shape for the mocks below.
snicaddr = collections.namedtuple("snicaddr", ["family", "address", "netmask", "broadcast", "ptp"])
# psutil.net_if_stats() returns snicstats namedtuples.
snicstats = collections.namedtuple("snicstats", ["isup", "duplex", "speed", "mtu", "flags"])


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
        assert "type" in interface
        assert "netmask" in interface
        assert "ip_addresses" in interface
        assert "status" in interface
        assert "speed" in interface
        assert "mtu" in interface
        assert "flags" in interface


def _fake_net_if_addrs():
    # A representative set of host interfaces exercising the address-collection logic.
    return {
        # several IPv4 and several IPv6 addresses on the same interface
        "eth0": [
            snicaddr(socket.AF_INET, "192.168.1.5", "255.255.255.0", "192.168.1.255", None),
            snicaddr(socket.AF_INET, "10.0.0.5", "255.255.255.0", "10.0.0.255", None),
            snicaddr(socket.AF_INET6, "fe80::1", "ffff:ffff:ffff:ffff::", None, None),
            snicaddr(socket.AF_INET6, "2001:db8::1", "ffff:ffff:ffff:ffff::", None, None),
            snicaddr(psutil.AF_LINK, "00:11:22:33:44:55", None, None, None),
        ],
        # no IP address at all (only a MAC)
        "eth1": [
            snicaddr(psutil.AF_LINK, "00:11:22:33:44:66", None, None, None),
        ],
        # IPv6 only
        "eth2": [
            snicaddr(socket.AF_INET6, "2001:db8::2", "ffff:ffff:ffff:ffff::", None, None),
            snicaddr(psutil.AF_LINK, "00:11:22:33:44:77", None, None, None),
        ],
        # present in net_if_addrs but absent from net_if_stats (exercises the fallback)
        "eth3": [
            snicaddr(psutil.AF_LINK, "00:11:22:33:44:88", None, None, None),
        ],
    }


def _fake_net_if_stats():
    # flags are returned as a comma-separated string by psutil >= 6.0
    return {
        "eth0": snicstats(True, 0, 1000, 1500, "up,broadcast,running,multicast"),
        "eth1": snicstats(False, 0, 0, 1500, "broadcast"),
        "eth2": snicstats(True, 0, 0, 1500, "up,running"),
    }


@patch("gns3server.utils.interfaces.psutil.net_if_stats", _fake_net_if_stats)
@patch("gns3server.utils.interfaces.psutil.net_if_addrs", _fake_net_if_addrs)
def test_interfaces_collects_all_ip_addresses(config):

    result = {iface["name"]: iface for iface in interfaces()}
    eth0 = result["eth0"]

    # every IPv4 and IPv6 address is reported, preserving order
    assert eth0["ip_addresses"] == [
        {"family": "ipv4", "address": "192.168.1.5", "netmask": "255.255.255.0"},
        {"family": "ipv4", "address": "10.0.0.5", "netmask": "255.255.255.0"},
        {"family": "ipv6", "address": "fe80::1", "netmask": "ffff:ffff:ffff:ffff::"},
        {"family": "ipv6", "address": "2001:db8::1", "netmask": "ffff:ffff:ffff:ffff::"},
    ]
    # legacy single-IPv4 fields are kept for backward compatibility
    assert eth0["ip_address"] == "10.0.0.5"
    assert eth0["netmask"] == "255.255.255.0"
    # link attributes and up status come from net_if_stats (flags split into a list)
    assert eth0["status"] == "up"
    assert eth0["speed"] == 1000
    assert eth0["mtu"] == 1500
    assert eth0["flags"] == ["up", "broadcast", "running", "multicast"]


@patch("gns3server.utils.interfaces.psutil.net_if_stats", _fake_net_if_stats)
@patch("gns3server.utils.interfaces.psutil.net_if_addrs", _fake_net_if_addrs)
def test_interfaces_with_no_address(config):

    result = {iface["name"]: iface for iface in interfaces()}
    eth1 = result["eth1"]
    assert eth1["ip_addresses"] == []
    assert eth1["ip_address"] == ""
    assert eth1["netmask"] == ""
    assert eth1["status"] == "down"
    assert eth1["flags"] == ["broadcast"]


@patch("gns3server.utils.interfaces.psutil.net_if_stats", _fake_net_if_stats)
@patch("gns3server.utils.interfaces.psutil.net_if_addrs", _fake_net_if_addrs)
def test_interfaces_with_ipv6_only(config):

    result = {iface["name"]: iface for iface in interfaces()}
    eth2 = result["eth2"]
    assert eth2["ip_addresses"] == [
        {"family": "ipv6", "address": "2001:db8::2", "netmask": "ffff:ffff:ffff:ffff::"},
    ]
    assert eth2["ip_address"] == ""
    assert eth2["status"] == "up"
    assert eth2["mtu"] == 1500


@patch("gns3server.utils.interfaces.psutil.net_if_stats", _fake_net_if_stats)
@patch("gns3server.utils.interfaces.psutil.net_if_addrs", _fake_net_if_addrs)
def test_interfaces_without_stats_entry(config):
    # an interface present in net_if_addrs but missing from net_if_stats falls
    # back to neutral defaults instead of crashing
    result = {iface["name"]: iface for iface in interfaces()}
    eth3 = result["eth3"]
    assert eth3["status"] == "down"
    assert eth3["speed"] == 0
    assert eth3["mtu"] == 0
    assert eth3["flags"] == []


def test_has_netmask(config):

    if sys.platform.startswith("darwin"):
        assert has_netmask("lo0") is True
    else:
        assert has_netmask("lo") is True


def test_is_interface_up():

    if sys.platform.startswith("darwin"):
        assert is_interface_up("lo0") is True
    else:
        assert is_interface_up("lo") is True
        assert is_interface_up("fake0") is False
