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
Thin overlay disks for project distribution.

A distributed copy does not copy the QEMU disks of the template project:
every disk becomes a fresh qcow2 overlay whose backing file is the
template's disk. The copy starts at the template state and only stores
what its recipient writes, so distributing to a whole class is seconds of
metadata work instead of one full copy per recipient.

The overlay indirection is safe because the template is frozen for
modification as soon as it is distributed (see Project.check_mutable):
nothing ever writes through the backing chain above the recipient's own
overlay.
"""

import json
import logging
import os
import shutil
import subprocess
from typing import Optional

from .controller_error import ControllerError

log = logging.getLogger(__name__)

# node working directories of QEMU nodes, relative to the project directory
QEMU_FILES_DIRECTORY = os.path.join("project-files", "qemu")


def find_qemu_img() -> str:
    """
    Locate the qemu-img binary on the controller host.
    """

    qemu_img = shutil.which("qemu-img")
    if qemu_img is None:
        raise ControllerError("Could not find qemu-img on the controller host: it is required to distribute projects")
    return qemu_img


def _image_info(qemu_img: str, path: str):
    """
    Probe a file with qemu-img: return its image information (a dict with at
    least "format" and "virtual-size") when it is a disk image, None when it
    is not (a config file, a log...).
    """

    try:
        result = subprocess.run(
            [qemu_img, "info", "--output=json", path],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, TimeoutError) as e:
        raise ControllerError(f"Could not probe '{path}' with qemu-img: {e}")
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def _create_overlay(qemu_img: str, backing_file: str, overlay_file: str, info: dict) -> None:
    """
    Create a qcow2 overlay at ``overlay_file`` with ``backing_file`` as its
    backing. The virtual size of the original image is preserved: a disk
    grown past its base (qemu-img resize) must not shrink back.
    """

    command = [qemu_img, "create", "-f", "qcow2", "-b", backing_file, "-F", info.get("format", "qcow2"), overlay_file]
    virtual_size = info.get("virtual-size")
    if virtual_size is not None:
        command.append(str(virtual_size))
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, TimeoutError) as e:
        raise ControllerError(f"Could not create the overlay disk '{overlay_file}': {e}")
    if result.returncode != 0:
        raise ControllerError(f"Could not create the overlay disk '{overlay_file}': {result.stderr.strip()}")


def _qemu_node_disks(topology: dict) -> dict:
    """
    Map each QEMU node id of the topology to the set of file names that are
    disk images in its node directory.

    The topology is the authority on what a disk is, never the file content:
    qemu-img reports any regular file as a raw image, so a log or a checksum
    cache cannot be told apart from a raw disk by probing (the compute side
    boots what the properties name, see QemuVM._build_command).
    """

    disks: dict = {}
    for node in topology.get("topology", {}).get("nodes", []):
        if node.get("node_type") != "qemu":
            continue
        properties = node.get("properties") or {}
        names = set()
        for drive in ("a", "b", "c", "d"):
            image = properties.get(f"hd{drive}_disk_image")
            if not image:
                continue
            # the disk living in the node directory when the property names a
            # file there, plus the conventional overlay (hdX_disk.qcow2) the
            # compute creates at startup when the property points at an image
            # directory
            names.add(os.path.basename(image))
            names.add(f"hd{drive}_disk.qcow2")
        if properties.get("create_config_disk"):
            # the config disk the compute builds in the node directory
            names.add("config.img")
        node_id = node.get("node_id")
        if node_id is not None:
            disks[node_id] = names
    return disks


def create_overlay_disks(
    source_project_dir: str,
    destination_project_dir: str,
    topology: dict,
    qemu_img: Optional[str] = None,
) -> int:
    """
    Cover the QEMU node directories of a freshly copied project with thin
    overlays: every file the topology names as a disk becomes an overlay in
    the destination, every other file of these directories (config files,
    logs) is copied verbatim. Returns the number of overlays created.
    """

    source_qemu_dir = os.path.join(source_project_dir, QEMU_FILES_DIRECTORY)
    if not os.path.isdir(source_qemu_dir):
        return 0
    # resolved lazily: a pass without any named disk must not need qemu-img
    node_disks = _qemu_node_disks(topology)

    overlays = 0
    for node_id in os.listdir(source_qemu_dir):
        source_node_dir = os.path.join(source_qemu_dir, node_id)
        if not os.path.isdir(source_node_dir):
            continue
        disk_names = node_disks.get(node_id, set())
        destination_node_dir = os.path.join(destination_project_dir, QEMU_FILES_DIRECTORY, node_id)
        os.makedirs(destination_node_dir, exist_ok=True)
        for root, dirs, files in os.walk(source_node_dir):
            relative = os.path.relpath(root, source_node_dir)
            target_root = destination_node_dir if relative == "." else os.path.join(destination_node_dir, relative)
            os.makedirs(target_root, exist_ok=True)
            for name in files:
                source_file = os.path.join(root, name)
                destination_file = os.path.join(target_root, name)
                if name not in disk_names:
                    shutil.copy2(source_file, destination_file)
                    continue
                if qemu_img is None:
                    qemu_img = find_qemu_img()
                info = _image_info(qemu_img, source_file)
                if info is None:
                    # a file the topology names as a disk but that qemu-img
                    # cannot read: copy it verbatim rather than lose it
                    shutil.copy2(source_file, destination_file)
                else:
                    _create_overlay(qemu_img, os.path.abspath(source_file), destination_file, info)
                    overlays += 1
    log.info(
        f"Created {overlays} overlay disk(s) pointing at '{os.path.abspath(source_project_dir)}' "
        f"for the distributed copy in '{destination_project_dir}'"
    )
    return overlays
