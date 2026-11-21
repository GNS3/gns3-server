#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
#

"""
The overlay disks of a distributed copy: the disk images named by the
topology become thin qcow2 overlays, every other file of the QEMU node
directories is copied verbatim and never probed.
"""

import os
import shutil

import pytest

from gns3server.controller import qemu_overlay
from gns3server.controller.controller_error import ControllerError

NODE_ID = "4b2b1e5a-0000-0000-0000-000000000001"


def _topology(disk_properties):
    """
    A topology with a single QEMU node naming its disks.
    """

    return {
        "topology": {
            "nodes": [
                {
                    "node_id": NODE_ID,
                    "node_type": "qemu",
                    "properties": disk_properties,
                }
            ]
        }
    }


@pytest.fixture
def source_project(tmp_path):
    """
    A template project directory with one QEMU node: a disk image, a plain
    config file, and a nested flash directory.
    """

    qemu_dir = tmp_path / "source" / "project-files" / "qemu" / NODE_ID
    qemu_dir.mkdir(parents=True)
    (qemu_dir / "hda_disk.qcow2").write_bytes(b"not really a disk, named by the topology")
    (qemu_dir / "config.txt").write_text("hostname r1")
    flash_dir = qemu_dir / "flash"
    flash_dir.mkdir()
    (flash_dir / "startup.cfg").write_text("boot")
    # files outside the QEMU directories are not touched by the overlay pass
    (tmp_path / "source" / "test.gns3").write_text("{}")
    return tmp_path / "source"


def test_disk_images_become_overlays_and_other_files_are_copied(source_project, tmp_path, monkeypatch):
    """
    The disks named by the node properties are replaced by overlays pointing
    at the template (absolute path, original virtual size); the other files
    are copied verbatim, and only the disks are probed.
    """

    destination = tmp_path / "copy"
    destination.mkdir()

    probed = []
    created = []

    def fake_image_info(qemu_img, path):
        probed.append(os.path.basename(path))
        return {"format": "qcow2", "virtual-size": 42949632}

    def fake_create_overlay(qemu_img, backing_file, overlay_file, info):
        created.append((backing_file, overlay_file, info))
        with open(overlay_file, "w") as f:
            f.write("overlay")

    monkeypatch.setattr(qemu_overlay, "find_qemu_img", lambda: "/fake/qemu-img")
    monkeypatch.setattr(qemu_overlay, "_image_info", fake_image_info)
    monkeypatch.setattr(qemu_overlay, "_create_overlay", fake_create_overlay)

    topology = _topology({"hda_disk_image": "hda_disk.qcow2"})
    overlays = qemu_overlay.create_overlay_disks(str(source_project), str(destination), topology)
    assert overlays == 1

    # exactly the topology's disk is probed: the config files never reach
    # qemu-img (which would report any file as a raw disk)
    assert probed == ["hda_disk.qcow2"]

    # exactly one overlay, pointing at the template's disk by absolute path
    (backing_file, overlay_file, info) = created[0]
    assert backing_file == str(source_project / "project-files" / "qemu" / NODE_ID / "hda_disk.qcow2")
    assert os.path.isabs(backing_file)
    assert info["virtual-size"] == 42949632
    assert overlay_file.endswith("hda_disk.qcow2")

    # the non-image files ride along verbatim, nested directories included
    assert (destination / "project-files" / "qemu" / NODE_ID / "config.txt").read_text() == "hostname r1"
    assert (destination / "project-files" / "qemu" / NODE_ID / "flash" / "startup.cfg").read_text() == "boot"


def test_files_not_named_by_the_topology_are_never_probed(source_project, tmp_path, monkeypatch):
    """
    qemu-img reports any regular file as a raw image, so probing cannot tell
    a disk from a log. A file the topology does not name (an orphan node
    directory, a leftover image) is copied verbatim and never probed, and
    qemu-img is not even needed when no disk is named.
    """

    destination = tmp_path / "copy"
    destination.mkdir()

    # an orphan node directory: no node of the topology has this id
    orphan_dir = source_project / "project-files" / "qemu" / "4b2b1e5a-0000-0000-0000-000000000099"
    orphan_dir.mkdir()
    (orphan_dir / "hda_disk.qcow2").write_bytes(b"a leftover disk of a deleted node")

    monkeypatch.setattr(
        qemu_overlay,
        "find_qemu_img",
        lambda: (_ for _ in ()).throw(AssertionError("qemu-img must not be needed without named disks")),
    )

    # a topology whose only node names no disk: every file rides along verbatim
    overlays = qemu_overlay.create_overlay_disks(str(source_project), str(destination), _topology({}))
    assert overlays == 0
    assert (destination / "project-files" / "qemu" / NODE_ID / "hda_disk.qcow2").read_bytes() == (
        source_project / "project-files" / "qemu" / NODE_ID / "hda_disk.qcow2"
    ).read_bytes()
    assert (destination / "project-files" / "qemu" / NODE_ID / "config.txt").read_text() == "hostname r1"
    assert (orphan_dir / "hda_disk.qcow2").exists()

    # the orphan directory is copied too (nothing of the template is lost)
    copied_orphan = destination / "project-files" / "qemu" / "4b2b1e5a-0000-0000-0000-000000000099"
    assert (copied_orphan / "hda_disk.qcow2").read_bytes() == (orphan_dir / "hda_disk.qcow2").read_bytes()


def test_a_named_disk_that_cannot_be_probed_is_copied_verbatim(source_project, tmp_path, monkeypatch):
    """
    A file the topology names as a disk but that qemu-img cannot read falls
    back to a verbatim copy: the recipient gets a private full disk instead
    of a thin one, never a lost one.
    """

    destination = tmp_path / "copy"
    destination.mkdir()

    monkeypatch.setattr(qemu_overlay, "find_qemu_img", lambda: "/fake/qemu-img")
    monkeypatch.setattr(qemu_overlay, "_image_info", lambda qemu_img, path: None)

    topology = _topology({"hda_disk_image": "hda_disk.qcow2"})
    assert qemu_overlay.create_overlay_disks(str(source_project), str(destination), topology) == 0
    assert (destination / "project-files" / "qemu" / NODE_ID / "hda_disk.qcow2").read_bytes() == (
        source_project / "project-files" / "qemu" / NODE_ID / "hda_disk.qcow2"
    ).read_bytes()


def test_project_without_qemu_files_is_a_no_op(source_project, tmp_path):
    """
    A project without a project-files/qemu directory (no QEMU nodes) creates
    no overlay and does not even need qemu-img.
    """

    destination = tmp_path / "copy"
    destination.mkdir()
    shutil.rmtree(source_project / "project-files" / "qemu")
    assert qemu_overlay.create_overlay_disks(str(source_project), str(destination), _topology({})) == 0


def test_overlay_creation_failure_is_reported(source_project, tmp_path, monkeypatch):
    """
    A failing qemu-img create surfaces as a ControllerError, not a silent
    broken copy.
    """

    destination = tmp_path / "copy"
    destination.mkdir()
    monkeypatch.setattr(qemu_overlay, "find_qemu_img", lambda: "/fake/qemu-img")
    monkeypatch.setattr(qemu_overlay, "_image_info", lambda qemu_img, path: {"format": "qcow2", "virtual-size": 1024})
    monkeypatch.setattr(
        qemu_overlay, "_create_overlay", lambda *args: (_ for _ in ()).throw(ControllerError("qemu-img failed"))
    )
    with pytest.raises(ControllerError, match="qemu-img failed"):
        qemu_overlay.create_overlay_disks(
            str(source_project), str(destination), _topology({"hda_disk_image": "hda_disk.qcow2"})
        )
