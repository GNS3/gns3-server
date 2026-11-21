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

import itertools
import json
import logging
import os
import shutil
import stat
import tempfile
import uuid

import aiofiles

import gns3server.utils.zipfile_zstd as zipfile_zstd

from ..utils.asyncio import aiozipstream, wait_run_in_executor
from .controller_error import ControllerError
from .quota_usage import QUOTA_COUNTED_TYPES, reserve_import
from .topology import load_topology

log = logging.getLogger(__name__)

"""
Handle the import of project from a .gns3project
"""


async def import_project(
    controller,
    project_id,
    stream,
    location=None,
    name=None,
    reset_mac_addresses=False,
    keep_compute_ids=False,
    auto_start=False,
    auto_open=False,
    auto_close=True,
    user=None,
    user_id=None,
):
    """
    Import a project contain in a zip file

    You must handle OSError exceptions

    :param controller: GNS3 Controller
    :param project_id: ID of the project to import
    :param stream: A io.BytesIO of the zipfile
    :param location: Directory for the project if None put in the default directory
    :param name: Wanted project name, generate one from the .gns3 if None
    :param reset_mac_addresses: Reset MAC addresses for each node
    :param keep_compute_ids: keep compute IDs unchanged
    :param project_name: Original project name when restoring a snapshot
    :param user: User importing the project
    :param user_id: Stable id of the user importing the project

    :returns: Project
    """

    if location and ".gns3" in location:
        raise ControllerError("The destination path should not contain .gns3")

    try:
        with zipfile_zstd.ZipFile(stream) as zip_file:
            project_file = zip_file.read("project.gns3").decode()
    except zipfile_zstd.BadZipFile:
        raise ControllerError("Cannot import project, not a GNS3 project (invalid zip)")
    except KeyError:
        raise ControllerError("Cannot import project, project.gns3 file could not be found")

    try:
        topology = json.loads(project_file)
        # We import the project on top of an existing project (snapshots).
        # The client chooses the project id in the URL, so the archive alone
        # must not decide: an archive that reuses the URL id must not pass
        # for a snapshot restore (it would skip the quota check and the id
        # regeneration below). Only a project the controller already knows
        # can be replaced.
        replaced_project = controller.projects.get(str(project_id))
        if replaced_project is not None and str(topology.get("project_id")) == str(project_id):
            # The project keeps its current name: the object reads <name>.gns3
            # on open, so writing the archive's (older) name would leave the
            # import invisible and a second .gns3 file with the same id behind.
            project_name = replaced_project.name
            restoring_snapshot = True
        else:
            # If the project name is already used we generate a new one
            if name:
                project_name = controller.get_free_project_name(name)
            else:
                project_name = controller.get_free_project_name(topology["name"])
            restoring_snapshot = False
    except (ValueError, KeyError):
        raise ControllerError("Cannot import project, the project.gns3 file is corrupted")

    # A new import with a known future owner counts its nodes against the
    # owner's quota (a snapshot restore keeps the nodes it replaces).
    # The reservation covers the whole import: until the project is
    # registered the nodes only exist as in-flight quota slots.
    if user and not restoring_snapshot:
        node_count = sum(
            1 for node in topology.get("topology", {}).get("nodes", []) if node.get("node_type") in QUOTA_COUNTED_TYPES
        )
        reservation = reserve_import(user, node_count)
    else:
        reservation = None

    try:
        if location:
            path = location
        else:
            projects_path = controller.projects_directory()
            path = os.path.join(projects_path, project_id)
        try:
            os.makedirs(path, exist_ok=True)
        except UnicodeEncodeError:
            raise ControllerError("The project name contain non supported or invalid characters")

        try:
            with zipfile_zstd.ZipFile(stream) as zip_file:
                await wait_run_in_executor(zip_file.extractall, path)
                _create_symbolic_links(zip_file, path)
        except zipfile_zstd.BadZipFile:
            raise ControllerError("Cannot extract files from GNS3 project (invalid zip)")

        topology = load_topology(os.path.join(path, "project.gns3"))
        topology["name"] = project_name
        # To avoid unexpected behavior (project start without manual operations just after import)
        topology["auto_start"] = auto_start
        topology["auto_open"] = auto_open
        topology["auto_close"] = auto_close

        # frozen, distribution_master_id and the owner id are server-side
        # state: an archive must not forge them. A fake distribution_master_id
        # would pass the imported project for a live copy of someone else's
        # template and lock that template forever, and a fake owner id would
        # point the owner ACE at someone else. When the import replaces a
        # project the controller already knows (a snapshot restore), the
        # state held by the server is kept.
        topology.pop("frozen", None)
        topology.pop("distribution_master_id", None)
        # an owner id claimed by the archive is never trusted: it is either
        # the importing user or the owner of the replaced project
        topology.pop("created_by_id", None)
        topology.pop("created_by_deleted", None)

        if user:
            topology["created_by"] = user
            if user_id:
                topology["created_by_id"] = user_id

        if replaced_project is not None:
            if replaced_project.frozen:
                topology["frozen"] = True
            if replaced_project.distribution_master_id:
                topology["distribution_master_id"] = str(replaced_project.distribution_master_id)
            if not user:
                # a snapshot restore keeps the owner the controller knows
                topology["created_by"] = replaced_project.created_by
                if replaced_project.created_by_id:
                    topology["created_by_id"] = replaced_project.created_by_id
                if replaced_project.created_by_deleted:
                    topology["created_by_deleted"] = True

        if not restoring_snapshot:
            # Do not re-generate IDs if we are restoring a snapshot because they should be the same in a project
            regenerate_topology_ids(topology, path, reset_mac_addresses=reset_mac_addresses)

        # Modify the compute id of the node depending on compute capacity
        if not keep_compute_ids:
            # Round-robin through available compute resources.
            # Only use computes that are connected to avoid import failures
            available_computes = {
                compute_id: compute for compute_id, compute in controller.computes.items() if compute.connected
            }
            if available_computes:
                compute_nodes = itertools.cycle(available_computes)
                for node in topology["topology"]["nodes"]:
                    node["compute_id"] = next(compute_nodes)
            else:
                # No remote computes are connected, use local only
                for node in topology["topology"]["nodes"]:
                    node["compute_id"] = "local"

        compute_created = set()
        for node in topology["topology"]["nodes"]:
            if node["compute_id"] != "local":
                # Project created on the remote GNS3 VM?
                if node["compute_id"] not in compute_created:
                    compute = controller.get_compute(node["compute_id"])
                    await compute.post(
                        "/projects",
                        data={
                            "name": project_name,
                            "project_id": project_id,
                        },
                    )
                    compute_created.add(node["compute_id"])
                await _move_files_to_compute(
                    compute, project_id, path, os.path.join("project-files", node["node_type"], node["node_id"])
                )

        # And we dump the updated.gns3
        dot_gns3_path = os.path.join(path, project_name + ".gns3")
        # We change the project_id to avoid erasing the project
        topology["project_id"] = project_id
        with open(dot_gns3_path, "w+") as f:
            json.dump(topology, f, indent=4, sort_keys=True)
        os.remove(os.path.join(path, "project.gns3"))
        if replaced_project is not None:
            # remove a topology file left under a different name (e.g. a
            # rename that could not update the file on disk): after a restart
            # the controller would load it again as the same project id
            previous_topology_file = replaced_project.topology_file
            if os.path.abspath(previous_topology_file) != os.path.abspath(dot_gns3_path) and os.path.exists(
                previous_topology_file
            ):
                os.remove(previous_topology_file)

        images_path = os.path.join(path, "images")
        if os.path.exists(images_path):
            await _import_images(controller, images_path)

        snapshots_path = os.path.join(path, "snapshots")
        if not restoring_snapshot and os.path.exists(snapshots_path):
            await update_snapshots(
                snapshots_path, path, project_name, project_id, reset_mac_addresses=reset_mac_addresses
            )

        project = await controller.load_project(dot_gns3_path, load=False)
        return project
    finally:
        if reservation is not None:
            reservation.release()


def _create_symbolic_links(zip_file, path):
    """
    Manually create symbolic links (if any) because ZipFile does not support it.
    Refuse any target that escapes `path`.

    :param zip_file: ZipFile instance
    :param path: project location
    """

    path_root = os.path.realpath(path) + os.sep
    for zip_info in zip_file.infolist():
        if not stat.S_ISLNK(zip_info.external_attr >> 16):
            continue
        symlink_target = zip_file.read(zip_info.filename).decode()
        symlink_path = os.path.join(path, zip_info.filename)

        # 1. Reject absolute targets outright.
        if os.path.isabs(symlink_target):
            raise ControllerError(f"Symlink {zip_info.filename!r} has absolute target {symlink_target!r}, refusing")

        # 2. Reject paths where the entry name itself escapes (defence in depth;
        #    extractall normally would already have caught this).
        member_abs = os.path.realpath(symlink_path)
        if not (member_abs + os.sep).startswith(path_root) and member_abs + os.sep != path_root:
            raise ControllerError(f"Symlink entry {zip_info.filename!r} escapes project dir, refusing")

        # 3. Resolve the symlink target relative to the entry's own parent
        #    directory and verify the resolved real path stays inside `path`.
        link_dir = os.path.realpath(os.path.dirname(symlink_path))
        resolved_target = os.path.realpath(os.path.join(link_dir, symlink_target))
        if not (resolved_target + os.sep).startswith(path_root) and resolved_target + os.sep != path_root:
            raise ControllerError("Symlink {zip_info.filename!r} -> {symlink_target!r} escapes project dir, refusing")

        try:
            os.remove(symlink_path)
            os.symlink(symlink_target, symlink_path)
        except OSError as e:
            raise ControllerError(f"Cannot create symbolic link: {e}")


def regenerate_topology_ids(topology, new_project_path, reset_mac_addresses=False):
    """
    Regenerate IDs in the topology and move the files of the nodes to match the new IDs.
    This is necessary because IDs must be unique across projects.

    :param topology: topology content
    :param new_project_path: new project path
    :param reset_mac_addresses: reset MAC addresses
    """

    # Generate new node IDs
    node_old_to_new = {}
    for node in topology["topology"]["nodes"]:
        new_node_id = str(uuid.uuid4())
        if "node_id" in node:
            node_old_to_new[node["node_id"]] = new_node_id
            _move_node_file(new_project_path, node["node_id"], new_node_id)
        node["node_id"] = new_node_id
        if reset_mac_addresses:
            if "properties" in node:
                for prop, value in node["properties"].items():
                    # reset the MAC address
                    if prop in ("mac_addr", "mac_address"):
                        node["properties"][prop] = None

    # Generate new link IDs
    for link in topology["topology"]["links"]:
        link["link_id"] = str(uuid.uuid4())
        for node in link["nodes"]:
            node["node_id"] = node_old_to_new[node["node_id"]]

    # Generate new drawings IDs
    for drawing in topology["topology"]["drawings"]:
        drawing["drawing_id"] = str(uuid.uuid4())


def _move_node_file(path, old_id, new_id):
    """
    Move a file from a node when changing its id

    :param path: Path of the project
    :param old_id: ID before change
    :param new_id: New node UUID
    """

    root = os.path.join(path, "project-files")
    if os.path.exists(root):
        for dirname in os.listdir(root):
            module_dir = os.path.join(root, dirname)
            if os.path.isdir(module_dir):
                node_dir = os.path.join(module_dir, old_id)
                if os.path.exists(node_dir):
                    shutil.move(node_dir, os.path.join(module_dir, new_id))


async def _move_files_to_compute(compute, project_id, directory, files_path):
    """
    Move files to a remote compute
    """

    location = os.path.join(directory, files_path)
    if os.path.exists(location):
        for dirpath, dirnames, filenames in os.walk(location, followlinks=False):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                if os.path.islink(path):
                    continue
                dst = os.path.relpath(path, directory)
                await _upload_file(compute, project_id, path, dst)
        await wait_run_in_executor(shutil.rmtree, os.path.join(directory, files_path))


async def _upload_file(compute, project_id, file_path, path):
    """
    Upload a file to a remote project

    :param file_path: File path on the controller file system
    :param path: File path on the remote system relative to project directory
    """

    path = "/projects/{}/files/{}".format(project_id, path.replace("\\", "/"))
    with open(file_path, "rb") as f:
        await compute.http_query("POST", path, f, timeout=None)


async def _import_images(controller, images_path):
    """
    Copy images to the images directory or delete them if they already exist.
    """

    image_dir = controller.images_path()
    root = images_path
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            dst = os.path.join(image_dir, os.path.relpath(path, root))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not os.path.exists(dst):
                await wait_run_in_executor(shutil.move, path, dst)
                try:
                    with open(dst, "rb") as f:
                        # read the first 7 bytes of the file.
                        elf_header_start = f.read(7)
                        # IOU images must start with the ELF magic number, be 32-bit or 64-bit, little endian and have an ELF version of 1
                        if elf_header_start == b"\x7fELF\x01\x01\x01" or elf_header_start == b"\x7fELF\x02\x01\x01":
                            os.chmod(dst, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
                except OSError as e:
                    continue


async def update_snapshots(snapshots_dir, project_path, project_name, project_id, reset_mac_addresses=True):
    """
    Load the snapshots and update their project name and project ID to be the same as the main project.
    Regenerate all the node, link and drawing IDs
    """

    for snapshot in os.listdir(snapshots_dir):
        if not (snapshot.endswith(".gns3snapshot") or snapshot.endswith(".gns3project")):
            continue
        snapshot_path = os.path.join(snapshots_dir, snapshot)
        with tempfile.TemporaryDirectory(dir=snapshots_dir) as tmpdir:
            # extract everything to a temporary directory
            try:
                with open(snapshot_path, "rb") as f:
                    with zipfile_zstd.ZipFile(f) as zip_file:
                        await wait_run_in_executor(zip_file.extractall, tmpdir)
                        _create_symbolic_links(zip_file, tmpdir)
            except OSError as e:
                raise ControllerError(f"Cannot open snapshot '{os.path.basename(snapshot)}': {e}")
            except zipfile_zstd.BadZipFile:
                raise ControllerError(
                    f"Cannot extract files from snapshot '{os.path.basename(snapshot)}': not a GNS3 project (invalid zip)"
                )

            # patch the topology with the correct project name and ID
            try:
                topology_file_path = os.path.join(tmpdir, "project.gns3")
                with open(topology_file_path, encoding="utf-8") as f:
                    topology = json.load(f)
                    topology["name"] = project_name
                    topology["project_id"] = project_id
                    regenerate_topology_ids(topology, tmpdir, reset_mac_addresses)
                with open(topology_file_path, "w+", encoding="utf-8") as f:
                    json.dump(topology, f, indent=4, sort_keys=True)
            except OSError as e:
                raise ControllerError(
                    f"Cannot update snapshot '{os.path.basename(snapshot)}': the project.gns3 file cannot be modified: {e}"
                )
            except (ValueError, KeyError):
                raise ControllerError(
                    f"Cannot update snapshot '{os.path.basename(snapshot)}': the project.gns3 file is corrupted"
                )

            # write everything back to the original snapshot file
            try:
                with aiozipstream.ZipFile(compression=zipfile_zstd.ZIP_STORED) as zstream:
                    for root, dirs, files in os.walk(tmpdir, topdown=True, followlinks=False):
                        for file in files:
                            path = os.path.join(root, file)
                            zstream.write(path, os.path.relpath(path, tmpdir))
                    async with aiofiles.open(snapshot_path, "wb+") as f:
                        async for chunk in zstream:
                            await f.write(chunk)
                log.info(f"Project '{project_name}': updated and repacked snapshot file '{snapshot}'")
            except OSError as e:
                raise ControllerError(
                    f"Cannot update snapshot '{os.path.basename(snapshot)}': the snapshot cannot be recreated: {e}"
                )
