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
import os
from tests.utils import asyncio_patch, AsyncioMagicMock

from gns3server.ubridge.ubridge_error import UbridgeNamespaceError
from gns3server.modules.docker.docker_vm import DockerVM
from gns3server.modules.docker.docker_error import *
from gns3server.modules.docker import Docker
from gns3server.utils.get_resource import get_resource


from unittest.mock import patch, MagicMock, PropertyMock, call
from gns3server.config import Config


@pytest.fixture(scope="module")
def manager(port_manager):
    m = Docker.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager):
    vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu:latest")
    vm._cid = "e90e34656842"
    vm.allocate_aux = False
    return vm


def test_json(vm, project):
    assert vm.__json__() == {
        'container_id': 'e90e34656842',
        'image': 'ubuntu:latest',
        'name': 'test',
        'project_id': project.id,
        'vm_id': vm.id,
        'adapters': 1,
        'console': vm.console,
        'console_type': 'telnet',
        'console_resolution': '1024x768',
        'console_http_port': 80,
        'console_http_path': '/',
        'aux': vm.aux,
        'start_command': vm.start_command,
        'environment': vm.environment,
        'vm_directory': vm.working_dir
    }


def test_start_command(vm):

    vm.start_command = "hello"
    assert vm.start_command == "hello"
    vm.start_command = " "
    assert vm.start_command is None


def test_create(loop, project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu:latest"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu:latest")
            loop.run_until_complete(asyncio.async(vm.create()))
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Binds": [
                            "{}:/gns3:ro".format(get_resource("modules/docker/resources")),
                            "{}:/etc/network:rw".format(os.path.join(vm.working_dir, "etc", "network"))
                        ],
                        "Privileged": True
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Name": "test",
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "GNS3_MAX_ETHERNET=eth0"
                        ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


def test_create_with_tag(loop, project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu:latest"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu:latest:16.04")
            loop.run_until_complete(asyncio.async(vm.create()))
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Binds": [
                            "{}:/gns3:ro".format(get_resource("modules/docker/resources")),
                            "{}:/etc/network:rw".format(os.path.join(vm.working_dir, "etc", "network"))
                        ],
                        "Privileged": True
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Name": "test",
                "Hostname": "test",
                "Image": "ubuntu:latest:16.04",
                "Env": [
                    "GNS3_MAX_ETHERNET=eth0"
                        ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


def test_create_vnc(loop, project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu:latest"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu:latest", console_type="vnc", console=5900)
            vm._start_vnc = MagicMock()
            vm._display = 42
            loop.run_until_complete(asyncio.async(vm.create()))
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Binds": [
                            "{}:/gns3:ro".format(get_resource("modules/docker/resources")),
                            "{}:/etc/network:rw".format(os.path.join(vm.working_dir, "etc", "network")),
                            '/tmp/.X11-unix/:/tmp/.X11-unix/'
                        ],
                        "Privileged": True
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Name": "test",
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "GNS3_MAX_ETHERNET=eth0",
                    "DISPLAY=:42"
                        ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._start_vnc.called
        assert vm._cid == "e90e34656806"
        assert vm._console_type == "vnc"


def test_create_start_cmd(loop, project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu:latest"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu:latest")
            vm._start_command = "/bin/ls"
            loop.run_until_complete(asyncio.async(vm.create()))
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Binds": [
                            "{}:/gns3:ro".format(get_resource("modules/docker/resources")),
                            "{}:/etc/network:rw".format(os.path.join(vm.working_dir, "etc", "network"))
                        ],
                        "Privileged": True
                    },
                "Volumes": {},
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/ls"],
                "NetworkDisabled": True,
                "Name": "test",
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "GNS3_MAX_ETHERNET=eth0"
                        ]
            })
        assert vm._cid == "e90e34656806"


def test_create_environment(loop, project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu:latest"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu:latest")
            vm.environment = "YES=1\nNO=0"
            loop.run_until_complete(asyncio.async(vm.create()))
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Binds": [
                            "{}:/gns3:ro".format(get_resource("modules/docker/resources")),
                            "{}:/etc/network:rw".format(os.path.join(vm.working_dir, "etc", "network"))
                        ],
                        "Privileged": True
                    },
                "Env": [
                    "GNS3_MAX_ETHERNET=eth0",
                    "YES=1",
                    "NO=0"
                        ],
                "Volumes": {},
                "NetworkDisabled": True,
                "Name": "test",
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


def test_create_image_not_available(loop, project, manager):

    call = 0

    @asyncio.coroutine
    def informations():
        nonlocal call
        if call == 0:
            call += 1
            raise DockerHttp404Error("missing")
        else:
            return {}

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu:latest")
    vm._get_image_informations = MagicMock()
    vm._get_image_informations.side_effect = informations

    with asyncio_patch("gns3server.modules.docker.DockerVM.pull_image", return_value=True) as mock_pull:
        with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
            loop.run_until_complete(asyncio.async(vm.create()))
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Binds": [
                            "{}:/gns3:ro".format(get_resource("modules/docker/resources")),
                            "{}:/etc/network:rw".format(os.path.join(vm.working_dir, "etc", "network"))
                        ],
                        "Privileged": True
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Name": "test",
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "GNS3_MAX_ETHERNET=eth0"
                        ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"
        mock_pull.assert_called_with("ubuntu:latest")


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

    vm.allocate_aux = True
    vm._start_aux = AsyncioMagicMock()

    vm._get_container_state = AsyncioMagicMock(return_value="stopped")
    vm._start_ubridge = AsyncioMagicMock()
    vm._get_namespace = AsyncioMagicMock(return_value=42)
    vm._add_ubridge_connection = AsyncioMagicMock()
    vm._start_console = AsyncioMagicMock()

    nio = manager.create_nio(0, {"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))

    with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
        loop.run_until_complete(asyncio.async(vm.start()))

    mock_query.assert_called_with("POST", "containers/e90e34656842/start")
    vm._add_ubridge_connection.assert_called_once_with(nio, 0, 42)
    assert vm._start_ubridge.called
    assert vm._start_console.called
    assert vm._start_aux.called
    assert vm.status == "started"


def test_start_namespace_failed(loop, vm, manager, free_console_port):

    assert vm.status != "started"
    vm.adapters = 1

    nio = manager.create_nio(0, {"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
            with asyncio_patch("gns3server.modules.docker.DockerVM._start_ubridge") as mock_start_ubridge:
                with asyncio_patch("gns3server.modules.docker.DockerVM._get_namespace", return_value=42) as mock_namespace:
                    with asyncio_patch("gns3server.modules.docker.DockerVM._add_ubridge_connection", side_effect=UbridgeNamespaceError()) as mock_add_ubridge_connection:
                        with asyncio_patch("gns3server.modules.docker.DockerVM._get_log", return_value='Hello not available') as mock_log:

                            with pytest.raises(DockerError):
                                loop.run_until_complete(asyncio.async(vm.start()))

    mock_query.assert_any_call("POST", "containers/e90e34656842/start")
    mock_add_ubridge_connection.assert_called_once_with(nio, 0, 42)
    assert mock_start_ubridge.called
    assert vm.status == "stopped"


def test_start_without_nio(loop, vm, manager, free_console_port):
    """
    If no nio exists we will create one.
    """

    assert vm.status != "started"
    vm.adapters = 1

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
            with asyncio_patch("gns3server.modules.docker.DockerVM._start_ubridge") as mock_start_ubridge:
                with asyncio_patch("gns3server.modules.docker.DockerVM._get_namespace", return_value=42) as mock_namespace:
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

    original_console = vm.console
    original_aux = vm.aux

    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu:latest"}]) as mock_list_images:
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
            "Binds": [
                "{}:/gns3:ro".format(get_resource("modules/docker/resources")),
                "{}:/etc/network:rw".format(os.path.join(vm.working_dir, "etc", "network"))
            ],
            "Privileged": True
        },
        "Volumes": {},
        "NetworkDisabled": True,
        "Name": "test",
        "Hostname": "test",
        "Image": "ubuntu:latest",
        "Env": [
            "GNS3_MAX_ETHERNET=eth0"
        ],
        "Entrypoint": ["/gns3/init.sh"],
        "Cmd": ["/bin/sh"]
    })
    assert vm.console == original_console
    assert vm.aux == original_aux


def test_update_vnc(loop, vm):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    vm.console_type = "vnc"
    vm.console = 5900
    vm._display = "display"
    original_console = vm.console
    original_aux = vm.aux

    with asyncio_patch("gns3server.modules.docker.DockerVM._start_vnc"):
        with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu:latest"}]) as mock_list_images:
            with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
                with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock_query:
                    loop.run_until_complete(asyncio.async(vm.update()))

    assert vm.console == original_console
    assert vm.aux == original_aux


def test_update_running(loop, vm):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    original_console = vm.console
    vm.start = MagicMock()

    with asyncio_patch("gns3server.modules.docker.Docker.list_images", return_value=[{"image": "ubuntu:latest"}]) as mock_list_images:
        with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="running"):
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
            "Binds": [
                "{}:/gns3:ro".format(get_resource("modules/docker/resources")),
                "{}:/etc/network:rw".format(os.path.join(vm.working_dir, "etc", "network"))
            ],
            "Privileged": True
        },
        "Volumes": {},
        "NetworkDisabled": True,
        "Name": "test",
        "Hostname": "test",
        "Image": "ubuntu:latest",
        "Env": [
            "GNS3_MAX_ETHERNET=eth0"
        ],
        "Entrypoint": ["/gns3/init.sh"],
        "Cmd": ["/bin/sh"]
    })

    assert vm.console == original_console
    assert vm.start.called


def test_delete(loop, vm):

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
            loop.run_until_complete(asyncio.async(vm.delete()))
    mock_query.assert_called_with("DELETE", "containers/e90e34656842", params={"force": 1})


def test_close(loop, vm, port_manager):
    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    loop.run_until_complete(asyncio.async(vm.adapter_add_nio_binding(0, nio)))

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
            loop.run_until_complete(asyncio.async(vm.close()))
    mock_query.assert_called_with("DELETE", "containers/e90e34656842", params={"force": 1})

    assert vm._closed is True
    assert "4242" not in port_manager.udp_ports


def test_close_vnc(loop, vm, port_manager):

    vm._console_type = "vnc"
    vm._x11vnc_process = MagicMock()
    vm._xvfb_process = MagicMock()

    with asyncio_patch("gns3server.modules.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.modules.docker.Docker.query") as mock_query:
            loop.run_until_complete(asyncio.async(vm.close()))
    mock_query.assert_called_with("DELETE", "containers/e90e34656842", params={"force": 1})

    assert vm._closed is True
    assert vm._xvfb_process.terminate.called


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

    loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 0, 42)))

    calls = [
        call.send("docker create_veth veth-gns3-ext0 veth-gns3-int0"),
        call.send('docker move_to_ns veth-gns3-int0 42 eth0'),
        call.send('bridge create bridge0'),
        call.send('bridge add_nio_linux_raw bridge0 veth-gns3-ext0'),
        call.send('bridge add_nio_udp bridge0 4242 127.0.0.1 4343'),
        call.send('bridge start_capture bridge0 "/tmp/capture.pcap"'),
        call.send('bridge start bridge0')
    ]
    # We need to check any_order ortherwise mock is confused by asyncio
    vm._ubridge_hypervisor.assert_has_calls(calls, any_order=True)


def test_add_ubridge_connection_none_nio(loop, vm):

    nio = None
    vm._ubridge_hypervisor = MagicMock()

    loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 0, 42)))

    calls = [
        call.send("docker create_veth veth-gns3-ext0 veth-gns3-int0"),
        call.send('docker move_to_ns veth-gns3-int0 42 eth0'),
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
        loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 12, 42)))


def test_add_ubridge_connection_no_free_interface(loop, vm):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)
    with pytest.raises(DockerError):

        # We create fake ethernet interfaces for docker
        interfaces = ["veth-gns3-ext{}".format(index) for index in range(128)]

        with patch("psutil.net_if_addrs", return_value=interfaces):
            loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 0, 42)))


def test_delete_ubridge_connection(loop, vm):

    vm._ubridge_hypervisor = MagicMock()
    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(0, nio)

    loop.run_until_complete(asyncio.async(vm._add_ubridge_connection(nio, 0, 42)))
    loop.run_until_complete(asyncio.async(vm._delete_ubridge_connection(0)))

    calls = [
        call.send("bridge delete bridge0"),
        call.send('docker delete_veth veth-gns3-ext0')
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
        images = loop.run_until_complete(asyncio.async(vm.pull_image("ubuntu:latest")))
        mock.assert_called_with("POST", "images/create", params={"fromImage": "ubuntu:latest"})


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


def test_get_log(loop, vm):
    @asyncio.coroutine
    def read():
        return b'Hello\nWorld'

    mock_query = MagicMock()
    mock_query.read = read

    with asyncio_patch("gns3server.modules.docker.Docker.http_query", return_value=mock_query) as mock:
        images = loop.run_until_complete(asyncio.async(vm._get_log()))
        mock.assert_called_with("GET", "containers/e90e34656842/logs", params={"stderr": 1, "stdout": 1}, data={})


def test_get_image_informations(project, manager, loop):
    response = {
    }
    with asyncio_patch("gns3server.modules.docker.Docker.query", return_value=response) as mock:
        vm = DockerVM("test", str(uuid.uuid4()), project, manager, "ubuntu:latest")
        loop.run_until_complete(asyncio.async(vm._get_image_informations()))
        mock.assert_called_with("GET", "images/ubuntu:latest/json")


def test_mount_binds(vm, tmpdir):
    image_infos = {
        "ContainerConfig": {
            "Volumes": {
                "/test/experimental": {}
            }
        }
    }

    dst = os.path.join(vm.working_dir, "test/experimental")
    assert vm._mount_binds(image_infos) == [
        "{}:/gns3:ro".format(get_resource("modules/docker/resources")),
        "{}:/etc/network:rw".format(os.path.join(vm.working_dir, "etc", "network")),
        "{}:{}".format(dst, "/test/experimental")
    ]

    assert os.path.exists(dst)


def test_start_vnc(vm, loop):
    vm.console_resolution = "1280x1024"
    with patch("shutil.which", return_value="/bin/x"):
        with asyncio_patch("gns3server.modules.docker.docker_vm.wait_for_file_creation") as mock_wait:
            with asyncio_patch("asyncio.create_subprocess_exec") as mock_exec:
                loop.run_until_complete(asyncio.async(vm._start_vnc()))
    assert vm._display is not None
    mock_exec.assert_any_call("Xvfb", "-nolisten", "tcp", ":{}".format(vm._display), "-screen", "0", "1280x1024x16")
    mock_exec.assert_any_call("x11vnc", "-forever", "-nopw", "-shared", "-geometry", "1280x1024", "-display", "WAIT:{}".format(vm._display), "-rfbport", str(vm.console), "-noncache", "-listen", "127.0.0.1")
    mock_wait.assert_called_with("/tmp/.X11-unix/X{}".format(vm._display))


def test_start_vnc_xvfb_missing(vm, loop):
    with pytest.raises(DockerError):
        loop.run_until_complete(asyncio.async(vm._start_vnc()))


def test_start_aux(vm, loop):

    with asyncio_patch("asyncio.subprocess.create_subprocess_exec", return_value=MagicMock()) as mock_exec:
        loop.run_until_complete(asyncio.async(vm._start_aux()))


def test_create_network_interfaces(vm):

    vm.adapters = 5
    network_config = vm._create_network_config()
    assert os.path.exists(os.path.join(network_config, "interfaces"))
    assert os.path.exists(os.path.join(network_config, "if-up.d"))

    with open(os.path.join(network_config, "interfaces")) as f:
        content = f.read()
    assert "eth0" in content
    assert "eth4" in content
    assert "eth5" not in content
