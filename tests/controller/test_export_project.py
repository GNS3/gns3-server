#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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


import os
import json
import pytest
import aiohttp
import zipfile

from unittest.mock import patch
from unittest.mock import MagicMock
from tests.utils import AsyncioMagicMock, AsyncioBytesIO

from gns3server.controller.project import Project
from gns3server.controller.compute import Compute
from gns3server.controller.export_project import export_project, _filter_files


@pytest.fixture
def project(controller):
    p = Project(controller=controller, name="Test")
    p.dump = MagicMock()
    return p


@pytest.fixture
def node(controller, project, async_run):
    compute = MagicMock()
    compute.id = "local"

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))
    return node


def test_filter_files():
    assert not _filter_files("hello/world")
    assert _filter_files("project-files/tmp")
    assert _filter_files("project-files/test_log.txt")
    assert _filter_files("project-files/test.log")
    assert _filter_files("test/snapshots")
    assert _filter_files("test/project-files/snapshots")
    assert _filter_files("test/project-files/snapshots/test.gns3p")


def test_export(tmpdir, project, async_run):
    path = project.path
    os.makedirs(os.path.join(path, "vm-1", "dynamips"))

    # The .gns3 should be renamed project.gns3 in order to simplify import
    with open(os.path.join(path, "test.gns3"), 'w+') as f:
        data = {
            "topology": {
                "computes": [
                    {
                        "compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0",
                        "host": "127.0.0.1",
                        "name": "Remote 1",
                        "port": 8001,
                        "protocol": "http"
                    }
                ],
                "nodes": [
                    {
                        "compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0",
                        "node_type": "vpcs"
                    }
                ]
            }
        }
        json.dump(data, f)

    with open(os.path.join(path, "vm-1", "dynamips", "test"), 'w+') as f:
        f.write("HELLO")
    with open(os.path.join(path, "vm-1", "dynamips", "test_log.txt"), 'w+') as f:
        f.write("LOG")
    os.makedirs(os.path.join(path, "project-files", "snapshots"))
    with open(os.path.join(path, "project-files", "snapshots", "test"), 'w+') as f:
        f.write("WORLD")

    z = async_run(export_project(project, str(tmpdir)))

    with open(str(tmpdir / 'zipfile.zip'), 'wb') as f:
        for data in z:
            f.write(data)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        with myzip.open("vm-1/dynamips/test") as myfile:
            content = myfile.read()
            assert content == b"HELLO"

        assert 'test.gns3' not in myzip.namelist()
        assert 'project.gns3' in myzip.namelist()
        assert 'project-files/snapshots/test' not in myzip.namelist()
        assert 'vm-1/dynamips/test_log.txt' not in myzip.namelist()

        with myzip.open("project.gns3") as myfile:
            topo = json.loads(myfile.read().decode())["topology"]
            assert topo["nodes"][0]["compute_id"] == "local"  # All node should have compute_id local after export
            assert topo["computes"] == []


def test_export_vm(tmpdir, project, async_run, controller):
    """
    If data is on a remote server export it locally before
    sending it in the archive.
    """

    compute = MagicMock()
    compute.id = "vm"
    compute.list_files = AsyncioMagicMock(return_value=[{"path": "vm-1/dynamips/test"}])

    # Fake file that will be download from the vm
    mock_response = AsyncioMagicMock()
    mock_response.content = AsyncioBytesIO()
    async_run(mock_response.content.write(b"HELLO"))
    mock_response.content.seek(0)
    compute.download_file = AsyncioMagicMock(return_value=mock_response)

    project._project_created_on_compute.add(compute)

    path = project.path
    os.makedirs(os.path.join(path, "vm-1", "dynamips"))

    # The .gns3 should be renamed project.gns3 in order to simplify import
    with open(os.path.join(path, "test.gns3"), 'w+') as f:
        f.write("{}")

    z = async_run(export_project(project, str(tmpdir)))
    assert compute.list_files.called

    with open(str(tmpdir / 'zipfile.zip'), 'wb') as f:
        for data in z:
            f.write(data)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        with myzip.open("vm-1/dynamips/test") as myfile:
            content = myfile.read()
            assert content == b"HELLO"


def test_export_disallow_running(tmpdir, project, node, async_run):
    """
    Dissallow export when a node is running
    """

    path = project.path

    topology = {
        "topology": {
            "nodes": [
                    {
                        "node_type": "dynamips"
                    }
            ]
        }
    }

    with open(os.path.join(path, "test.gns3"), 'w+') as f:
        json.dump(topology, f)

    node._status = "started"
    with pytest.raises(aiohttp.web.HTTPConflict):
        z = async_run(export_project(project, str(tmpdir)))


def test_export_disallow_some_type(tmpdir, project, async_run):
    """
    Dissalow export for some node type
    """

    path = project.path

    topology = {
        "topology": {
            "nodes": [
                {
                    "node_type": "cloud"
                }
            ]
        }
    }

    with open(os.path.join(path, "test.gns3"), 'w+') as f:
        json.dump(topology, f)

    with pytest.raises(aiohttp.web.HTTPConflict):
        z = async_run(export_project(project, str(tmpdir)))
    z = async_run(export_project(project, str(tmpdir), allow_all_nodes=True))

    # VirtualBox is always disallowed
    topology = {
        "topology": {
            "nodes": [
                {
                    "node_type": "virtualbox",
                    "properties": {
                        "linked_clone": True
                    }
                }
            ]
        }
    }
    with open(os.path.join(path, "test.gns3"), 'w+') as f:
        json.dump(topology, f)
    with pytest.raises(aiohttp.web.HTTPConflict):
        z = async_run(export_project(project, str(tmpdir), allow_all_nodes=True))


def test_export_fix_path(tmpdir, project, async_run):
    """
    Fix absolute image path, except for Docker
    """

    path = project.path

    topology = {
        "topology": {
            "nodes": [
                {
                    "properties": {
                        "image": "/tmp/c3725-adventerprisek9-mz.124-25d.image"
                    },
                    "node_type": "dynamips"
                },
                {
                    "properties": {
                        "image": "gns3/webterm:lastest"
                    },
                    "node_type": "docker"
                }
            ]
        }
    }

    with open(os.path.join(path, "test.gns3"), 'w+') as f:
        json.dump(topology, f)

    z = async_run(export_project(project, str(tmpdir)))
    with open(str(tmpdir / 'zipfile.zip'), 'wb') as f:
        for data in z:
            f.write(data)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        with myzip.open("project.gns3") as myfile:
            content = myfile.read().decode()
            topology = json.loads(content)
    assert topology["topology"]["nodes"][0]["properties"]["image"] == "c3725-adventerprisek9-mz.124-25d.image"
    assert topology["topology"]["nodes"][1]["properties"]["image"] == "gns3/webterm:lastest"


def test_export_with_images(tmpdir, project, async_run):
    """
    Fix absolute image path
    """
    path = project.path

    os.makedirs(str(tmpdir / "IOS"))
    with open(str(tmpdir / "IOS" / "test.image"), "w+") as f:
        f.write("AAA")

    topology = {
        "topology": {
            "nodes": [
                    {
                        "properties": {
                            "image": "test.image"
                        },
                        "node_type": "dynamips"
                    }
            ]
        }
    }

    with open(os.path.join(path, "test.gns3"), 'w+') as f:
        json.dump(topology, f)

    with patch("gns3server.compute.Dynamips.get_images_directory", return_value=str(tmpdir / "IOS"),):
        z = async_run(export_project(project, str(tmpdir), include_images=True))
        with open(str(tmpdir / 'zipfile.zip'), 'wb') as f:
            for data in z:
                f.write(data)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        myzip.getinfo("images/IOS/test.image")


def test_export_keep_compute_id(tmpdir, project, async_run):
    """
    If we want to restore the same computes we could ask to keep them
    in the file
    """

    with open(os.path.join(project.path, "test.gns3"), 'w+') as f:
        data = {
            "topology": {
                "computes": [
                    {
                        "compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0",
                        "host": "127.0.0.1",
                        "name": "Remote 1",
                        "port": 8001,
                        "protocol": "http"
                    }
                ],
                "nodes": [
                    {
                        "compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0",
                        "node_type": "vpcs"
                    }
                ]
            }
        }
        json.dump(data, f)

    z = async_run(export_project(project, str(tmpdir), keep_compute_id=True))

    with open(str(tmpdir / 'zipfile.zip'), 'wb') as f:
        for data in z:
            f.write(data)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        with myzip.open("project.gns3") as myfile:
            topo = json.loads(myfile.read().decode())["topology"]
            assert topo["nodes"][0]["compute_id"] == "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0"
            assert len(topo["computes"]) == 1
