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
import aiohttp
import asyncio
import os
from tests.utils import asyncio_patch


from unittest.mock import patch, MagicMock
from gns3server.modules.vpcs.vpcs_vm import VPCSVM
from gns3server.modules.docker.docker_vm import DockerVM
from gns3server.modules.vpcs.vpcs_error import VPCSError
from gns3server.modules.vm_error import VMError
from gns3server.modules.vpcs import VPCS


@pytest.fixture(scope="module")
def manager(port_manager):
    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager):
    return VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)


def test_temporary_directory(project, manager):
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    assert isinstance(vm.temporary_directory, str)


def test_console(project, manager):
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    vm.console = 5011
    assert vm.console == 5011
    vm.console = None
    assert vm.console is None


def test_change_console_port(vm, port_manager):
    port1 = port_manager.get_free_tcp_port(vm.project)
    port2 = port_manager.get_free_tcp_port(vm.project)
    port_manager.release_tcp_port(port1, vm.project)
    port_manager.release_tcp_port(port2, vm.project)
    vm.console = port1
    vm.console = port2
    assert vm.console == port2
    port_manager.reserve_tcp_port(port1, vm.project)


def test_console_vnc_invalid(project, manager):
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    vm.console_type = "vnc"
    with pytest.raises(VMError):
        vm.console = 2012


def test_close(vm, loop, port_manager):
    assert vm.console is not None

    aux = port_manager.get_free_tcp_port(vm.project)
    port_manager.release_tcp_port(aux, vm.project)

    vm.aux = aux
    port = vm.console
    assert loop.run_until_complete(asyncio.async(vm.close()))
    # Raise an exception if the port is not free
    port_manager.reserve_tcp_port(port, vm.project)
    # Raise an exception if the port is not free
    port_manager.reserve_tcp_port(aux, vm.project)
    assert vm.console is None
    assert vm.aux is None

    # Called twice closed should return False
    assert loop.run_until_complete(asyncio.async(vm.close())) is False


def test_aux(project, manager, port_manager):
    aux = port_manager.get_free_tcp_port(project)
    port_manager.release_tcp_port(aux, project)

    vm = DockerVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, "ubuntu", aux=aux)
    assert vm.aux == aux
    vm.aux = None
    assert vm.aux is None


def test_allocate_aux(project, manager):
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    assert vm.aux is None

    # Docker has an aux port by default
    vm = DockerVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager, "ubuntu")
    assert vm.aux is not None


def test_change_aux_port(vm, port_manager):
    port1 = port_manager.get_free_tcp_port(vm.project)
    port2 = port_manager.get_free_tcp_port(vm.project)
    port_manager.release_tcp_port(port1, vm.project)
    port_manager.release_tcp_port(port2, vm.project)
    vm.aux = port1
    vm.aux = port2
    assert vm.aux == port2
    port_manager.reserve_tcp_port(port1, vm.project)
