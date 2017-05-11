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
import asyncio
import aiohttp
import zipfile
import tempfile
import zipstream


import logging
log = logging.getLogger(__name__)


@asyncio.coroutine
def export_project(project, temporary_dir, include_images=False, keep_compute_id=False, allow_all_nodes=False):
    """
    Export the project as zip. It's a ZipStream object.
    The file will be read chunk by chunk when you iterate on
    the zip.

    It will ignore some files like snapshots and

    :param temporary_dir: A temporary dir where to store intermediate data
    :param keep_compute_id: If false replace all compute id by local it's the standard behavior for .gns3project to make them portable
    :param allow_all_nodes: Allow all nodes type to be include in the zip even if not portable default False
    :returns: ZipStream object
    """

    # To avoid issue with data not saved we disallow the export of a running topologie
    if project.is_running():
        raise aiohttp.web.HTTPConflict(text="Running topology could not be exported")

    # Make sure we save the project
    project.dump()

    z = zipstream.ZipFile(allowZip64=True)

    if not os.path.exists(project._path):
        raise aiohttp.web.HTTPNotFound(text="The project doesn't exist at location {}".format(project._path))

    # First we process the .gns3 in order to be sure we don't have an error
    for file in os.listdir(project._path):
        if file.endswith(".gns3"):
            _export_project_file(project, os.path.join(project._path, file), z, include_images, keep_compute_id, allow_all_nodes)

    for root, dirs, files in os.walk(project._path, topdown=True):
        files = [f for f in files if not _filter_files(os.path.join(root, f))]

        for file in files:
            path = os.path.join(root, file)
            # Try open the file
            try:
                open(path).close()
            except OSError as e:
                msg = "Could not export file {}: {}".format(path, e)
                log.warn(msg)
                project.controller.notification.emit("log.warning", {"message": msg})
                continue
            if file.endswith(".gns3"):
                pass
            else:
                z.write(path, os.path.relpath(path, project._path), compress_type=zipfile.ZIP_DEFLATED)

    for compute in project.computes:
        if compute.id != "local":
            compute_files = yield from compute.list_files(project)
            for compute_file in compute_files:
                if not _filter_files(compute_file["path"]):
                    (fd, temp_path) = tempfile.mkstemp(dir=temporary_dir)
                    f = open(fd, "wb", closefd=True)
                    response = yield from compute.download_file(project, compute_file["path"])
                    while True:
                        data = yield from response.content.read(512)
                        if not data:
                            break
                        f.write(data)
                    response.close()
                    f.close()
                    z.write(temp_path, arcname=compute_file["path"], compress_type=zipfile.ZIP_DEFLATED)
    return z


def _filter_files(path):
    """
    :returns: True if file should not be included in the final archive
    """
    s = os.path.normpath(path).split(os.path.sep)

    if path.endswith("snapshots"):
        return True

    try:
        i = s.index("project-files")
        if s[i + 1] in ("tmp", "captures", "snapshots"):
            return True
    except (ValueError, IndexError):
        pass

    file_name = os.path.basename(path)
    # Ignore log files and OS noises
    if file_name.endswith('_log.txt') or file_name.endswith('.log') or file_name == '.DS_Store':
        return True

    return False


def _export_project_file(project, path, z, include_images, keep_compute_id, allow_all_nodes):
    """
    Take a project file (.gns3) and patch it for the export

    We rename the .gns3 project.gns3 to avoid the task to the client to guess the file name

    :param path: Path of the .gns3
    """

    # Image file that we need to include in the exported archive
    images = set()

    with open(path) as f:
        topology = json.load(f)

    if "topology" in topology:
        if "nodes" in topology["topology"]:
            for node in topology["topology"]["nodes"]:
                if node["node_type"] == "virtualbox" and node.get("properties", {}).get("linked_clone"):
                    raise aiohttp.web.HTTPConflict(text="Topology with a linked {} clone could not be exported. Use qemu instead.".format(node["node_type"]))
                if not allow_all_nodes and node["node_type"] in ["virtualbox", "vmware", "cloud"]:
                    raise aiohttp.web.HTTPConflict(text="Topology with a {} could not be exported".format(node["node_type"]))

                if not keep_compute_id:
                    node["compute_id"] = "local"  # To make project portable all node by default run on local

                if "properties" in node and node["node_type"] != "docker":
                    for prop, value in node["properties"].items():
                        if prop.endswith("image"):
                            if not keep_compute_id:  # If we keep the original compute we can keep the image path
                                node["properties"][prop] = os.path.basename(value)
                            if include_images is True:
                                images.add(value)

        if not keep_compute_id:
            topology["topology"]["computes"] = []  # Strip compute informations because could contain secret info like password

    for image in images:
        _export_images(project, image, z)

    z.writestr("project.gns3", json.dumps(topology).encode())


def _export_images(project, image, z):
    """
    Take a project file (.gns3) and export images to the zip

    :param image: Image path
    :param z: Zipfile instance for the export
    """
    from ..compute import MODULES

    for module in MODULES:
        try:
            img_directory = module.instance().get_images_directory()
        except NotImplementedError:
            # Some modules don't have images
            continue

        directory = os.path.split(img_directory)[-1:][0]

        if os.path.exists(image):
            path = image
        else:
            path = os.path.join(img_directory, image)

        if os.path.exists(path):
            arcname = os.path.join("images", directory, os.path.basename(image))
            z.write(path, arcname)
            return
    raise aiohttp.web.HTTPConflict(text="Topology could not be exported because the image {} is not available. If you use multiple server, we need a copy of the image on the main server.".format(image))
