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
import aiohttp

from .topology import load_topology


"""
Handle the import of project from a .gns3project
"""


@asyncio.coroutine
def import_project(controller, project_id, stream, location=None, name=None, keep_compute_id=False):
    """
    Import a project contain in a zip file

    You need to handle OSerror exceptions

    :param controller: GNS3 Controller
    :param project_id: ID of the project to import
    :param stream: A io.BytesIO of the zipfile
    :param location: Directory for the project if None put in the default directory
    :param name: Wanted project name, generate one from the .gns3 if None
    :param keep_compute_id: If true do not touch the compute id
    :returns: Project
    """

    if location and ".gns3" in location:
        raise aiohttp.web.HTTPConflict(text="The destination path should not contain .gns3")

    try:
        with zipfile.ZipFile(stream) as myzip:

            try:
                topology = json.loads(myzip.read("project.gns3").decode())

                # We import the project on top of an existing project (snapshots)
                if topology["project_id"] == project_id:
                    project_name = topology["name"]
                else:
                    # If the project name is already used we generate a new one
                    if name:
                        project_name = controller.get_free_project_name(name)
                    else:
                        project_name = controller.get_free_project_name(topology["name"])
            except KeyError:
                raise aiohttp.web.HTTPConflict(text="Can't import topology the .gns3 is corrupted or missing")

            if location:
                path = location
            else:
                projects_path = controller.projects_directory()
                path = os.path.join(projects_path, project_id)
            try:
                os.makedirs(path, exist_ok=True)
            except UnicodeEncodeError as e:
                raise aiohttp.web.HTTPConflict(text="The project name contain non supported or invalid characters")
            myzip.extractall(path)

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
                    for node in topology["topology"]["nodes"]:
                        node["compute_id"] = "local"

            compute_created = set()
            for node in topology["topology"]["nodes"]:

                if node["compute_id"] != "local":
                    # Project created on the remote GNS3 VM?
                    if node["compute_id"] not in compute_created:
                        compute = controller.get_compute(node["compute_id"])
                        yield from compute.post("/projects", data={
                            "name": project_name,
                            "project_id": project_id,
                        })
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
    except zipfile.BadZipFile:
        raise aiohttp.web.HTTPConflict(text="Can't import topology the file is corrupted or not a GNS3 project (invalid zip)")


def _move_node_file(path, old_id, new_id):
    """
    Move the files from a node when changing his id

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
    Move the files to a remote compute
    """
    location = os.path.join(directory, files_path)
    if os.path.exists(location):
        for (dirpath, dirnames, filenames) in os.walk(location):
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                dst = os.path.relpath(path, directory)
                yield from _upload_file(compute, project_id, path, dst)
        shutil.rmtree(os.path.join(directory, files_path))


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
    Copy images to the images directory or delete them if they
    already exists.
    """
    image_dir = controller.images_path()

    root = os.path.join(path, "images")
    for (dirpath, dirnames, filenames) in os.walk(root):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            dst = os.path.join(image_dir, os.path.relpath(path, root))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(path, dst)
