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

import aiohttp
import asyncio
import pytest
import pytest_asyncio
import uuid
import os

from unittest.mock import patch
from tests.utils import asyncio_patch, AsyncioMagicMock

from gns3server.compute.ubridge.ubridge_error import UbridgeNamespaceError
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.docker.docker_error import DockerError, DockerHttp404Error
from gns3server.compute.docker import Docker


from unittest.mock import patch, MagicMock, call


@pytest_asyncio.fixture
async def manager(port_manager):

    m = Docker.instance()
    m.port_manager = port_manager
    return m


@pytest_asyncio.fixture(scope="function")
async def vm(compute_project, manager):

    vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", aux_type="none")
    vm._cid = "e90e34656842"
    return vm


def test_json(vm, compute_project):

    assert vm.asdict() == {
        'container_id': 'e90e34656842',
        'image': 'ubuntu:latest',
        'name': 'test',
        'project_id': compute_project.id,
        'node_id': vm.id,
        'adapters': 1,
        'console': vm.console,
        'console_type': 'telnet',
        'aux_type': 'none',
        'console_resolution': '1024x768',
        'console_http_port': 80,
        'console_http_path': '/',
        'extra_hosts': None,
        'extra_volumes': [],
        'memory': 0,
        'cpus': 0,
        'aux': vm.aux,
        'start_command': vm.start_command,
        'environment': vm.environment,
        'node_directory': vm.working_dir,
        'status': 'stopped',
        'usage': ''
    }


def test_start_command(vm):

    vm.start_command = "hello"
    assert vm.start_command == "hello"
    vm.start_command = " "
    assert vm.start_command is None


@pytest.mark.asyncio
async def test_create(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest")
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_with_tag(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:16.04")
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:16.04",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_vnc(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu", console_type="vnc", console=5900)
            vm._start_vnc = MagicMock()
            vm._display = 42
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            },
                            {
                                "Type": "bind",
                                "Source": f"/tmp/.X11-unix/X{vm._display}",
                                "Target": f"/tmp/.X11-unix/X{vm._display}",
                                "ReadOnly": True
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network",
                    "QT_GRAPHICSSYSTEM=native",
                    "DISPLAY=:42"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._start_vnc.called
        assert vm._cid == "e90e34656806"
        assert vm._console_type == "vnc"


@pytest.mark.asyncio
async def test_create_with_extra_hosts(compute_project, manager):

    extra_hosts = "test:199.199.199.1\ntest2:199.199.199.1"
    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu", extra_hosts=extra_hosts)
            await vm.create()
            called_kwargs = mock.call_args[1]
            assert "GNS3_EXTRA_HOSTS=199.199.199.1\ttest\n199.199.199.1\ttest2" in called_kwargs["data"]["Env"]
        assert vm._extra_hosts == extra_hosts

@pytest.mark.asyncio
async def test_create_with_colon_in_project_name(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
            with patch("gns3server.compute.project.Project.node_working_directory", return_value="/tmp/test_:_/"):
                vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu")
                with pytest.raises(DockerError):
                    await vm.create()


@pytest.mark.asyncio
async def test_create_with_extra_hosts_wrong_format(compute_project, manager):
    extra_hosts = "test"

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu", extra_hosts=extra_hosts)
            with pytest.raises(DockerError):
                await vm.create()


@pytest.mark.asyncio
async def test_create_with_empty_extra_hosts(compute_project, manager):
    extra_hosts = "test:\n"

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu", extra_hosts=extra_hosts)
            await vm.create()
            called_kwargs = mock.call_args[1]
            assert len([ e for e in called_kwargs["data"]["Env"] if "GNS3_EXTRA_HOSTS" in e]) == 0


@pytest.mark.asyncio
async def test_create_with_project_variables(compute_project, manager):
    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    compute_project.variables = [
        {"name": "VAR1"},
        {"name": "VAR2", "value": "VAL1"},
        {"name": "VAR3", "value": "2x${VAR2}"}
    ]

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu")
            await vm.create()
            called_kwargs = mock.call_args[1]
            assert "VAR1=" in called_kwargs["data"]["Env"]
            assert "VAR2=VAL1" in called_kwargs["data"]["Env"]
            assert "VAR3=2xVAL1" in called_kwargs["data"]["Env"]
    compute_project.variables = None


@pytest.mark.asyncio
async def test_create_start_cmd(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest")
            vm._start_command = "/bin/ls"
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/ls"],
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network"
                    ]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_environment(compute_project, manager):
    """
    Allow user to pass an environment. User can't override our
    internal variables
    """

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu")
            vm.environment = "YES=1\nNO=0\nGNS3_MAX_ETHERNET=eth2"
            await vm.create()
            assert mock.call_args[1]['data']['Env'] == [
                "container=docker",
                "GNS3_MAX_ETHERNET=eth0",
                "GNS3_VOLUMES=/etc/network",
                "YES=1",
                "NO=0"
            ]


@pytest.mark.asyncio
async def test_create_environment_with_last_new_line_character(compute_project, manager):
    """
    Allow user to pass an environment. User can't override our
    internal variables
    """

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu")
            vm.environment = "YES=1\nNO=0\nGNS3_MAX_ETHERNET=eth2\n"
            await vm.create()
            assert mock.call_args[1]['data']['Env'] == [
                "container=docker",
                "GNS3_MAX_ETHERNET=eth0",
                "GNS3_VOLUMES=/etc/network",
                "YES=1",
                "NO=0"
            ]


@pytest.mark.asyncio
async def test_create_image_not_available(compute_project, manager):

    call = 0
    async def information():
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

    vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu")
    vm._get_image_information = MagicMock()
    vm._get_image_information.side_effect = information
    with asyncio_patch("gns3server.compute.docker.DockerVM.pull_image", return_value=True) as mock_pull:
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"
        mock_pull.assert_called_with("ubuntu:latest")


@pytest.mark.asyncio
async def test_create_with_user(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": [],
        "Config" : {
            "User" : "test",
        },
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest")
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "User": "root",
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network",
                    "GNS3_USER=test"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_with_extra_volumes_invalid_format_1(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["vol1"])
            with pytest.raises(DockerError):
                await vm.create()


@pytest.mark.asyncio
async def test_create_with_extra_volumes_invalid_format_2(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["/vol1", ""])
            with pytest.raises(DockerError):
                await vm.create()


@pytest.mark.asyncio
async def test_create_with_extra_volumes_invalid_format_3(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["/vol1/.."])
            with pytest.raises(DockerError):
                await vm.create()


@pytest.mark.asyncio
async def test_create_with_extra_volumes_duplicate_1_image(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": [],
        "Config" : {
            "Volumes" : {
                "/vol/1": None
            },
        },
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["/vol/1"])
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "vol", "1"),
                                "Target": "/gns3volumes/vol/1"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network:/vol/1"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_with_extra_volumes_duplicate_2_user(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": [],
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["/vol/1", "/vol/1"])
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "vol", "1"),
                                "Target": "/gns3volumes/vol/1"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network:/vol/1"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_with_extra_volumes_duplicate_3_subdir(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": [],
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["/vol/1/", "/vol"])
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "vol"),
                                "Target": "/gns3volumes/vol"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network:/vol"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_with_extra_volumes_duplicate_4_backslash(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": [],
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["/vol//", "/vol"])
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "vol"),
                                "Target": "/gns3volumes/vol"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network:/vol"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_with_extra_volumes_duplicate_5_subdir_issue_1595(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": [],
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["/etc"])
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc"),
                                "Target": "/gns3volumes/etc"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_with_extra_volumes_duplicate_6_subdir_issue_1595(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": [],
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["/etc/test", "/etc"])
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc"),
                                "Target": "/gns3volumes/etc"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_create_with_extra_volumes(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": [],
        "Config" : {
            "Volumes" : {
                "/vol/1": None
            },
        },
    }

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", extra_volumes=["/vol/2"])
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "vol", "1"),
                                "Target": "/gns3volumes/vol/1"
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "vol", "2"),
                                "Target": "/gns3volumes/vol/2"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network:/vol/1:/vol/2"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_get_container_state(vm):

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
    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
        assert await vm._get_container_state() == "running"

    response["State"]["Running"] = False
    response["State"]["Paused"] = True
    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
        assert await vm._get_container_state() == "paused"

    response["State"]["Running"] = False
    response["State"]["Paused"] = False
    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
        assert await vm._get_container_state() == "exited"


@pytest.mark.asyncio
async def test_is_running(vm):

    response = {
        "State": {
            "Running": False,
            "Paused": False
        }
    }
    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
        assert await vm.is_running() is False

    response["State"]["Running"] = True
    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
        assert await vm.is_running() is True


@pytest.mark.asyncio
async def test_pause(vm):

    with asyncio_patch("gns3server.compute.docker.Docker.query") as mock:
        await vm.pause()

    mock.assert_called_with("POST", "containers/e90e34656842/pause")
    assert vm.status == "suspended"


@pytest.mark.asyncio
async def test_unpause(vm):

    with asyncio_patch("gns3server.compute.docker.Docker.query") as mock:
        await vm.unpause()
    mock.assert_called_with("POST", "containers/e90e34656842/unpause")


@pytest.mark.asyncio
async def test_start(vm, manager, free_console_port, tmpdir):

    assert vm.status != "started"
    vm.adapters = 1

    vm.aux_type = "telnet"
    vm._start_aux = AsyncioMagicMock()

    vm._get_container_state = AsyncioMagicMock(return_value="stopped")
    vm._start_ubridge = AsyncioMagicMock()
    vm._get_namespace = AsyncioMagicMock(return_value=42)
    vm._add_ubridge_connection = AsyncioMagicMock()
    vm._start_console = AsyncioMagicMock()

    nio = manager.create_nio({"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    await vm.adapter_add_nio_binding(0, nio)

    with patch("gns3server.compute.docker.Docker.install_busybox"):
        with asyncio_patch("gns3server.compute.docker.Docker.query") as mock_query:
            await vm.start()

    mock_query.assert_called_with("POST", "containers/e90e34656842/start")
    vm._add_ubridge_connection.assert_called_once_with(nio, 0)
    assert vm._start_ubridge.called
    assert vm._start_console.called
    assert vm._start_aux.called
    assert vm.status == "started"


@pytest.mark.asyncio
async def test_resources_installed(vm, manager, tmpdir):

    assert vm.status != "started"
    vm.adapters = 1

    docker_resources_path = os.path.join(tmpdir, "docker", "resources")
    os.makedirs(docker_resources_path, exist_ok=True)
    manager.resources_path = MagicMock(return_value=docker_resources_path)

    with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.compute.docker.Docker.query"):
            with asyncio_patch("gns3server.compute.docker.DockerVM._start_ubridge"):
                with asyncio_patch("gns3server.compute.docker.DockerVM._get_namespace", return_value=42):
                    with asyncio_patch("gns3server.compute.docker.DockerVM._add_ubridge_connection"):
                        with asyncio_patch("gns3server.compute.docker.DockerVM._start_console"):
                            await vm.start()

    assert vm.status == "started"
    assert os.path.exists(os.path.join(docker_resources_path, "init.sh"))
    assert os.path.exists(os.path.join(docker_resources_path, "run-cmd.sh"))
    assert os.path.exists(os.path.join(docker_resources_path, "bin", "busybox"))
    assert os.path.exists(os.path.join(docker_resources_path, "bin", "udhcpc"))
    assert os.path.exists(os.path.join(docker_resources_path, "etc", "udhcpc", "default.script"))


@pytest.mark.asyncio
async def test_start_namespace_failed(vm, manager, free_console_port):

    assert vm.status != "started"
    vm.adapters = 1

    nio = manager.create_nio({"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    await vm.adapter_add_nio_binding(0, nio)

    with patch("gns3server.compute.docker.Docker.install_busybox"):
        with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="stopped"):
            with asyncio_patch("gns3server.compute.docker.Docker.query") as mock_query:
                with asyncio_patch("gns3server.compute.docker.DockerVM._start_ubridge") as mock_start_ubridge:
                    with asyncio_patch("gns3server.compute.docker.DockerVM._get_namespace", return_value=42) as mock_namespace:
                        with asyncio_patch("gns3server.compute.docker.DockerVM._add_ubridge_connection", side_effect=UbridgeNamespaceError()) as mock_add_ubridge_connection:
                            with asyncio_patch("gns3server.compute.docker.DockerVM._get_log", return_value='Hello not available') as mock_log:

                                with pytest.raises(DockerError):
                                    await vm.start()

    mock_query.assert_any_call("POST", "containers/e90e34656842/start")
    mock_add_ubridge_connection.assert_called_once_with(nio, 0)
    assert mock_start_ubridge.called
    assert vm.status == "stopped"


@pytest.mark.asyncio
async def test_start_without_nio(vm):
    """
    If no nio exists we will create one.
    """

    assert vm.status != "started"
    vm.adapters = 1

    with patch("gns3server.compute.docker.Docker.install_busybox"):
        with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="stopped"):
            with asyncio_patch("gns3server.compute.docker.Docker.query") as mock_query:
                with asyncio_patch("gns3server.compute.docker.DockerVM._start_ubridge") as mock_start_ubridge:
                    with asyncio_patch("gns3server.compute.docker.DockerVM._get_namespace", return_value=42):
                        with asyncio_patch("gns3server.compute.docker.DockerVM._add_ubridge_connection") as mock_add_ubridge_connection:
                            with asyncio_patch("gns3server.compute.docker.DockerVM._start_console") as mock_start_console:
                                await vm.start()

    mock_query.assert_called_with("POST", "containers/e90e34656842/start")
    assert mock_add_ubridge_connection.called
    assert mock_start_ubridge.called
    assert mock_start_console.called
    assert vm.status == "started"


@pytest.mark.asyncio
async def test_start_unpause(vm):

    with patch("gns3server.compute.docker.Docker.install_busybox"):
        with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="paused"):
            with asyncio_patch("gns3server.compute.docker.DockerVM.unpause", return_value="paused") as mock:
                await vm.start()
    assert mock.called
    assert vm.status == "started"


@pytest.mark.asyncio
async def test_restart(vm):

    with asyncio_patch("gns3server.compute.docker.Docker.query") as mock:
        await vm.restart()
    mock.assert_called_with("POST", "containers/e90e34656842/restart")


@pytest.mark.asyncio
async def test_stop(vm):

    mock = MagicMock()
    vm._ubridge_hypervisor = mock
    vm._ubridge_hypervisor.is_running.return_value = True
    vm._fix_permissions = MagicMock()

    with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="running"):
        with asyncio_patch("gns3server.compute.docker.Docker.query") as mock_query:
            vm._permissions_fixed = False
            await vm.stop()
            mock_query.assert_called_with("POST", "containers/e90e34656842/stop", params={"t": 5})
    assert mock.stop.called
    assert vm._ubridge_hypervisor is None
    assert vm._fix_permissions.called


@pytest.mark.asyncio
async def test_stop_paused_container(vm):

    with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="paused"):
        with asyncio_patch("gns3server.compute.docker.DockerVM.unpause") as mock_unpause:
            with asyncio_patch("gns3server.compute.docker.Docker.query") as mock_query:
                await vm.stop()
                mock_query.assert_called_with("POST", "containers/e90e34656842/stop", params={"t": 5})
                assert mock_unpause.called


@pytest.mark.asyncio
async def test_update(vm):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    original_console = vm.console
    original_aux = vm.aux

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="stopped"):
            with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock_query:
                await vm.update()

    mock_query.assert_any_call("DELETE", "containers/e90e34656842", params={"force": 1, "v": 1})
    mock_query.assert_any_call("POST", "containers/create", data={
        "Tty": True,
        "OpenStdin": True,
        "StdinOnce": False,
        "HostConfig":
        {
            "CapAdd": ["ALL"],
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": Docker.resources_path(),
                    "Target": "/gns3",
                    "ReadOnly": True
                },
                {
                    "Type": "bind",
                    "Source": os.path.join(vm.working_dir, "etc", "network"),
                    "Target": "/gns3volumes/etc/network"
                }
            ],
            "Privileged": True,
            "Memory": 0,
            "NanoCpus": 0
        },
        "Volumes": {},
        "NetworkDisabled": True,
        "Hostname": "test",
        "Image": "ubuntu:latest",
        "Env": [
            "container=docker",
            "GNS3_MAX_ETHERNET=eth0",
            "GNS3_VOLUMES=/etc/network"
        ],
        "Entrypoint": ["/gns3/init.sh"],
        "Cmd": ["/bin/sh"]
    })
    assert vm.console == original_console
    assert vm.aux == original_aux


@pytest.mark.asyncio
async def test_update_vnc(vm):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    vm._console_type = "vnc"
    vm._console = 5900
    vm._display = "display"
    original_console = vm.console
    original_aux = vm.aux

    with asyncio_patch("gns3server.compute.docker.DockerVM._start_vnc"):
        with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
            with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="stopped"):
                with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
                    await vm.update()

    assert vm.console == original_console
    assert vm.aux == original_aux


@pytest.mark.asyncio
async def test_update_running(vm):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }

    original_console = vm.console
    vm.start = MagicMock()

    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]) as mock_list_images:
        with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="running"):
            with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock_query:
                await vm.update()

    mock_query.assert_any_call("DELETE", "containers/e90e34656842", params={"force": 1, "v": 1})
    mock_query.assert_any_call("POST", "containers/create", data={
        "Tty": True,
        "OpenStdin": True,
        "StdinOnce": False,
        "HostConfig":
        {
            "CapAdd": ["ALL"],
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": Docker.resources_path(),
                    "Target": "/gns3",
                    "ReadOnly": True
                },
                {
                    "Type": "bind",
                    "Source": os.path.join(vm.working_dir, "etc", "network"),
                    "Target": "/gns3volumes/etc/network"
                }
            ],
            "Privileged": True,
            "Memory": 0,
            "NanoCpus": 0
        },
        "Volumes": {},
        "NetworkDisabled": True,
        "Hostname": "test",
        "Image": "ubuntu:latest",
        "Env": [
            "container=docker",
            "GNS3_MAX_ETHERNET=eth0",
            "GNS3_VOLUMES=/etc/network"
        ],
        "Entrypoint": ["/gns3/init.sh"],
        "Cmd": ["/bin/sh"]
    })

    assert vm.console == original_console
    assert vm.start.called


@pytest.mark.asyncio
async def test_delete(vm):

    with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.compute.docker.Docker.query") as mock_query:
            await vm.delete()
        mock_query.assert_called_with("DELETE", "containers/e90e34656842", params={"force": 1, "v": 1})


@pytest.mark.asyncio
async def test_close(vm, port_manager):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(nio)
    await vm.adapter_add_nio_binding(0, nio)

    with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.compute.docker.Docker.query") as mock_query:
            await vm.close()
        mock_query.assert_called_with("DELETE", "containers/e90e34656842", params={"force": 1, "v": 1})

    assert vm._closed is True
    assert "4242" not in port_manager.udp_ports


@pytest.mark.asyncio
async def test_close_vnc(vm):

    vm._console_type = "vnc"
    vm._vnc_process = MagicMock()

    with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="stopped"):
        with asyncio_patch("gns3server.compute.docker.Docker.query") as mock_query:
            await vm.close()
        mock_query.assert_called_with("DELETE", "containers/e90e34656842", params={"force": 1, "v": 1})

    assert vm._closed is True
    assert vm._vnc_process.terminate.called


@pytest.mark.asyncio
async def test_get_namespace(vm):

    response = {
        "State": {
            "Pid": 42
        }
    }
    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock_query:
        assert await vm._get_namespace() == 42
    mock_query.assert_called_with("GET", "containers/e90e34656842/json")


@pytest.mark.asyncio
async def test_add_ubridge_connection(vm):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(nio)
    nio.start_packet_capture("/tmp/capture.pcap")
    vm._ubridge_hypervisor = MagicMock()
    vm._namespace = 42
    await vm._add_ubridge_connection(nio, 0)

    calls = [
        call.send('bridge create bridge0'),
        call.send("bridge add_nio_tap bridge0 tap-gns3-e0"),
        call.send('docker move_to_ns tap-gns3-e0 42 eth0'),
        call.send('bridge add_nio_udp bridge0 4242 127.0.0.1 4343'),
        call.send('bridge start_capture bridge0 "/tmp/capture.pcap"'),
        call.send('bridge start bridge0')
    ]
    assert 'bridge0' in vm._bridges
    # We need to check any_order ortherwise mock is confused by asyncio
    vm._ubridge_hypervisor.assert_has_calls(calls, any_order=True)


@pytest.mark.asyncio
async def test_add_ubridge_connection_none_nio(vm):

    nio = None
    vm._ubridge_hypervisor = MagicMock()
    vm._namespace = 42

    await vm._add_ubridge_connection(nio, 0)

    calls = [
        call.send('bridge create bridge0'),
        call.send("bridge add_nio_tap bridge0 tap-gns3-e0"),
        call.send('docker move_to_ns tap-gns3-e0 42 eth0'),

    ]
    assert 'bridge0' in vm._bridges
    # We need to check any_order ortherwise mock is confused by asyncio
    vm._ubridge_hypervisor.assert_has_calls(calls, any_order=True)


@pytest.mark.asyncio
async def test_add_ubridge_connection_invalid_adapter_number(vm):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(nio)
    with pytest.raises(DockerError):
        await vm._add_ubridge_connection(nio, 12)


@pytest.mark.asyncio
async def test_add_ubridge_connection_no_free_interface(vm):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(nio)
    with pytest.raises(DockerError):

        # We create fake ethernet interfaces for docker
        interfaces = ["tap-gns3-e{}".format(index) for index in range(4096)]

        with patch("psutil.net_if_addrs", return_value=interfaces):
            await vm._add_ubridge_connection(nio, 0)


@pytest.mark.asyncio
async def test_adapter_add_nio_binding_1(vm):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(nio)
    await vm.adapter_add_nio_binding(0, nio)
    assert vm._ethernet_adapters[0].get_nio(0) == nio


@pytest.mark.asyncio
async def test_adapter_udpate_nio_binding_bridge_not_started(vm):

    vm._ubridge_apply_filters = AsyncioMagicMock()
    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(nio)
    with asyncio_patch("gns3server.compute.docker.DockerVM._get_container_state", return_value="running"):
        await vm.adapter_add_nio_binding(0, nio)
        await vm.adapter_update_nio_binding(0, nio)
    assert vm._ubridge_apply_filters.called is False


@pytest.mark.asyncio
async def test_adapter_add_nio_binding_invalid_adapter(vm):

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(nio)
    with pytest.raises(DockerError):
        await vm.adapter_add_nio_binding(12, nio)


@pytest.mark.asyncio
async def test_adapter_remove_nio_binding(vm):

    vm.ubridge = MagicMock()
    vm.ubridge.is_running.return_value = True

    nio = {"type": "nio_udp",
           "lport": 4242,
           "rport": 4343,
           "rhost": "127.0.0.1"}
    nio = vm.manager.create_nio(nio)
    await vm.adapter_add_nio_binding(0, nio)

    with asyncio_patch("gns3server.compute.docker.DockerVM._ubridge_send") as delete_ubridge_mock:
        await vm.adapter_remove_nio_binding(0)
        assert vm._ethernet_adapters[0].get_nio(0) is None
        delete_ubridge_mock.assert_any_call('bridge stop bridge0')
        delete_ubridge_mock.assert_any_call('bridge remove_nio_udp bridge0 4242 127.0.0.1 4343')


@pytest.mark.asyncio
async def test_adapter_remove_nio_binding_invalid_adapter(vm):

    with pytest.raises(DockerError):
        await vm.adapter_remove_nio_binding(12)


@pytest.mark.asyncio
async def test_start_capture(vm, tmpdir, manager, free_console_port):

    output_file = str(tmpdir / "test.pcap")
    nio = manager.create_nio({"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    await vm.adapter_add_nio_binding(0, nio)
    await vm.start_capture(0, output_file)
    assert vm._ethernet_adapters[0].get_nio(0).capturing


@pytest.mark.asyncio
async def test_stop_capture(vm, tmpdir, manager, free_console_port):

    output_file = str(tmpdir / "test.pcap")
    nio = manager.create_nio({"type": "nio_udp", "lport": free_console_port, "rport": free_console_port, "rhost": "127.0.0.1"})
    await vm.adapter_add_nio_binding(0, nio)
    await vm.start_capture(0, output_file)
    assert vm._ethernet_adapters[0].get_nio(0).capturing
    await vm.stop_capture(0)
    assert vm._ethernet_adapters[0].get_nio(0).capturing is False


@pytest.mark.asyncio
async def test_get_log(vm):

    async def read():
        return b'Hello\nWorld'

    mock_query = MagicMock()
    mock_query.read = read

    with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=mock_query) as mock:
        await vm._get_log()
        mock.assert_called_with("GET", "containers/e90e34656842/logs", params={"stderr": 1, "stdout": 1}, data={})


@pytest.mark.asyncio
async def test_get_image_information(compute_project, manager):

    response = {}
    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
        vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu")
        await vm._get_image_information()
        mock.assert_called_with("GET", "images/ubuntu:latest/json")


@pytest.mark.asyncio
async def test_mount_binds(vm):

    image_infos = {
        "Config": {
            "Volumes": {
                "/test/experimental": {}
            }
        }
    }

    dst = os.path.join(vm.working_dir, "test/experimental")
    assert vm._mount_binds(image_infos) == [
        {
            "Type": "bind",
            "Source": Docker.resources_path(),
            "Target": "/gns3",
            "ReadOnly": True
        },
        {
            "Type": "bind",
            "Source": os.path.join(vm.working_dir, "etc", "network"),
            "Target": "/gns3volumes/etc/network"
        },
        {
            "Type": "bind",
            "Source": dst,
            "Target": "/gns3volumes/test/experimental"
        }
    ]

    assert vm._volumes == ["/etc/network", "/test/experimental"]
    assert os.path.exists(dst)


@pytest.mark.asyncio
async def test_start_vnc(vm):

    vm.console_resolution = "1280x1024"
    with patch("shutil.which", return_value="/bin/Xtigervnc"):
        with asyncio_patch("gns3server.compute.docker.docker_vm.wait_for_file_creation") as mock_wait:
            with asyncio_patch("asyncio.create_subprocess_exec") as mock_exec:
                await vm._start_vnc()
    assert vm._display is not None
    assert mock_exec.call_args[0] == ("/bin/Xtigervnc", "-extension", "MIT-SHM", "-geometry", vm.console_resolution, "-depth", "16", "-interface", "127.0.0.1", "-rfbport", str(vm.console), "-AlwaysShared", "-SecurityTypes", "None", ":{}".format(vm._display))
    mock_wait.assert_called_with("/tmp/.X11-unix/X{}".format(vm._display))


@pytest.mark.asyncio
async def test_start_vnc_missing(vm):

    with patch("shutil.which", return_value=None):
        with pytest.raises(DockerError):
            await vm._start_vnc()


@pytest.mark.asyncio
async def test_start_aux(vm):

    with asyncio_patch("asyncio.subprocess.create_subprocess_exec", return_value=MagicMock()) as mock_exec:
        await vm._start_aux()
        mock_exec.assert_called_with(
            "script",
            "-qfc",
            "docker exec -i -t e90e34656842 /gns3/bin/busybox sh -c 'while true; do TERM=vt100 /gns3/bin/busybox sh; done'",
            "/dev/null",
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE
        )


@pytest.mark.asyncio
async def test_create_network_interfaces(vm):

    vm.adapters = 5
    network_config = vm._create_network_config()
    assert os.path.exists(os.path.join(network_config, "interfaces"))
    assert os.path.exists(os.path.join(network_config, "if-up.d"))

    with open(os.path.join(network_config, "interfaces")) as f:
        content = f.read()
    assert "eth0" in content
    assert "eth4" in content
    assert "eth5" not in content


@pytest.mark.asyncio
async def test_fix_permission(vm):

    vm._volumes = ["/etc"]
    vm._get_container_state = AsyncioMagicMock(return_value="running")
    process = MagicMock()
    with asyncio_patch("asyncio.subprocess.create_subprocess_exec", return_value=process) as mock_exec:
        await vm._fix_permissions()
    mock_exec.assert_called_with('docker', 'exec', 'e90e34656842', '/gns3/bin/busybox', 'sh', '-c', '(/gns3/bin/busybox find "/etc" -depth -print0 | /gns3/bin/busybox xargs -0 /gns3/bin/busybox stat -c \'%a:%u:%g:%n\' > "/etc/.gns3_perms") && /gns3/bin/busybox chmod -R u+rX "/etc" && /gns3/bin/busybox chown {}:{} -R "/etc"'.format(os.getuid(), os.getgid()))
    assert process.wait.called


@pytest.mark.asyncio
async def test_fix_permission_not_running(vm):

    vm._volumes = ["/etc"]
    vm._get_container_state = AsyncioMagicMock(return_value="stopped")
    process = MagicMock()
    with asyncio_patch("gns3server.compute.docker.Docker.query") as mock_start:
        with asyncio_patch("asyncio.subprocess.create_subprocess_exec", return_value=process) as mock_exec:
            await vm._fix_permissions()
    mock_exec.assert_called_with('docker', 'exec', 'e90e34656842', '/gns3/bin/busybox', 'sh', '-c', '(/gns3/bin/busybox find "/etc" -depth -print0 | /gns3/bin/busybox xargs -0 /gns3/bin/busybox stat -c \'%a:%u:%g:%n\' > "/etc/.gns3_perms") && /gns3/bin/busybox chmod -R u+rX "/etc" && /gns3/bin/busybox chown {}:{} -R "/etc"'.format(os.getuid(), os.getgid()))
    assert mock_start.called
    assert process.wait.called


@pytest.mark.asyncio
async def test_read_console_output_with_binary_mode(vm):

    class InputStreamMock(object):
        def __init__(self):
            self.sent = False

        async def receive(self):
            if not self.sent:
                self.sent = True
                return MagicMock(type=aiohttp.WSMsgType.BINARY, data=b"test")
            else:
                return MagicMock(type=aiohttp.WSMsgType.CLOSE)

        async def close(self):
            pass

    input_stream = InputStreamMock()
    output_stream = MagicMock()

    with asyncio_patch('gns3server.compute.docker.docker_vm.DockerVM.stop'):
        await vm._read_console_output(input_stream, output_stream)
        output_stream.feed_data.assert_called_once_with(b"test")


@pytest.mark.asyncio
async def test_cpus(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", cpus=0.5)
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 0,
                        "NanoCpus": 500000000
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"


@pytest.mark.asyncio
async def test_memory(compute_project, manager):

    response = {
        "Id": "e90e34656806",
        "Warnings": []
    }
    with asyncio_patch("gns3server.compute.docker.Docker.list_images", return_value=[{"image": "ubuntu"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
            vm = DockerVM("test", str(uuid.uuid4()), compute_project, manager, "ubuntu:latest", memory=32)
            await vm.create()
            mock.assert_called_with("POST", "containers/create", data={
                "Tty": True,
                "OpenStdin": True,
                "StdinOnce": False,
                "HostConfig":
                    {
                        "CapAdd": ["ALL"],
                        "Mounts": [
                            {
                                "Type": "bind",
                                "Source": Docker.resources_path(),
                                "Target": "/gns3",
                                "ReadOnly": True
                            },
                            {
                                "Type": "bind",
                                "Source": os.path.join(vm.working_dir, "etc", "network"),
                                "Target": "/gns3volumes/etc/network"
                            }
                        ],
                        "Privileged": True,
                        "Memory": 33554432,  # 32MB in bytes
                        "NanoCpus": 0
                    },
                "Volumes": {},
                "NetworkDisabled": True,
                "Hostname": "test",
                "Image": "ubuntu:latest",
                "Env": [
                    "container=docker",
                    "GNS3_MAX_ETHERNET=eth0",
                    "GNS3_VOLUMES=/etc/network"
                    ],
                "Entrypoint": ["/gns3/init.sh"],
                "Cmd": ["/bin/sh"]
            })
        assert vm._cid == "e90e34656806"
