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

from ..config import Config
from .topology import load_topology


"""
Handle the import of project from a .gns3project
"""


@asyncio.coroutine
def import_project(controller, project_id, stream):
    """
    Import a project contain in a zip file

    You need to handle OSerror exceptions

    :param stream: A io.BytesIO of the zipfile
    :param gns3vm: True move Docker, IOU and Qemu to the GNS3 VM
    :returns: Project
    """
    projects_path = controller.projects_directory()
    os.makedirs(projects_path, exist_ok=True)

    with zipfile.ZipFile(stream) as myzip:

        try:
            topology = json.loads(myzip.read("project.gns3").decode())
            # If the project name is already used we generate a new one
            project_name = controller.get_free_project_name(topology["name"])
        except KeyError:
            raise aiohttp.web.HTTPConflict(text="Can't import topology the .gns3 is corrupted or missing")

        path = os.path.join(projects_path, project_name)
        os.makedirs(path)
        myzip.extractall(path)

        topology = load_topology(os.path.join(path, "project.gns3"))
        topology["name"] = project_name

        # For some VM type we move them to the GNS3 VM if it's not a Linux host
        if not sys.platform.startswith("linux"):
            vm_created = False

            for node in topology["topology"]["nodes"]:
                if node["node_type"] in ("docker", "qemu", "iou"):
                    node["compute_id"] = "vm"

                    # Project created on the remote GNS3 VM?
                    if not vm_created:
                        compute = controller.get_compute("vm")
                        yield from compute.post("/projects", data={
                            "name": project_name,
                            "project_id": project_id,
                        })
                        vm_created = True

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


@asyncio.coroutine
def _move_files_to_compute(compute, project_id, directory, files_path):
    """
    Move the files to a remote compute
    """
    for (dirpath, dirnames, filenames) in os.walk(os.path.join(directory, files_path)):
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
