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
import asyncio

from tests.utils import asyncio_patch, AsyncioMagicMock
from unittest.mock import patch, MagicMock, ANY

from gns3server.compute.traceng.traceng_vm import TraceNGVM
from gns3server.compute.traceng.traceng_error import TraceNGError
from gns3server.compute.traceng import TraceNG
from gns3server.compute.notification_manager import NotificationManager


@pytest.fixture
async def manager(port_manager):

    m = TraceNG.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
async def vm(compute_project, manager, ubridge_path):

    vm = TraceNGVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", compute_project, manager)
    vm._start_ubridge = AsyncioMagicMock()
    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_hypervisor.is_running.return_value = True
    return vm


async def test_vm(project, manager):

    vm = TraceNGVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    assert vm.name == "test"
    assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0f"


async def test_vm_invalid_traceng_path(vm, manager):

    with patch("gns3server.compute.traceng.traceng_vm.TraceNGVM._traceng_path", return_value="/tmp/fake/path/traceng"):
        with pytest.raises(TraceNGError):
            nio = manager.create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
            await vm.port_add_nio_binding(0, nio)
            await vm.start()
            assert vm.name == "test"
            assert vm.id == "00010203-0405-0607-0809-0a0b0c0d0e0e"


async def test_start(vm):

    process = MagicMock()
    process.returncode = None

    with NotificationManager.instance().queue() as queue:
        await queue.get(1)  # Ping

        vm.ip_address = "192.168.1.1"
        with patch("sys.platform", return_value="win"):
            with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM._check_requirements", return_value=True):
                with asyncio_patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                    await vm.start("192.168.1.2")
                    assert mock_exec.call_args[0] == (vm._traceng_path(),
                                                      '-u',
                                                      '-c',
                                                      ANY,
                                                      '-v',
                                                      ANY,
                                                      '-b',
                                                      '127.0.0.1',
                                                      '-s',
                                                      'ICMP',
                                                      '-f',
                                                      '192.168.1.1',
                                                      '192.168.1.2')
                    assert vm.is_running()
                    assert vm.command_line == ' '.join(mock_exec.call_args[0])
        (action, event, kwargs) = await queue.get(1)
        assert action == "node.updated"
        assert event == vm


async def test_stop(vm):

    process = MagicMock()
    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future
    process.returncode = None

    vm.ip_address = "192.168.1.1"
    with NotificationManager.instance().queue() as queue:
        with patch("sys.platform", return_value="win"):
            with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM._check_requirements", return_value=True):
                with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
                    nio = TraceNG.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
                    await vm.port_add_nio_binding(0, nio)

                    vm._ubridge_send = AsyncioMagicMock()
                    await vm.start("192.168.1.2")
                    assert vm.is_running()

                    with asyncio_patch("gns3server.utils.asyncio.wait_for_process_termination"):
                        await vm.stop()
                    assert vm.is_running() is False

                    process.terminate.assert_called_with()

                    await queue.get(1)  #  Ping
                    await queue.get(1)  #  Started

                    (action, event, kwargs) = await queue.get(1)
                    assert action == "node.updated"
                    assert event == vm


async def test_reload(vm):

    process = MagicMock()
    # Wait process kill success
    future = asyncio.Future()
    future.set_result(True)
    process.wait.return_value = future
    process.returncode = None

    vm.ip_address = "192.168.1.1"
    with patch("sys.platform", return_value="win"):
        with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM._check_requirements", return_value=True):
            with asyncio_patch("asyncio.create_subprocess_exec", return_value=process):
                nio = TraceNG.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
                await vm.port_add_nio_binding(0, nio)

                vm._ubridge_send = AsyncioMagicMock()
                await vm.start("192.168.1.2")
                assert vm.is_running()

                with asyncio_patch("gns3server.utils.asyncio.wait_for_process_termination"):
                    await vm.reload()
                assert vm.is_running() is True

                #if sys.platform.startswith("win"):
                #    process.send_signal.assert_called_with(1)
                #else:
                process.terminate.assert_called_with()


async def test_add_nio_binding_udp(vm):

    nio = TraceNG.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1", "filters": {}})
    await vm.port_add_nio_binding(0, nio)
    assert nio.lport == 4242


async def test_port_remove_nio_binding(vm):

    nio = TraceNG.instance().create_nio({"type": "nio_udp", "lport": 4242, "rport": 4243, "rhost": "127.0.0.1"})
    await vm.port_add_nio_binding(0, nio)
    await vm.port_remove_nio_binding(0)
    assert vm._ethernet_adapter.ports[0] is None


async def test_close(vm):

    vm.ip_address = "192.168.1.1"
    with patch("sys.platform", return_value="win"):
        with asyncio_patch("gns3server.compute.traceng.traceng_vm.TraceNGVM._check_requirements", return_value=True):
            with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()):
                await vm.start("192.168.1.2")
                await vm.close()
                assert vm.is_running() is False
