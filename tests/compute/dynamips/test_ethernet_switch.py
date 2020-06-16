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

from tests.utils import AsyncioMagicMock
from gns3server.compute.nios.nio_udp import NIOUDP


def test_mac_command():

    node = AsyncioMagicMock()
    node.name = "Test"
    node.nios = {}
    node.nios[0] = NIOUDP(55, "127.0.0.1", 56)
    node.nios[0].name = "Ethernet0"
    node.nios[1] = NIOUDP(55, "127.0.0.1", 56)
    node.nios[1].name = "Ethernet1"
    #node._hypervisor.send = AsyncioMagicMock(return_value=["0050.7966.6801  1  Ethernet0", "0050.7966.6802  1  Ethernet1"])
    #console = EthernetSwitchConsole(node)
    #assert async_run(console.mac()) == \
    #    "Port       Mac                VLAN\n" \
    #    "Ethernet0  00:50:79:66:68:01  1\n" \
    #    "Ethernet1  00:50:79:66:68:02  1\n"
    #node._hypervisor.send.assert_called_with("ethsw show_mac_addr_table Test")
