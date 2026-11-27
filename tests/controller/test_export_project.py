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


import json
import os
import stat
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from gns3server.controller.controller_error import ControllerError
from gns3server.controller.export_project import _is_exportable, export_project
from gns3server.controller.import_project import import_project
from gns3server.controller.project import Project
from gns3server.schemas.configurations import Selection
from gns3server.services.configurations.sets.selections import SelectionStore
from gns3server.services.configurations.sets.store import StartupStore
from gns3server.services.configurations.shared.safe_io import read_json, write_json
from gns3server.utils.asyncio import aiozipstream
from tests.support.configurations import save_startup
from tests.utils import AsyncioBytesIO, AsyncioMagicMock


@pytest_asyncio.fixture
async def project(controller):

    p = Project(controller=controller, name="test")
    p.dump = MagicMock()
    return p


@pytest_asyncio.fixture
async def node(controller, project):

    compute = MagicMock()
    compute.id = "local"

    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node = await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})
    return node


@pytest.mark.asyncio
async def write_file(path, z):

    with open(path, "wb") as f:
        async for chunk in z:
            f.write(chunk)


def test_exportable_files():

    assert _is_exportable("hello/world")
    assert not _is_exportable("project-files/tmp")
    assert not _is_exportable("project-files/test_log.txt")
    assert _is_exportable("project-files/startup-configs/configurations.json")
    assert not _is_exportable("project-files/qemu/abc/.asav-recovery/console.bin")
    # The staged media and the journal travel together: Start needs the file the journal says is staged.
    assert _is_exportable("project-files/qemu/abc/startup-media.iso")
    assert _is_exportable("project-files/qemu/abc/startup-media.img")
    assert not _is_exportable("project-files/test.log")
    assert not _is_exportable("test/project-files/snapshots")
    assert not _is_exportable("test/project-files/snapshots/test.gns3p")


@pytest.mark.parametrize(
    "name,exported",
    [
        (".prepare-ab12/flash.raw", False),
        (".prepare-ab12/nested/partition.img", False),
        (".disk-copy-x1y2", False),
        ("hda_disk.qcow2", True),
        (".startup-runtime.json", True),
        ("startup-media.iso", True),
    ],
)
@pytest.mark.parametrize("include_snapshots", [False, True])
def test_preparation_scratch_files_are_never_exported(name, exported, include_snapshots):
    path = os.path.join("project-files", "qemu", "node-id", *name.split("/"))
    assert _is_exportable(path, include_snapshots) is exported
    assert _is_exportable(os.path.join(os.sep, "projects", "p", path), include_snapshots) is exported


@pytest.mark.asyncio
async def test_export(tmpdir, project):

    path = project.path
    os.makedirs(os.path.join(path, "vm-1", "dynamips"))

    os.makedirs(str(tmpdir / "IOS"))
    with open(str(tmpdir / "IOS" / "test.image"), "w+") as f:
        f.write("AAA")

    # The .gns3 should be renamed project.gns3 in order to simplify import
    with open(os.path.join(path, "test.gns3"), "w+") as f:
        data = {
            "topology": {
                "computes": [
                    {
                        "compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0",
                        "host": "127.0.0.1",
                        "name": "Remote 1",
                        "port": 8001,
                        "protocol": "http",
                    }
                ],
                "nodes": [
                    {
                        "compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0",
                        "node_type": "dynamips",
                        "properties": {"image": "test.image"},
                    }
                ],
            }
        }
        json.dump(data, f)

    with open(os.path.join(path, "vm-1", "dynamips", "test"), "w+") as f:
        f.write("HELLO")
    with open(os.path.join(path, "vm-1", "dynamips", "test_log.txt"), "w+") as f:
        f.write("LOG")
    os.makedirs(os.path.join(path, "vm-1", "dynamips", "empty-dir"))
    os.makedirs(os.path.join(path, "project-files", "snapshots"))
    with open(os.path.join(path, "project-files", "snapshots", "test"), "w+") as f:
        f.write("WORLD")

    os.symlink("/tmp/anywhere", os.path.join(path, "vm-1", "dynamips", "symlink"))

    with aiozipstream.ZipFile() as z:
        with patch(
            "gns3server.compute.Dynamips.get_images_directory",
            return_value=str(tmpdir / "IOS"),
        ):
            await export_project(z, project, str(tmpdir), include_images=False)
            await write_file(str(tmpdir / "zipfile.zip"), z)

    with zipfile.ZipFile(str(tmpdir / "zipfile.zip")) as myzip:
        with myzip.open("vm-1/dynamips/test") as myfile:
            content = myfile.read()
            assert content == b"HELLO"

        assert "test.gns3" not in myzip.namelist()
        assert "project.gns3" in myzip.namelist()
        assert "vm-1/dynamips/empty-dir/" in myzip.namelist()
        assert "project-files/snapshots/test" not in myzip.namelist()
        assert "vm-1/dynamips/test_log.txt" not in myzip.namelist()
        assert "images/IOS/test.image" not in myzip.namelist()

        assert "vm-1/dynamips/symlink" in myzip.namelist()
        zip_info = myzip.getinfo("vm-1/dynamips/symlink")
        assert stat.S_ISLNK(zip_info.external_attr >> 16)

        with myzip.open("project.gns3") as myfile:
            topo = json.loads(myfile.read().decode())["topology"]
            assert topo["nodes"][0]["compute_id"] == "local"  # All node should have compute_id local after export
            assert topo["computes"] == []


# @pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_export_disallow_running(tmpdir, project, node):
    """
    Disallow export when a node is running
    """

    path = project.path

    topology = {"topology": {"nodes": [{"node_type": "dynamips"}]}}

    with open(os.path.join(path, "test.gns3"), "w+") as f:
        json.dump(topology, f)

    node._status = "started"
    with pytest.raises(ControllerError):
        with aiozipstream.ZipFile() as z:
            await export_project(z, project, str(tmpdir))


@pytest.mark.asyncio
async def test_export_disallow_some_type(tmpdir, project):
    """
    Disallow export for some node type
    """

    path = project.path

    topology = {"topology": {"nodes": [{"node_type": "vmware"}]}}

    with open(os.path.join(path, "test.gns3"), "w+") as f:
        json.dump(topology, f)

    with pytest.raises(ControllerError):
        with aiozipstream.ZipFile() as z:
            await export_project(z, project, str(tmpdir))
    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir), allow_all_nodes=True)

    # VirtualBox is always disallowed
    topology = {"topology": {"nodes": [{"node_type": "virtualbox", "properties": {"linked_clone": True}}]}}
    with open(os.path.join(path, "test.gns3"), "w+") as f:
        json.dump(topology, f)
    with pytest.raises(ControllerError):
        with aiozipstream.ZipFile() as z:
            await export_project(z, project, str(tmpdir), allow_all_nodes=True)


@pytest.mark.asyncio
async def test_project_export_keeps_set_and_selection_revisions_together(tmpdir, project):
    store, selections = StartupStore(project), SelectionStore(project)
    saved, lab = store.create_set("Lab", revision=0)
    node_id = uuid4()
    choice = selections.assign(node_id, Selection(kind="set", set_id=lab.id), 0)
    filename = str(tmpdir / "startup.zip")
    with aiozipstream.ZipFile() as stream:
        await export_project(stream, project, str(tmpdir))
        # The files change before ZipStream begins reading its inputs.
        pending = saved.model_copy(update={"sets": (saved.sets[0],)})
        updated = selections.prepare_updates({node_id: Selection()}, choice["revision"])
        store.write(pending, revision=saved.revision, assignments=updated)
        await write_file(filename, stream)
    with zipfile.ZipFile(filename) as exported:
        for relative, expected in (
            ("configurations.json", saved.model_dump(mode="json")),
            ("nodes/selections.json", choice),
        ):
            assert json.loads(exported.read(f"project-files/startup-configs/{relative}")) == expected


@pytest.mark.asyncio
async def test_export_fix_path(tmpdir, project):
    """
    Fix absolute image path, except for Docker
    """

    path = project.path

    topology = {
        "topology": {
            "nodes": [
                {"properties": {"image": "/tmp/c3725-adventerprisek9-mz.124-25d.image"}, "node_type": "dynamips"},
                {"properties": {"image": "gns3/webterm:lastest"}, "node_type": "docker"},
            ]
        }
    }

    with open(os.path.join(path, "test.gns3"), "w+") as f:
        json.dump(topology, f)

    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir))
        await write_file(str(tmpdir / "zipfile.zip"), z)

    with zipfile.ZipFile(str(tmpdir / "zipfile.zip")) as myzip:
        with myzip.open("project.gns3") as myfile:
            content = myfile.read().decode()
            topology = json.loads(content)
    assert topology["topology"]["nodes"][0]["properties"]["image"] == "c3725-adventerprisek9-mz.124-25d.image"
    assert topology["topology"]["nodes"][1]["properties"]["image"] == "gns3/webterm:lastest"


@pytest.mark.asyncio
async def test_export_with_images(tmpdir, project):
    """
    Fix absolute image path
    """
    path = project.path

    os.makedirs(str(tmpdir / "IOS"))
    with open(str(tmpdir / "IOS" / "test.image"), "w+") as f:
        f.write("AAA")

    topology = {"topology": {"nodes": [{"properties": {"image": "test.image"}, "node_type": "dynamips"}]}}

    with open(os.path.join(path, "test.gns3"), "w+") as f:
        json.dump(topology, f)

    with aiozipstream.ZipFile() as z:
        with patch(
            "gns3server.compute.Dynamips.get_images_directory",
            return_value=str(tmpdir / "IOS"),
        ):
            await export_project(z, project, str(tmpdir), include_images=True)
            await write_file(str(tmpdir / "zipfile.zip"), z)

    with zipfile.ZipFile(str(tmpdir / "zipfile.zip")) as myzip:
        myzip.getinfo("images/IOS/test.image")


@pytest.mark.asyncio
async def test_export_keep_compute_ids(tmpdir, project):
    """
    If we want to restore the same computes we could ask to keep them
    in the file
    """

    with open(os.path.join(project.path, "test.gns3"), "w+") as f:
        data = {
            "topology": {
                "computes": [
                    {
                        "compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0",
                        "host": "127.0.0.1",
                        "name": "Remote 1",
                        "port": 8001,
                        "protocol": "http",
                    }
                ],
                "nodes": [{"compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0", "node_type": "vpcs"}],
            }
        }
        json.dump(data, f)

    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir), keep_compute_ids=True)
        await write_file(str(tmpdir / "zipfile.zip"), z)

    with zipfile.ZipFile(str(tmpdir / "zipfile.zip")) as myzip:
        with myzip.open("project.gns3") as myfile:
            topo = json.loads(myfile.read().decode())["topology"]
            assert topo["nodes"][0]["compute_id"] == "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0"
            assert len(topo["computes"]) == 1


@pytest.mark.asyncio
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
        "topology": {"nodes": [{"compute_id": "vm", "properties": {"image": "test.image"}, "node_type": "dynamips"}]}
    }

    # The .gns3 should be renamed project.gns3 in order to simplify import
    with open(os.path.join(path, "test.gns3"), "w+") as f:
        f.write(json.dumps(topology))

    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir), include_images=True)
        assert compute.list_files.called
        await write_file(str(tmpdir / "zipfile.zip"), z)

    with zipfile.ZipFile(str(tmpdir / "zipfile.zip")) as myzip:
        with myzip.open("vm-1/dynamips/test") as myfile:
            content = myfile.read()
            assert content == b"HELLO"

        with myzip.open("images/dynamips/test.image") as myfile:
            content = myfile.read()
            assert content == b"IMAGE"


@pytest.mark.asyncio
async def test_export_with_ignoring_snapshots(tmpdir, project):

    with open(os.path.join(project.path, "test.gns3"), "w+") as f:
        data = {
            "topology": {
                "computes": [
                    {
                        "compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0",
                        "host": "127.0.0.1",
                        "name": "Remote 1",
                        "port": 8001,
                        "protocol": "http",
                    }
                ],
                "nodes": [{"compute_id": "6b7149c8-7d6e-4ca0-ab6b-daa8ab567be0", "node_type": "vpcs"}],
            }
        }
        json.dump(data, f)

    # create snapshot directory
    snapshots_dir = os.path.join(project.path, "snapshots")
    os.makedirs(snapshots_dir)
    Path(os.path.join(snapshots_dir, "snap.gns3project")).touch()

    with aiozipstream.ZipFile() as z:
        await export_project(z, project, str(tmpdir), keep_compute_ids=True)
        await write_file(str(tmpdir / "zipfile.zip"), z)

    with zipfile.ZipFile(str(tmpdir / "zipfile.zip")) as myzip:
        assert os.path.join("snapshots", "snap.gns3project") not in [f.filename for f in myzip.filelist]


@pytest.mark.asyncio
async def test_export_two_isos_with_identical_filenames(tmpdir, project):
    from gns3server.compute.qemu import Qemu
    from gns3server.controller.import_project import _import_images

    root = Path(str(tmpdir)) / "QEMU"
    installer = root / "windows/install.iso"
    drivers = root / "drivers/install.iso"
    for image, data in ((installer, b"installer"), (drivers, b"drivers")):
        image.parent.mkdir(parents=True)
        image.write_bytes(data)
    topology = {
        "topology": {
            "nodes": [
                {
                    "node_type": "qemu",
                    "properties": {
                        "cdrom_image": str(installer),
                        "cdrom2_image": str(drivers),
                    },
                }
            ]
        }
    }
    Path(project.path, "test.gns3").write_text(json.dumps(topology))
    archive = str(tmpdir / "iso-project.zip")
    with aiozipstream.ZipFile() as stream:
        with patch.object(Qemu, "get_images_directory", return_value=str(root)):
            await export_project(stream, project, str(tmpdir), include_images=True)
            await write_file(archive, stream)
    with zipfile.ZipFile(archive) as stream:
        properties = json.loads(stream.read("project.gns3"))["topology"]["nodes"][0]["properties"]
        assert properties["cdrom_image"] != properties["cdrom2_image"]
        assert stream.read("images/QEMU/" + properties["cdrom_image"]) == b"installer"
        assert stream.read("images/QEMU/" + properties["cdrom2_image"]) == b"drivers"
        assert len(stream.namelist()) == len(set(stream.namelist()))
        destination = Path(str(tmpdir)) / "unpacked"
        stream.extractall(destination)
    controller = MagicMock()
    imported_images = Path(str(tmpdir)) / "imported-images"
    controller.images_path.return_value = str(imported_images)
    await _import_images(controller, str(destination / "images"))
    assert (imported_images / "QEMU" / properties["cdrom_image"]).read_bytes() == b"installer"
    assert (imported_images / "QEMU" / properties["cdrom2_image"]).read_bytes() == b"drivers"


@pytest_asyncio.fixture
async def persisted_project(controller):
    return await controller.add_project(name="Test")


async def _seed_startup_project(project, controller):
    compute = MagicMock()
    compute.id = "local"
    response = SimpleNamespace(json={"console": 2048})
    compute.post = AsyncMock(return_value=response)
    compute.get = AsyncMock(return_value=response)
    compute.delete = AsyncMock(return_value=response)
    compute.put = AsyncMock(return_value=response)
    controller._computes["local"] = compute
    node = await project.add_node(compute, "Router", str(uuid4()), node_type="iou", properties={})
    assignments = SelectionStore(project)
    store = StartupStore(project)
    save_startup(store, node.id, "cisco_ios_telnet", "hostname SavedRouter\r\n")
    assignments.assign(node.id, Selection(kind="set", set_id=store.read().selected), 0)
    write_json(assignments.root / "managed" / f"{node.id}.json", {"managed": True})
    journal = Path(project.path) / "project-files" / "iou" / node.id / ".startup-runtime.json"
    write_json(journal, {"version": 1, "generation": 2, "state": "initialized"})
    project.dump()
    return node, journal


def _assert_startup_project_saved(project, node_id):
    store = StartupStore(project)
    entry = store.read().sets[0].nodes[UUID(node_id)]
    assert entry.enabled and entry.content == "hostname SavedRouter\r\n"
    assignments = SelectionStore(project)
    assert assignments.selections()["nodes"] == {node_id: {"kind": "set", "set_id": str(store.read().selected)}}
    assert read_json(assignments.root / "managed" / f"{node_id}.json") == {"managed": True}
    journal = Path(project.path) / "project-files" / "iou" / node_id / ".startup-runtime.json"
    assert read_json(journal)["generation"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["portable", "duplicate"])
async def test_project_roundtrip_remaps_sets_assignment_and_journal(persisted_project, controller, tmp_path, method):
    project = persisted_project
    node, journal = await _seed_startup_project(project, controller)
    original_journal = journal.read_bytes()
    if method == "duplicate":
        copied = await project.duplicate(name="Copy")
    else:
        archive = tmp_path / "project.zip"
        with tempfile.TemporaryDirectory(dir=tmp_path) as temporary, aiozipstream.ZipFile() as stream:
            await export_project(stream, project, temporary)
            await write_file(archive, stream)
        with archive.open("rb") as stream:
            copied = await import_project(controller, str(uuid4()), stream, name="Imported", keep_compute_ids=True)
    topology = json.loads((Path(copied.path) / copied._filename).read_bytes())
    new_id = topology["topology"]["nodes"][0]["node_id"]
    assert new_id != node.id and copied.id != project.id
    _assert_startup_project_saved(copied, new_id)
    root = SelectionStore(copied).root
    assert not (root / "managed" / f"{node.id}.json").exists()
    assert not (Path(copied.path) / "project-files" / "iou" / node.id).exists()
    # Portability never edits the original project's assignment or recovery data.
    assert journal.read_bytes() == original_journal


@pytest.mark.asyncio
async def test_actual_snapshot_restore_restores_assignment_and_runtime_without_start(persisted_project, controller):
    project = persisted_project
    node, journal = await _seed_startup_project(project, controller)
    snapshot = await project.snapshot("saved-startup-state")
    assignments = SelectionStore(project)
    assignments.assign(node.id, Selection(kind="none"), 1)
    write_json(journal, {"version": 1, "generation": 9, "state": "clean"})
    store = StartupStore(project)
    save_startup(store, node.id, "cisco_ios_telnet", "hostname Changed\n", enabled=False)
    controller._notification = MagicMock()
    restored = await snapshot.restore()
    assert restored.id == project.id and list(restored.nodes) == [node.id]
    _assert_startup_project_saved(restored, node.id)
    compute = controller._computes["local"]
    assert all(not call.args[0].endswith("/start") for call in compute.post.call_args_list)
