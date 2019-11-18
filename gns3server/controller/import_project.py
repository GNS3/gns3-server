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
import sys
import json
import uuid
import shutil
import asyncio
import zipfile
import zstandard as zstd
import tarfile
import aiohttp
import itertools

from .topology import load_topology
from ..utils.asyncio import wait_run_in_executor

"""
Handle the import of project from a .gns3project
"""


@asyncio.coroutine
def import_project(controller, selfpath, project_id, stream, location=None, name=None, keep_compute_id=False):
    """
    Import a project contain in a zip file OR a zstandard archive

    You need to handle OSError exceptions

    :param controller: GNS3 Controller
    :param selfpath: archive file path
    :param project_id: ID of the project to import
    :param stream: A io.BytesIO of the zipfile
    :param location: Directory for the project if None put in the default directory
    :param name: Wanted project name, generate one from the .gns3 if None
    :param keep_compute_id: If true do not touch the compute id

    :returns: Project
    """

    if location and ".gns3" in location:
        raise aiohttp.web.HTTPConflict(text="The destination path should not contain .gns3")

    if selfpath.endswith(".gns3project"):
        try:
            with zipfile.ZipFile(stream) as zip_file:
                project_file = zip_file.read("project.gns3").decode()
        except zipfile.BadZipFile:
            raise aiohttp.web.HTTPConflict(text="Cannot import project, not a GNS3 project (invalid zip)")
        except KeyError:
            raise aiohttp.web.HTTPConflict(text="Cannot import project, project.gns3 file could not be found")
        try:
            topology = json.loads(project_file)
            # We import the project on top of an existing project (snapshots)
            if topology["project_id"] == project_id:
                project_name = topology["name"]
            else:
                # If the project name is already used we generate a new one
                if name:
                    project_name = controller.get_free_project_name(name)
                else:
                    project_name = controller.get_free_project_name(topology["name"])
        except (ValueError, KeyError):
            raise aiohttp.web.HTTPConflict(text="Cannot import project, the project.gns3 file is corrupted")

    if location:
        path = location
    else:
        projects_path = controller.projects_directory()
        path = os.path.join(projects_path, project_id)
    try:
        os.makedirs(path, exist_ok=True)
    except UnicodeEncodeError:
        raise aiohttp.web.HTTPConflict(text="The project name contain non supported or invalid characters")

    if selfpath.endswith(".genens3"):
        try:
            dctx = zstd.ZstdDecompressor(max_window_size=2147483648)
            with open(selfpath, "rb") as f:
                with dctx.stream_reader(f) as reader:
                #stream into tarfile
                    with tarfile.open(name=None, mode='r|', fileobj=reader) as tfile:
                        yield from wait_run_in_executor(tfile.extractall, path=path)
        except tfile.ReadError:
            raise aiohttp.web.HTTPConflict(text="Cannot import project, not a GNS3 project (invalid tar)")
        try:
            with open(os.path.join(path,"project.gns3")) as project_file:
                topology = json.loads(project_file.read())
                # We import the project on top of an existing project (snapshots)
                if topology["project_id"] == project_id:
                    project_name = topology["name"]
                else:
                    # If the project name is already used we generate a new one
                    if name:
                        project_name = controller.get_free_project_name(name)
                    else:
                        project_name = controller.get_free_project_name(topology["name"])
        except (ValueError, KeyError):
            raise aiohttp.web.HTTPConflict(text="Cannot import project, the project.gns3 file is corrupted")
    elif selfpath.endswith(".gns3project"):
        try:
            with zipfile.ZipFile(stream) as zip_file:
                yield from wait_run_in_executor(zip_file.extractall, path)
        except zipfile.BadZipFile:
            raise aiohttp.web.HTTPConflict(text="Cannot extract files from GNS3 project (invalid zip)")

    topology = load_topology(os.path.join(path, "project.gns3"))
    topology["name"] = project_name
    # To avoid unexpected behavior (project start without manual operations just after import)
    topology["auto_start"] = False
    topology["auto_open"] = False
    topology["auto_close"] = True

    # Generate a new node id
    node_old_to_new = {}
    for node in topology["topology"]["nodes"]:
        if "node_id" in node:
            node_old_to_new[node["node_id"]] = str(uuid.uuid4())
            _move_node_file(path, node["node_id"], node_old_to_new[node["node_id"]])
            node["node_id"] = node_old_to_new[node["node_id"]]
        else:
            node["node_id"] = str(uuid.uuid4())

    # Update link to use new id
    for link in topology["topology"]["links"]:
        link["link_id"] = str(uuid.uuid4())
        for node in link["nodes"]:
            node["node_id"] = node_old_to_new[node["node_id"]]

    # Generate new drawings id
    for drawing in topology["topology"]["drawings"]:
        drawing["drawing_id"] = str(uuid.uuid4())

    # Modify the compute id of the node depending of compute capacity
    if not keep_compute_id:
        # For some VM type we move them to the GNS3 VM if possible
        # unless it's a linux host without GNS3 VM
        if not sys.platform.startswith("linux") or controller.has_compute("vm"):
            for node in topology["topology"]["nodes"]:
                if node["node_type"] in ("docker", "qemu", "iou", "nat"):
                    node["compute_id"] = "vm"
        else:
            # Round-robin through available compute resources.
            compute_nodes = itertools.cycle(controller.computes)
            for node in topology["topology"]["nodes"]:
                node["compute_id"] = next(compute_nodes)

    compute_created = set()
    for node in topology["topology"]["nodes"]:
        if node["compute_id"] != "local":
            # Project created on the remote GNS3 VM?
            if node["compute_id"] not in compute_created:
                compute = controller.get_compute(node["compute_id"])
                yield from compute.post("/projects", data={"name": project_name, "project_id": project_id,})
                compute_created.add(node["compute_id"])
            yield from _move_files_to_compute(compute, project_id, path, os.path.join("project-files", node["node_type"], node["node_id"]))

    # And we dump the updated.gns3
    dot_gns3_path = os.path.join(path, project_name + ".gns3")
    # We change the project_id to avoid erasing the project
    topology["project_id"] = project_id
    with open(dot_gns3_path, "w+") as f:
        json.dump(topology, f, indent=4)
    os.remove(os.path.join(path, "project.gns3"))

    if os.path.exists(os.path.join(path, "images")):
        _import_images(controller, path)

    project = yield from controller.load_project(dot_gns3_path, load=False)
    return project


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


@asyncio.coroutine
def _move_files_to_compute(compute, project_id, directory, files_path):
    """
    Move files to a remote compute
    """

    location = os.path.join(directory, files_path)
    if os.path.exists(location):
        for (dirpath, dirnames, filenames) in os.walk(location, followlinks=False):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                if os.path.islink(path):
                    continue
                dst = os.path.relpath(path, directory)
                yield from _upload_file(compute, project_id, path, dst)
        yield from wait_run_in_executor(shutil.rmtree, os.path.join(directory, files_path))


@asyncio.coroutine
def _upload_file(compute, project_id, file_path, path):
    """
    Upload a file to a remote project

    :param file_path: File path on the controller file system
    :param path: File path on the remote system relative to project directory
    """

    path = "/projects/{}/files/{}".format(project_id, path.replace("\\", "/"))
    with open(file_path, "rb") as f:
        yield from compute.http_query("POST", path, f, timeout=None)


def _import_images(controller, path):
    """
    Copy images to the images directory or delete them if they already exists.
    """

    image_dir = controller.images_path()
    root = os.path.join(path, "images")
    for (dirpath, dirnames, filenames) in os.walk(root, followlinks=False):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            if os.path.islink(path):
                continue
            dst = os.path.join(image_dir, os.path.relpath(path, root))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(path, dst)
