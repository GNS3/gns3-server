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
import uuid
import json
import zipfile


from tests.utils import asyncio_patch, AsyncioMagicMock

from gns3server.controller.project import Project
from gns3server.controller.import_project import import_project, _move_files_to_compute

from gns3server.version import __version__


def test_import_project(async_run, tmpdir, controller):
    project_id = str(uuid.uuid4())

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "auto_open": True,
        "auto_start": True,
        "topology": {
        },
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)
    with open(str(tmpdir / "b.png"), 'w+') as f:
        f.write("B")

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")
        myzip.write(str(tmpdir / "b.png"), "b.png")
        myzip.write(str(tmpdir / "b.png"), "project-files/dynamips/test")
        myzip.write(str(tmpdir / "b.png"), "project-files/qemu/test")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f))

    assert project.name == "test"
    assert project.id == project_id

    assert os.path.exists(os.path.join(project.path, "b.png"))
    assert not os.path.exists(os.path.join(project.path, "project.gns3"))
    assert os.path.exists(os.path.join(project.path, "test.gns3"))
    assert os.path.exists(os.path.join(project.path, "project-files/dynamips/test"))
    assert os.path.exists(os.path.join(project.path, "project-files/qemu/test"))

    # A new project name is generated when you import twice the same name
    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, str(uuid.uuid4()), f))
    assert project.auto_open is False
    assert project.auto_start is False
    assert project.name != "test"


def test_import_project_override(async_run, tmpdir, controller):
    """
    In the case of snapshot we will import a project for
    override the previous keeping the same project id & location
    """
    project_id = str(uuid.uuid4())

    topology = {
        "project_id": project_id,
        "name": "test",
        "topology": {
        },
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f, location=str(tmpdir)))

    assert project.name == "test"
    assert project.id == project_id

    # Overide the project with same project
    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f, location=str(tmpdir)))
    assert project.id == project_id
    assert project.name == "test"


def test_import_upgrade(async_run, tmpdir, controller):
    """
    Topology made for previous GNS3 version are upgraded during the process
    """
    project_id = str(uuid.uuid4())

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "topology": {
        },
        "version": "1.4.2"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f))

    with open(os.path.join(project.path, "test.gns3")) as f:
        topo = json.load(f)
        assert topo["version"] == __version__


def test_import_with_images(tmpdir, async_run, controller):

    project_id = str(uuid.uuid4())

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "topology": {
        },
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    with open(str(tmpdir / "test.image"), 'w+') as f:
        f.write("B")

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")
        myzip.write(str(tmpdir / "test.image"), "images/IOS/test.image")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f))

    assert not os.path.exists(os.path.join(project.path, "images/IOS/test.image"))

    path = os.path.join(project._config().get("images_path"), "IOS", "test.image")
    assert os.path.exists(path), path


def test_import_iou_linux_no_vm(linux_platform, async_run, tmpdir, controller):
    """
    On non linux host IOU should be local if we don't have a GNS3 VM
    """
    project_id = str(uuid.uuid4())

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "type": "topology",
        "topology": {
            "nodes": [
                {
                    "compute_id": "local",
                    "node_type": "iou",
                    "name": "test",
                    "properties": {}
                }
            ],
            "links": [],
            "computes": [],
            "drawings": []
        },
        "revision": 5,
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f))

    with open(os.path.join(project.path, "test.gns3")) as f:
        topo = json.load(f)
        assert topo["topology"]["nodes"][0]["compute_id"] == "local"


def test_import_iou_linux_with_vm(linux_platform, async_run, tmpdir, controller):
    """
    On non linux host IOU should be vm if we have a GNS3 VM configured
    """
    project_id = str(uuid.uuid4())
    controller._computes["vm"] = AsyncioMagicMock()

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "type": "topology",
        "topology": {
            "nodes": [
                {
                    "compute_id": "local",
                    "node_id": "0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b",
                    "node_type": "iou",
                    "name": "test",
                    "properties": {}
                }
            ],
            "links": [],
            "computes": [],
            "drawings": []
        },
        "revision": 5,
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f))

    with open(os.path.join(project.path, "test.gns3")) as f:
        topo = json.load(f)
        assert topo["topology"]["nodes"][0]["compute_id"] == "vm"


def test_import_nat_non_linux(windows_platform, async_run, tmpdir, controller):
    """
    On non linux host NAT should be moved to the GNS3 VM
    """
    project_id = str(uuid.uuid4())
    controller._computes["vm"] = AsyncioMagicMock()

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "type": "topology",
        "topology": {
            "nodes": [
                {
                    "compute_id": "local",
                    "node_id": "0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b",
                    "node_type": "nat",
                    "name": "test",
                    "properties": {}
                }
            ],
            "links": [],
            "computes": [],
            "drawings": []
        },
        "revision": 5,
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f))

    with open(os.path.join(project.path, "test.gns3")) as f:
        topo = json.load(f)
        assert topo["topology"]["nodes"][0]["compute_id"] == "vm"


def test_import_iou_non_linux(windows_platform, async_run, tmpdir, controller):
    """
    On non linux host IOU should be moved to the GNS3 VM
    """
    project_id = str(uuid.uuid4())
    controller._computes["vm"] = AsyncioMagicMock()

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "type": "topology",
        "topology": {
            "nodes": [
                {
                    "compute_id": "local",
                    "node_id": "0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b",
                    "node_type": "iou",
                    "name": "test",
                    "properties": {}
                },
                {
                    "compute_id": "local",
                    "node_type": "vpcs",
                    "name": "test2",
                    "properties": {}
                }
            ],
            "links": [],
            "computes": [],
            "drawings": []
        },
        "revision": 5,
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")

    with open(zip_path, "rb") as f:
        with asyncio_patch("gns3server.controller.import_project._move_files_to_compute") as mock:
            project = async_run(import_project(controller, project_id, f))
            controller._computes["vm"].post.assert_called_with('/projects', data={'name': 'test', 'project_id': project_id})

    with open(os.path.join(project.path, "test.gns3")) as f:
        topo = json.load(f)
        assert topo["topology"]["nodes"][0]["compute_id"] == "vm"
        assert topo["topology"]["nodes"][1]["compute_id"] == "local"

    mock.assert_called_with(controller._computes["vm"], project_id, project.path, os.path.join('project-files', 'iou', topo["topology"]["nodes"][0]['node_id']))


def test_import_node_id(linux_platform, async_run, tmpdir, controller):
    """
    When importing a node, node_id should change
    """
    project_id = str(uuid.uuid4())

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "type": "topology",
        "topology": {
            "nodes": [
                {
                    "compute_id": "local",
                    "node_id": "0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b",
                    "node_type": "iou",
                    "name": "test",
                    "properties": {}
                },
                {
                    "compute_id": "local",
                    "node_id": "c3ae286c-c81f-40d9-a2d0-5874b2f2478d",
                    "node_type": "iou",
                    "name": "test2",
                    "properties": {}
                }
            ],
            "links": [
                {
                    "link_id": "b570a150-c09f-47d9-8d32-9ca5b03234d6",
                    "nodes": [
                        {
                            "adapter_number": 0,
                            "node_id": "0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b",
                            "port_number": 0
                        },
                        {
                            "adapter_number": 0,
                            "node_id": "c3ae286c-c81f-40d9-a2d0-5874b2f2478d",
                            "port_number": 0
                        }
                    ]
                }
            ],
            "computes": [],
            "drawings": [
                {
                    "drawing_id": "08d665ba-e982-4d54-82b4-aa0c4d5ba6a3",
                    "rotation": 0,
                    "x": -210,
                    "y": -108,
                    "z": 0
                }
            ]
        },
        "revision": 5,
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    # Fake .gns3project
    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")
        myzip.writestr("project-files/iou/0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b/startup.cfg", "test")
        myzip.writestr("project-files/iou/c3ae286c-c81f-40d9-a2d0-5874b2f2478d/startup.cfg", "test")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f))

    with open(os.path.join(project.path, "test.gns3")) as f:
        topo = json.load(f)
        # Node id should have change
        assert topo["topology"]["nodes"][0]["node_id"] not in ["0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b", "c3ae286c-c81f-40d9-a2d0-5874b2f2478d"]

        # Link should have change
        link = topo["topology"]["links"][0]
        assert link["link_id"] != "b570a150-c09f-47d9-8d32-9ca5b03234d6"
        assert link["nodes"][0]["node_id"] not in ["0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b", "c3ae286c-c81f-40d9-a2d0-5874b2f2478d"]

        # Drawing id should change
        assert topo["topology"]["drawings"][0]["drawing_id"] != "08d665ba-e982-4d54-82b4-aa0c4d5ba6a3"

        # Node files should have moved to the new node id
        assert not os.path.exists(os.path.join(project.path, "project-files", "iou", "0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b", "startup.cfg"))
        assert not os.path.exists(os.path.join(project.path, "project-files", "iou", "c3ae286c-c81f-40d9-a2d0-5874b2f2478d", "startup.cfg"))
        assert os.path.exists(os.path.join(project.path, "project-files", "iou", topo["topology"]["nodes"][0]["node_id"], "startup.cfg"))


def test_import_keep_compute_id(windows_platform, async_run, tmpdir, controller):
    """
    On linux host IOU should be moved to the GNS3 VM
    """
    project_id = str(uuid.uuid4())
    controller._computes["vm"] = AsyncioMagicMock()

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "type": "topology",
        "topology": {
            "nodes": [
                {
                    "compute_id": "local",
                    "node_id": "0fd3dd4d-dc93-4a04-a9b9-7396a9e22e8b",
                    "node_type": "iou",
                    "name": "test",
                    "properties": {}
                }
            ],
            "links": [],
            "computes": [],
            "drawings": []
        },
        "revision": 5,
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f, keep_compute_id=True))

    with open(os.path.join(project.path, "test.gns3")) as f:
        topo = json.load(f)
        assert topo["topology"]["nodes"][0]["compute_id"] == "local"


def test_move_files_to_compute(tmpdir, async_run):
    project_id = str(uuid.uuid4())

    os.makedirs(str(tmpdir / "project-files" / "docker"))
    (tmpdir / "project-files" / "docker" / "test").open("w").close()
    (tmpdir / "project-files" / "docker" / "test2").open("w").close()

    with asyncio_patch("gns3server.controller.import_project._upload_file") as mock:
        async_run(_move_files_to_compute(None, project_id, str(tmpdir), os.path.join("project-files", "docker")))

    mock.assert_any_call(None, project_id, str(tmpdir / "project-files" / "docker" / "test"), os.path.join("project-files", "docker", "test"))
    mock.assert_any_call(None, project_id, str(tmpdir / "project-files" / "docker" / "test2"), os.path.join("project-files", "docker", "test2"))
    assert not os.path.exists(str(tmpdir / "project-files" / "docker"))


def test_import_project_name_and_location(async_run, tmpdir, controller):
    """
    Import a project with a different location and name
    """
    project_id = str(uuid.uuid4())

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "topology": {
        },
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f, name="hello", location=str(tmpdir / "hello")))

    assert project.name == "hello"

    assert os.path.exists(str(tmpdir / "hello" / "hello.gns3"))

    # A new project name is generated when you import twice the same name
    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, str(uuid.uuid4()), f, name="hello", location=str(tmpdir / "test")))
    assert project.name == "hello-1"
