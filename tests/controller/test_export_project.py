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


import os
import json
import pytest
import aiohttp
import zipfile
import stat

from pathlib import Path
from unittest.mock import patch
from unittest.mock import MagicMock
from tests.utils import AsyncioMagicMock, AsyncioBytesIO

from gns3server.controller.project import Project
from gns3server.controller.export_project import export_project, _is_exportable
from gns3server.utils.asyncio import aiozipstream


@pytest.fixture
async def project(controller):

    p = Project(controller=controller, name="test")
    p.dump = MagicMock()
    return p


@pytest.fixture
async def node(controller, project):

    compute = MagicMock()
    compute.id = "local"

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    return node


async def write_file(path, z):

    with open(path, 'wb') as f:
        async for chunk in z:
            f.write(chunk)


def test_exportable_files():

    assert _is_exportable("hello/world")
    assert not _is_exportable("project-files/tmp")
    assert not _is_exportable("project-files/test_log.txt")
    assert not _is_exportable("project-files/test.log")
    assert not _is_exportable("test/snapshots")
    assert not _is_exportable("test/project-files/snapshots")
    assert not _is_exportable("test/project-files/snapshots/test.gns3p")


async def test_export(tmpdir, project):

    path = project.path
    os.makedirs(os.path.join(path, "vm-1", "dynamips"))

    os.makedirs(str(tmpdir / "IOS"))
    with open(str(tmpdir / "IOS" / "test.image"), "w+") as f:
        f.write("AAA")

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
                        "node_type": "dynamips",
                        "properties": {
                            "image": "test.image"
                        }
                    }
                ]
            }
        }
        json.dump(data, f)

    with open(os.path.join(path, "vm-1", "dynamips", "test"), 'w+') as f:
        f.write("HELLO")
    with open(os.path.join(path, "vm-1", "dynamips", "test_log.txt"), 'w+') as f:
        f.write("LOG")
    os.makedirs(os.path.join(path, "vm-1", "dynamips", "empty-dir"))
    os.makedirs(os.path.join(path, "project-files", "snapshots"))
    with open(os.path.join(path, "project-files", "snapshots", "test"), 'w+') as f:
        f.write("WORLD")

    os.symlink("/tmp/anywhere", os.path.join(path, "vm-1", "dynamips", "symlink"))

    with aiozipstream.ZipFile() as z:
        with patch("gns3server.compute.Dynamips.get_images_directory", return_value=str(tmpdir / "IOS"),):
            await export_project(z, project, str(tmpdir), include_images=False)
            await write_file(str(tmpdir / 'zipfile.zip'), z)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        with myzip.open("vm-1/dynamips/test") as myfile:
            content = myfile.read()
            assert content == b"HELLO"

        assert 'test.gns3' not in myzip.namelist()
        assert 'project.gns3' in myzip.namelist()
        assert 'vm-1/dynamips/empty-dir/' in myzip.namelist()
        assert 'project-files/snapshots/test' not in myzip.namelist()
        assert 'vm-1/dynamips/test_log.txt' not in myzip.namelist()
        assert 'images/IOS/test.image' not in myzip.namelist()

        assert 'vm-1/dynamips/symlink' in myzip.namelist()
        zip_info = myzip.getinfo('vm-1/dynamips/symlink')
        assert stat.S_ISLNK(zip_info.external_attr >> 16)

        with myzip.open("project.gns3") as myfile:
            topo = json.loads(myfile.read().decode())["topology"]
            assert topo["nodes"][0]["compute_id"] == "local"  # All node should have compute_id local after export
            assert topo["computes"] == []


# async def test_export_vm(tmpdir, project):
#     """
#     If data is on a remote server export it locally before
#     sending it in the archive.
#     """
#
#     compute = MagicMock()
#     compute.id = "vm"
#     compute.list_files = AsyncioMagicMock(return_value=[{"path": "vm-1/dynamips/test"}])
#
#     # Fake file that will be download from the vm
#     mock_response = AsyncioMagicMock()
#     mock_response.content = AsyncioBytesIO()
#     await mock_response.content.write(b"HELLO")
#     mock_response.content.seek(0)
#     compute.download_file = AsyncioMagicMock(return_value=mock_response)
#
#     project._project_created_on_compute.add(compute)
#
#     path = project.path
#     os.makedirs(os.path.join(path, "vm-1", "dynamips"))
#
#     # The .gns3 should be renamed project.gns3 in order to simplify import
#     with open(os.path.join(path, "test.gns3"), 'w+') as f:
#         f.write("{}")
#
#     with aiozipstream.ZipFile() as z:
#         await export_project(z, project, str(tmpdir))
#         assert compute.list_files.called
#         await write_file(str(tmpdir / 'zipfile.zip'), z)
#
#     with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
#         with myzip.open("vm-1/dynamips/test") as myfile:
#             content = myfile.read()
#             assert content == b"HELLO"


async def test_export_disallow_running(tmpdir, project, node):
    """
    Disallow export when a node is running
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
        with aiozipstream.ZipFile() as z:
            await export_project(z, project, str(tmpdir))


async def test_export_disallow_some_type(tmpdir, project):
    """
    Disallow export for some node type
    """

    path = project.path

    topology = {
        "topology": {
            "nodes": [
                {
                    "node_type": "vmware"
                }
            ]
        }
    }

    with open(os.path.join(path, "test.gns3"), 'w+') as f:
        json.dump(topology, f)

    with pytest.raises(aiohttp.web.HTTPConflict):
        with aiozipstream.ZipFile() as z:
            await export_project(z, project, str(tmpdir))
    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir), allow_all_nodes=True)

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
        with aiozipstream.ZipFile() as z:
            await export_project(z, project, str(tmpdir), allow_all_nodes=True)


async def test_export_fix_path(tmpdir, project):
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

    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir))
        await write_file(str(tmpdir / 'zipfile.zip'), z)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        with myzip.open("project.gns3") as myfile:
            content = myfile.read().decode()
            topology = json.loads(content)
    assert topology["topology"]["nodes"][0]["properties"]["image"] == "c3725-adventerprisek9-mz.124-25d.image"
    assert topology["topology"]["nodes"][1]["properties"]["image"] == "gns3/webterm:lastest"


async def test_export_with_images(tmpdir, project):
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

    with aiozipstream.ZipFile() as z:
        with patch("gns3server.compute.Dynamips.get_images_directory", return_value=str(tmpdir / "IOS"),):
            await export_project(z, project, str(tmpdir), include_images=True)
            await write_file(str(tmpdir / 'zipfile.zip'), z)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        myzip.getinfo("images/IOS/test.image")


async def test_export_keep_compute_ids(tmpdir, project):
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

    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir), keep_compute_ids=True)
        await write_file(str(tmpdir / 'zipfile.zip'), z)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        with myzip.open("project.gns3") as myfile:
            topo = json.loads(myfile.read().decode())["topology"]
            assert topo["nodes"][0]["compute_id"] == "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0"
            assert len(topo["computes"]) == 1


async def test_export_images_from_vm(tmpdir, project):
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
    await mock_response.content.write(b"HELLO")
    mock_response.content.seek(0)
    mock_response.status = 200
    compute.download_file = AsyncioMagicMock(return_value=mock_response)

    mock_response = AsyncioMagicMock()
    mock_response.content = AsyncioBytesIO()
    await mock_response.content.write(b"IMAGE")
    mock_response.content.seek(0)
    mock_response.status = 200
    compute.download_image = AsyncioMagicMock(return_value=mock_response)


    project._project_created_on_compute.add(compute)

    path = project.path
    os.makedirs(os.path.join(path, "vm-1", "dynamips"))

    topology = {
        "topology": {
            "nodes": [
                    {
                        "compute_id": "vm",
                        "properties": {
                            "image": "test.image"
                        },
                        "node_type": "dynamips"
                    }
            ]
        }
    }

    # The .gns3 should be renamed project.gns3 in order to simplify import
    with open(os.path.join(path, "test.gns3"), 'w+') as f:
        f.write(json.dumps(topology))

    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir), include_images=True)
        assert compute.list_files.called
        await write_file(str(tmpdir / 'zipfile.zip'), z)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        with myzip.open("vm-1/dynamips/test") as myfile:
            content = myfile.read()
            assert content == b"HELLO"

        with myzip.open("images/dynamips/test.image") as myfile:
            content = myfile.read()
            assert content == b"IMAGE"


async def test_export_with_ignoring_snapshots(tmpdir, project):

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

    # create snapshot directory
    snapshots_dir = os.path.join(project.path, 'snapshots')
    os.makedirs(snapshots_dir)
    Path(os.path.join(snapshots_dir, 'snap.gns3project')).touch()

    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir), keep_compute_ids=True)
        await write_file(str(tmpdir / 'zipfile.zip'), z)

    with zipfile.ZipFile(str(tmpdir / 'zipfile.zip')) as myzip:
        assert not os.path.join('snapshots', 'snap.gns3project') in [f.filename for f in myzip.filelist]
