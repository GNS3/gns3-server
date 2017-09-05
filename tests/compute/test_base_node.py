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
from collections import OrderedDict

import pytest
import aiohttp
import asyncio
import os
from tests.utils import asyncio_patch, AsyncioMagicMock


from unittest.mock import patch, MagicMock
from gns3server.compute.vpcs.vpcs_vm import VPCSVM
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.vpcs.vpcs_error import VPCSError
from gns3server.compute.error import NodeError
from gns3server.compute.vpcs import VPCS
from gns3server.compute.nios.nio_udp import NIOUDP


@pytest.fixture(scope="function")
def manager(port_manager):
    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def node(project, manager):
    return VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)


def test_temporary_directory(project, manager):
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    assert isinstance(node.temporary_directory, str)


def test_console(project, manager):
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    node.console = 5011
    assert node.console == 5011
    node.console = None
    assert node.console is None


def test_change_console_port(node, port_manager):
    port1 = port_manager.get_free_tcp_port(node.project)
    port2 = port_manager.get_free_tcp_port(node.project)
    port_manager.release_tcp_port(port1, node.project)
    port_manager.release_tcp_port(port2, node.project)
    node.console = port1
    node.console = port2
    assert node.console == port2
    port_manager.reserve_tcp_port(port1, node.project)


def test_console_vnc_invalid(project, manager):
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    node._console_type = "vnc"
    with pytest.raises(NodeError):
        node.console = 2012


def test_close(node, loop, port_manager):
    assert node.console is not None

    aux = port_manager.get_free_tcp_port(node.project)
    port_manager.release_tcp_port(aux, node.project)

    node.aux = aux
    port = node.console
    assert loop.run_until_complete(asyncio.async(node.close()))
    # Raise an exception if the port is not free
    port_manager.reserve_tcp_port(port, node.project)
    # Raise an exception if the port is not free
    port_manager.reserve_tcp_port(aux, node.project)
    assert node.console is None
    assert node.aux is None

    # Called twice closed should return False
    assert loop.run_until_complete(asyncio.async(node.close())) is False


def test_aux(project, manager, port_manager):
    aux = port_manager.get_free_tcp_port(project)
    port_manager.release_tcp_port(aux, project)

    node = DockerVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, "ubuntu", aux=aux)
    assert node.aux == aux
    node.aux = None
    assert node.aux is None


def test_allocate_aux(project, manager):
    node = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    assert node.aux is None

    # Docker has an aux port by default
    node = DockerVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, "ubuntu")
    assert node.aux is not None


def test_change_aux_port(node, port_manager):
    port1 = port_manager.get_free_tcp_port(node.project)
    port2 = port_manager.get_free_tcp_port(node.project)
    port_manager.release_tcp_port(port1, node.project)
    port_manager.release_tcp_port(port2, node.project)
    node.aux = port1
    node.aux = port2
    assert node.aux == port2
    port_manager.reserve_tcp_port(port1, node.project)


def test_update_ubridge_udp_connection(node, async_run):
    filters = {
        "latency": [10]
    }

    snio = NIOUDP(1245, "localhost", 1246, {})
    dnio = NIOUDP(1245, "localhost", 1244, filters)
    with asyncio_patch("gns3server.compute.base_node.BaseNode._ubridge_apply_filters") as mock:
        async_run(node.update_ubridge_udp_connection('VPCS-10', snio, dnio))
    mock.assert_called_with("VPCS-10", filters)


def test_ubridge_apply_filters(node, async_run):
    filters = OrderedDict((
        ('latency', [10]),
        ('bpf', ["icmp[icmptype] == 8\ntcp src port 53"])
    ))
    node._ubridge_send = AsyncioMagicMock()
    async_run(node._ubridge_apply_filters("VPCS-10", filters))
    node._ubridge_send.assert_any_call("bridge reset_packet_filters VPCS-10")
    node._ubridge_send.assert_any_call("bridge add_packet_filter VPCS-10 filter0 latency 10")


def test_ubridge_apply_bpf_filters(node, async_run):
    filters = {
        "bpf": ["icmp[icmptype] == 8\ntcp src port 53"]
    }
    node._ubridge_send = AsyncioMagicMock()
    async_run(node._ubridge_apply_filters("VPCS-10", filters))
    node._ubridge_send.assert_any_call("bridge reset_packet_filters VPCS-10")
    node._ubridge_send.assert_any_call("bridge add_packet_filter VPCS-10 filter0 bpf \"icmp[icmptype] == 8\"")
    node._ubridge_send.assert_any_call("bridge add_packet_filter VPCS-10 filter1 bpf \"tcp src port 53\"")
