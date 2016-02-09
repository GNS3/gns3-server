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
import uuid
import asyncio
from tests.utils import asyncio_patch

from gns3server.modules.docker.docker_vm import DockerVM
from gns3server.modules.docker.docker_error import DockerError
from gns3server.modules.docker import Docker

from unittest.mock import patch, MagicMock, PropertyMock, call
from gns3server.config import Config


@pytest.fixture(scope="module")
def manager(port_manager):
    m = Docker.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager):
    vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu")
    vm._cid = "e90e34656842"
    return vm


def test_json(vm, project):
    assert vm.__json__() == {
        'container_id': 'e90e34656842',
        'image': 'ubuntu',
        'name': 'test',
        'project_id': project.id,
        'vm_id': vm.id,
        'adapters': 1,
        'console': vm.console,
        'start_command': vm.start_command,
        'environment': vm.environment
    }


def test_create(loop, project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu")
            loop.run_until_complete(asyncio.async(vm.create()))
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Privileged": True
                    },
                "NetworkDisabled": True,
                "Name": "test",
                "Image": "ubuntu"
            })
        assert vm._cid == "e90e34656806"


def test_create_start_cmd(loop, project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu")
            vm._start_command = "/bin/ls"
            loop.run_until_complete(asyncio.async(vm.create()))
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Privileged": True
                    },
                "Cmd": ["/bin/ls"],
                "NetworkDisabled": True,
                "Name": "test",
                "Image": "ubuntu"
            })
        assert vm._cid == "e90e34656806"


def test_create_environment(loop, project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu")
            vm.environment = "YES=1\nNO=0"
            loop.run_until_complete(asyncio.async(vm.create()))
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Privileged": True
                    },
                "Env": [
                    "YES=1",
                    "NO=0"
                    ],
                "NetworkDisabled": True,
                "Name": "test",
                "Image": "ubuntu"
            })
        assert vm._cid == "e90e34656806"


def test_create_image_not_available(loop, project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.DockerVM.pull_image", return_value=True) as mock_pull:
            with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
                vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu")
                loop.run_until_complete(asyncio.async(vm.create()))
                mock.assert_called_with("POST", "containers/create", data={
                    "Tty": True,
                    "OpenStdin": True,
                    "StdinOnce": False,
                    "HostConfig":
                        {
                            "CapAdd": ["ALL"],
                            "Privileged": True
                        },
                    "NetworkDisabled": True,
                    "Name": "test",
                    "Image": "ubuntu"
                })
            assert vm._cid == "e90e34656806"
            mock_pull.assert_called_with("ubuntu")


def test_get_container_state(loop, vm):
    response = {
        "State": {
            "Error": "",
            "ExitCode": 9,
            "FinishedAt": "2015-01-06T15:47:32.080254511Z",
            "OOMKilled": False,
            "Paused": False,
            "Pid": 0,
            "Restarting": False,
            "Running": True,
            "StartedAt": "2015-01-06T15:47:32.072697474Z"
        }
    }
    with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
        assert loop.run_until_complete(asyncio.async(vm._get_container_state())) == "running"

    response["State"]["Running"] = False
    response["State"]["Paused"] = True
    with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
        assert loop.run_until_complete(asyncio.async(vm._get_container_state())) == "paused"

    response["State"]["Running"] = False
    response["State"]["Paused"] = False
    with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
        assert loop.run_until_complete(asyncio.async(vm._get_container_state())) == "exited"


def test_is_running(loop, vm):
    response = {
        "State": {
            "Running": False,
            "Paused": False
        }
    }
    with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
        assert loop.run_until_complete(asyncio.async(vm.is_running())) is False

    response["State"]["Running"] = True
    with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
        assert loop.run_until_complete(asyncio.async(vm.is_running())) is True


def test_pause(loop, vm):

    with asyncio_patch("gns3server.modules.docker.Docker.query") as mock:
        loop.run_until_complete(asyncio.async(vm.pause()))

    mock.assert_called_with("POST", "containers/e90e34656842/pause")
    assert vm.status == "paused"


def test_unpause(loop, vm):

    with asyncio_patch("gns3server.modules.docker.Docker.query") as mock:
        loop.run_until_complete(asyncio.async(vm.unpause()))

    mock.assert_called_with("POST", "containers/e90e34656842/unpause")


def test_start(loop, vm, manager, free_console_port):

    assert vm.status != "started"
    vm.adapters = 1

    nio = manager.create_nio(0, {"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
            with asyncio_patch("gns3server.modules.docker.DockerVM._start_ubridge") as mock_start_ubridge:
                with asyncio_patch("gns3server.modules.docker.DockerVM._add_ubridge_connection") as mock_add_ubridge_connection:
                    with asyncio_patch("gns3server.modules.docker.DockerVM._start_console") as mock_start_console:
                        loop.run_until_complete(asyncio.async(vm.start()))

    mock_query.assert_called_with("POST", "containers/e90e34656842/start")
    mock_add_ubridge_connection.assert_called_once_with(nio, 0)
    assert mock_start_ubridge.called
    assert mock_start_console.called
    assert vm.status == "started"


def test_start_without_nio(loop, vm, manager, free_console_port):
    """
    If no nio exists we will create one.
    """

    assert vm.status != "started"
    vm.adapters = 1

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
            with asyncio_patch("gns3server.modules.docker.DockerVM._start_ubridge") as mock_start_ubridge:
                with asyncio_patch("gns3server.modules.docker.DockerVM._add_ubridge_connection") as mock_add_ubridge_connection:
                    with asyncio_patch("gns3server.modules.docker.DockerVM._start_console") as mock_start_console:
                        loop.run_until_complete(asyncio.async(vm.start()))

    mock_query.assert_called_with("POST", "containers/e90e34656842/start")
    assert mock_add_ubridge_connection.called
    assert mock_start_ubridge.called
    assert mock_start_console.called
    assert vm.status == "started"


def test_start_unpause(loop, vm, manager, free_console_port):

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="paused"):
        with asyncio_patch("gns3server.modules.docker.DockerVM.unpause", return_value="paused") as mock:
            loop.run_until_complete(asyncio.async(vm.start()))
    assert mock.called
    assert vm.status == "started"


def test_restart(loop, vm):

    with asyncio_patch("gns3server.modules.docker.Docker.query") as mock:
        loop.run_until_complete(asyncio.async(vm.restart()))

    mock.assert_called_with("POST", "containers/e90e34656842/restart")


def test_stop(loop, vm):
    vm._ubridge_hypervisor = MagicMock()
    vm._ubridge_hypervisor.is_running.return_value = True

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="running"):
        with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
            loop.run_until_complete(asyncio.async(vm.stop()))
            mock_query.assert_called_with("POST", "containers/e90e34656842/stop", params={"t": 5})
    assert vm._ubridge_hypervisor.stop.called


def test_stop_paused_container(loop, vm):

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="paused"):
        with asyncio_patch("gns3server.modules.docker.DockerVM.unpause") as mock_unpause:
            with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
                loop.run_until_complete(asyncio.async(vm.stop()))
                mock_query.assert_called_with("POST", "containers/e90e34656842/stop", params={"t": 5})
                assert mock_unpause.called


def test_update(loop, vm):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
            with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock_query:
                loop.run_until_complete(asyncio.async(vm.update()))

    mock_query.assert_any_call("DELETE", "containers/e90e34656842", params={"force": 1})
    mock_query.assert_any_call("POST", "containers/create", data={
        "Tty": True,
        "OpenStdin": True,
        "StdinOnce": False,
        "HostConfig":
        {
            "CapAdd": ["ALL"],
            "Privileged": True
        },
            "NetworkDisabled": True,
            "Name": "test",
            "Image": "ubuntu"
    })


def test_remove(loop, vm):

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
            loop.run_until_complete(asyncio.async(vm.remove()))
    mock_query.assert_called_with("DELETE", "containers/e90e34656842", params={"force": 1})


def test_remove_paused(loop, vm):

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="paused"):
        with asyncio_patch("gns3server.modules.docker.DockerVM.unpause") as mock_unpause:
            with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
                loop.run_until_complete(asyncio.async(vm.remove()))
    mock_query.assert_called_with("DELETE", "containers/e90e34656842", params={"force": 1})
    assert mock_unpause.called


def test_remove_running(loop, vm):

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="running"):
        with asyncio_patch("gns3server.modules.docker.DockerVM.stop") as mock_stop:
            with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
                loop.run_until_complete(asyncio.async(vm.remove()))
    mock_query.assert_called_with("DELETE", "containers/e90e34656842", params={"force": 1})
    assert mock_stop.called


def test_close(loop, vm, port_manager):
    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))

    with asyncio_patch("gns3server.modules.docker.DockerVM.remove") as mock_remove:
        loop.run_until_complete(asyncio.async(vm.close()))
    assert mock_remove.called
    assert vm._closed is True
    assert "4242" not in port_manager.udp_ports


def test_get_namespace(loop, vm):
    response = {
        "State": {
            "Pid": 42
        }
    }
    with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock_query:
        assert loop.run_until_complete(asyncio.async(vm._get_namespace())) == 42
    mock_query.assert_called_with("GET", "containers/e90e34656842/json")


def test_add_ubridge_connection(loop, vm):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    nio.startPacketCapture("/tmp/capture.pcap")
    vm._ubridge_hypervisor = MagicMock()
    with asyncio_patch("gns3server.modules.docker.DockerVM._get_namespace", return_value=42):
        loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 0)))

    calls = [
        call.send("docker create_veth gns3-veth0ext gns3-veth0int"),
        call.send('docker move_to_ns gns3-veth0int 42 eth0'),
        call.send('bridge create bridge0'),
        call.send('bridge add_nio_linux_raw bridge0 gns3-veth0ext'),
        call.send('bridge add_nio_udp bridge0 4242 127.0.0.1 4343'),
        call.send('bridge start_capture bridge0 "/tmp/capture.pcap"'),
        call.send('bridge start bridge0')
    ]
    # We need to check any_order ortherwise mock is confused by asyncio
    vm._ubridge_hypervisor.assert_has_calls(calls, any_order=True)


def test_add_ubridge_connection_none_nio(loop, vm):

    nio = None
    vm._ubridge_hypervisor = MagicMock()
    with asyncio_patch("gns3server.modules.docker.DockerVM._get_namespace", return_value=42):
        loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 0)))

    calls = [
        call.send("docker create_veth gns3-veth0ext gns3-veth0int"),
        call.send('docker move_to_ns gns3-veth0int 42 eth0'),
    ]
    # We need to check any_order ortherwise mock is confused by asyncio
    vm._ubridge_hypervisor.assert_has_calls(calls, any_order=True)


def test_add_ubridge_connection_invalid_adapter_number(loop, vm):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    with pytest.raises(DockerError):
        loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 12)))


def test_add_ubridge_connection_no_free_interface(loop, vm):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    with pytest.raises(DockerError):

        # We create fake ethernet interfaces for docker
        interfaces = ["gns3-veth{}ext".format(index) for index in range(128)]

        with patch("psutil.net_if_addrs", return_value=interfaces):
            loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 0)))


def test_delete_ubridge_connection(loop, vm):

    vm._ubridge_hypervisor = MagicMock()
    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    with asyncio_patch("gns3server.modules.docker.DockerVM._get_namespace", return_value=42):
        loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 0)))
    loop.run_until_complete(asyncio.async(vm._delete_ubridge_connection(0)))

    calls = [
        call.send("bridge delete bridge0"),
        call.send('docker delete_veth gns3-veth0ext gns3-veth0int')
    ]
    vm._ubridge_hypervisor.assert_has_calls(calls, any_order=True)


def test_adapter_add_nio_binding(vm, loop):
    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
    assert vm._ethernet_adapters[0].get_nio(0) == nio


def test_adapter_add_nio_binding_invalid_adapter(vm, loop):
    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    with pytest.raises(DockerError):
        loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(12, nio)))


def test_adapter_remove_nio_binding(vm, loop):
    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
    with asyncio_patch("gns3server.modules.docker.DockerVM._delete_ubridge_connection") as delete_ubridge_mock:
        loop.run_until_complete(asyncio.async(vm.adapter_remove_nio_binding(0)))
        assert vm._ethernet_adapters[0].get_nio(0) is None
        delete_ubridge_mock.assert_called_with(0)


def test_adapter_remove_nio_binding_invalid_adapter(vm, loop):
    with pytest.raises(DockerError):
        loop.run_until_complete(asyncio.async(vm.adapter_remove_nio_binding(12)))


def test_pull_image(loop, vm):
    class Response:
        """
        Simulate a response splitted in multiple packets
        """

        def __init__(self):
            self._read = -1

        @asyncio.coroutine
        def read(self, size):
            self._read += 1
            if self._read == 0:
                return b'{"progress": "0/100",'
            elif self._read == 1:
                return '"id": 42}'
            else:
                None

    mock_query = MagicMock()
    mock_query.content.return_value = Response()

    with asyncio_patch("gns3server.modules.docker.Docker.http_query", return_value=mock_query) as mock:
        images = loop.run_until_complete(asyncio.async(vm.pull_image("ubuntu")))
        mock.assert_called_with("POST", "images/create", params={"fromImage": "ubuntu"})


def test_start_capture(vm, tmpdir, manager, free_console_port, loop):

    output_file = str(tmpdir / "test.pcap")
    nio = manager.create_nio(0, {"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
    loop.run_until_complete(asyncio.async(vm.start_capture(0, output_file)))
    assert vm._ethernet_adapters[0].get_nio(0).capturing


def test_stop_capture(vm, tmpdir, manager, free_console_port, loop):

    output_file = str(tmpdir / "test.pcap")
    nio = manager.create_nio(0, {"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))
    loop.run_until_complete(vm.start_capture(0, output_file))
    assert vm._ethernet_adapters[0].get_nio(0).capturing
    loop.run_until_complete(asyncio.async(vm.stop_capture(0)))
    assert vm._ethernet_adapters[0].get_nio(0).capturing is False
