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
import asyncio
import aiohttp
import zipfile
import tempfile
import zipstream

from datetime import datetime

import logging
log = logging.getLogger(__name__)


@asyncio.coroutine
def export_project(project, temporary_dir, include_images=False, keep_compute_id=False, allow_all_nodes=False, reset_mac_addresses=False):
    """
    Export a project to a zip file.

    The file will be read chunk by chunk when you iterate over the zip stream.
    Some files like snapshots and packet captures are ignored.

    :param temporary_dir: A temporary dir where to store intermediate data
    :param include images: save OS images to the zip file
    :param keep_compute_id: If false replace all compute id by local (standard behavior for .gns3project to make it portable)
    :param allow_all_nodes: Allow all nodes type to be include in the zip even if not portable
    :param reset_mac_addresses: Reset MAC addresses for every nodes.

    :returns: ZipStream object
    """

    # To avoid issue with data not saved we disallow the export of a running project
    if project.is_running():
        raise aiohttp.web.HTTPConflict(text="Project must be stopped in order to export it")

    # Make sure we save the project
    project.dump()

    zstream = zipstream.ZipFile(allowZip64=True)

    if not os.path.exists(project._path):
        raise aiohttp.web.HTTPNotFound(text="Project could not be found at '{}'".format(project._path))

    # First we process the .gns3 in order to be sure we don't have an error
    for file in os.listdir(project._path):
        if file.endswith(".gns3"):
            yield from _patch_project_file(project, os.path.join(project._path, file), zstream, include_images, keep_compute_id, allow_all_nodes, temporary_dir, reset_mac_addresses)

    # Export the local files
    for root, dirs, files in os.walk(project._path, topdown=True, followlinks=False):
        files = [f for f in files if _is_exportable(os.path.join(root, f))]
        for file in files:
            path = os.path.join(root, file)
            # check if we can export the file
            try:
                open(path).close()
            except OSError as e:
                msg = "Could not export file '{}': {}".format(path, e)
                log.warning(msg)
                project.controller.notification.emit("log.warning", {"message": msg})
                continue
            # ignore the .gns3 file
            if file.endswith(".gns3"):
                continue
            _patch_mtime(path)
            zstream.write(path, os.path.relpath(path, project._path), compress_type=zipfile.ZIP_DEFLATED)

    # Export files from remote computes
    downloaded_files = set()
    for compute in project.computes:
        if compute.id != "local":
            compute_files = yield from compute.list_files(project)
            for compute_file in compute_files:
                if _is_exportable(compute_file["path"]):
                    (fd, temp_path) = tempfile.mkstemp(dir=temporary_dir)
                    f = open(fd, "wb", closefd=True)
                    response = yield from compute.download_file(project, compute_file["path"])
                    while True:
                        try:
                            data = yield from response.content.read(1024)
                        except asyncio.TimeoutError:
                            raise aiohttp.web.HTTPRequestTimeout(text="Timeout when downloading file '{}' from remote compute server {}:{}".format(compute_file["path"], compute.host, compute.port))
                        if not data:
                            break
                        f.write(data)
                    response.close()
                    f.close()
                    _patch_mtime(temp_path)
                    zstream.write(temp_path, arcname=compute_file["path"], compress_type=zipfile.ZIP_DEFLATED)
                    downloaded_files.add(compute_file['path'])

    return zstream

@asyncio.coroutine
def export_project_zs(project, tmpid, temporary_dir, include_images=False, keep_compute_id=False, allow_all_nodes=False, reset_mac_addresses=False):
    """
    Export a project to a zstandard compressed tar file.

    Some files like snapshots and packet captures are ignored.

    :param temporary_dir: A temporary dir where to store intermediate data
    :param include images: save OS images to the zip file
    :param keep_compute_id: If false replace all compute id by local (standard behavior for .gns3project to make it portable)
    :param allow_all_nodes: Allow all nodes type to be include in the zip even if not portable
    :param reset_mac_addresses: Reset MAC addresses for every nodes.

    :returns: simple list of files to compress
    """

    # To avoid issue with data not saved we disallow the export of a running project
    if project.is_running():
        raise aiohttp.web.HTTPConflict(text="Project must be stopped in order to export it")

    # Make sure we save the project
    project.dump()

    filelist = {}

    if not os.path.exists(project._path):
        raise aiohttp.web.HTTPNotFound(text="Project could not be found at '{}'".format(project._path))

    # First we process the .gns3 in order to be sure we don't have an error
    for file in os.listdir(project._path):
        if file.endswith(".gns3"):
            yield from _patch_project_file_zs(project, tmpid, os.path.join(project._path, file), filelist, include_images, keep_compute_id, allow_all_nodes, temporary_dir, reset_mac_addresses)

    # Export the local files
    for root, dirs, files in os.walk(project._path, topdown=True, followlinks=False):
        files = [f for f in files if _is_exportable(os.path.join(root, f))]
        for file in files:
            path = os.path.join(root, file)
            # check if we can export the file
            try:
                open(path).close()
            except OSError as e:
                msg = "Could not export file '{}': {}".format(path, e)
                log.warning(msg)
                project.controller.notification.emit("log.warning", {"message": msg})
                continue
            # ignore the .gns3 file
            if file.endswith(".gns3"):
                continue
            _patch_mtime(path)
            #zstream.write(path, os.path.relpath(path, project._path), compress_type=zipfile.ZIP_DEFLATED)
            filelist[path]=os.path.relpath(path, project._path)

    # Export files from remote computes
    downloaded_files = set()
    for compute in project.computes:
        if compute.id != "local":
            compute_files = yield from compute.list_files(project)
            for compute_file in compute_files:
                if _is_exportable(compute_file["path"]):
                    (fd, temp_path) = tempfile.mkstemp(dir=temporary_dir)
                    f = open(fd, "wb", closefd=True)
                    response = yield from compute.download_file(project, compute_file["path"])
                    while True:
                        try:
                            data = yield from response.content.read(1024)
                        except asyncio.TimeoutError:
                            raise aiohttp.web.HTTPRequestTimeout(text="Timeout when downloading file '{}' from remote compute server {}:{}".format(compute_file["path"], compute.host, compute.port))
                        if not data:
                            break
                        f.write(data)
                    response.close()
                    f.close()
                    _patch_mtime(temp_path)
                    #zstream.write(temp_path, arcname=compute_file["path"], compress_type=zipfile.ZIP_DEFLATED)
                    filelist[temp_path]=compute_file["path"]
                    downloaded_files.add(compute_file['path'])

    return filelist

def _patch_mtime(path):
    """
    Patch the file mtime because ZIP does not support timestamps before 1980

    :param path: file path
    """

    if sys.platform.startswith("win"):
        # only UNIX type platforms
        return
    st = os.stat(path)
    file_date = datetime.fromtimestamp(st.st_mtime)
    if file_date.year < 1980:
        new_mtime = file_date.replace(year=1980).timestamp()
        os.utime(path, (st.st_atime, new_mtime))


def _is_exportable(path):
    """
    :returns: True if file should not be included in the final archive
    """

    # do not export snapshots
    if path.endswith("snapshots"):
        return False

    # do not export symlinks
    if os.path.islink(path):
        return False

    # do not export directories of snapshots
    if "{sep}snapshots{sep}".format(sep=os.path.sep) in path:
        return False

    try:
        # do not export captures and other temporary directory
        s = os.path.normpath(path).split(os.path.sep)
        i = s.index("project-files")
        if s[i + 1] in ("tmp", "captures", "snapshots"):
            return False
    except (ValueError, IndexError):
        pass

    # do not export log files and OS noise
    filename = os.path.basename(path)
    if filename.endswith('_log.txt') or filename.endswith('.log') or filename == '.DS_Store':
        return False
    return True


@asyncio.coroutine
def _patch_project_file(project, path, zstream, include_images, keep_compute_id, allow_all_nodes, temporary_dir, reset_mac_addresses):
    """
    Patch a project file (.gns3) to export a project.
    The .gns3 file is renamed to project.gns3

    :param path: path of the .gns3 file
    """

    # image files that we need to include in the exported archive
    images = []

    try:
        with open(path) as f:
            topology = json.load(f)
    except (OSError, ValueError) as e:
        raise aiohttp.web.HTTPConflict(text="Project file '{}' cannot be read: {}".format(path, e))

    if "topology" in topology:
        if "nodes" in topology["topology"]:
            for node in topology["topology"]["nodes"]:
                compute_id = node.get('compute_id', 'local')

                if node["node_type"] == "virtualbox" and node.get("properties", {}).get("linked_clone"):
                    raise aiohttp.web.HTTPConflict(text="Projects with a linked {} clone node cannot not be exported. Please use Qemu instead.".format(node["node_type"]))
                if not allow_all_nodes and node["node_type"] in ["virtualbox", "vmware", "cloud"]:
                    raise aiohttp.web.HTTPConflict(text="Projects with a {} node cannot be exported".format(node["node_type"]))

                if not keep_compute_id:
                    node["compute_id"] = "local"  # To make project portable all node by default run on local

                if "properties" in node and node["node_type"] != "docker":
                    for prop, value in node["properties"].items():

                        # reset the MAC address
                        if reset_mac_addresses and prop in ("mac_addr", "mac_address"):
                            node["properties"][prop] = None

                        if node["node_type"] == "iou":
                            if not prop == "path":
                                continue
                        elif not prop.endswith("image"):
                            continue
                        if value is None or value.strip() == '':
                            continue

                        if not keep_compute_id:  # If we keep the original compute we can keep the image path
                            node["properties"][prop] = os.path.basename(value)

                        if include_images is True:
                            images.append({
                                'compute_id': compute_id,
                                'image': value,
                                'image_type': node['node_type']
                            })

        if not keep_compute_id:
            topology["topology"]["computes"] = []  # Strip compute information because could contain secret info like password

    local_images = set([i['image'] for i in images if i['compute_id'] == 'local'])

    for image in local_images:
        _export_local_image(image, zstream)

    remote_images = set([
        (i['compute_id'], i['image_type'], i['image'])
        for i in images if i['compute_id'] != 'local'])

    for compute_id, image_type, image in remote_images:
        yield from _export_remote_images(project, compute_id, image_type, image, zstream, temporary_dir)

    zstream.writestr("project.gns3", json.dumps(topology).encode())
    return images

@asyncio.coroutine
def _patch_project_file_zs(project, tmpid, path, filelist, include_images, keep_compute_id, allow_all_nodes, temporary_dir, reset_mac_addresses):
    """
    Patch a project file (.gns3) to export a project.
    The .gns3 file is renamed to project.gns3

    :param path: path of the .gns3 file
    """

    # image files that we need to include in the exported archive
    images = []

    try:
        with open(path) as f:
            topology = json.load(f)
    except (OSError, ValueError) as e:
        raise aiohttp.web.HTTPConflict(text="Project file '{}' cannot be read: {}".format(path, e))

    if "topology" in topology:
        if "nodes" in topology["topology"]:
            for node in topology["topology"]["nodes"]:
                compute_id = node.get('compute_id', 'local')

                if node["node_type"] == "virtualbox" and node.get("properties", {}).get("linked_clone"):
                    raise aiohttp.web.HTTPConflict(text="Projects with a linked {} clone node cannot not be exported. Please use Qemu instead.".format(node["node_type"]))
                if not allow_all_nodes and node["node_type"] in ["virtualbox", "vmware", "cloud"]:
                    raise aiohttp.web.HTTPConflict(text="Projects with a {} node cannot be exported".format(node["node_type"]))

                if not keep_compute_id:
                    node["compute_id"] = "local"  # To make project portable all node by default run on local

                if "properties" in node and node["node_type"] != "docker":
                    for prop, value in node["properties"].items():

                        # reset the MAC address
                        if reset_mac_addresses and prop in ("mac_addr", "mac_address"):
                            node["properties"][prop] = None

                        if node["node_type"] == "iou":
                            if not prop == "path":
                                continue
                        elif not prop.endswith("image"):
                            continue
                        if value is None or value.strip() == '':
                            continue

                        if not keep_compute_id:  # If we keep the original compute we can keep the image path
                            node["properties"][prop] = os.path.basename(value)

                        if include_images is True:
                            images.append({
                                'compute_id': compute_id,
                                'image': value,
                                'image_type': node['node_type']
                            })

        if not keep_compute_id:
            topology["topology"]["computes"] = []  # Strip compute information because could contain secret info like password

    local_images = set([i['image'] for i in images if i['compute_id'] == 'local'])

    for image in local_images:
        _export_local_image_zs(image, filelist)

    remote_images = set([
        (i['compute_id'], i['image_type'], i['image'])
        for i in images if i['compute_id'] != 'local'])

    for compute_id, image_type, image in remote_images:
        yield from _export_remote_images_zs(project, compute_id, image_type, image, zstream, temporary_dir)

    #zstream.writestr("project.gns3", json.dumps(topology).encode())
    tmppath = "/tmp/project_" + tmpid + ".gns3"
    with open(tmppath,'wb') as projectfile:
        projectfile.write(json.dumps(topology).encode())
    filelist[tmppath]="project.gns3"
    return images

def _export_local_image(image, zstream):
    """
    Exports a local image to the zip file.

    :param image: image path
    :param zstream: Zipfile instance for the export
    """

    from ..compute import MODULES
    for module in MODULES:
        try:
            images_directory = module.instance().get_images_directory()
        except NotImplementedError:
            # Some modules don't have images
            continue

        directory = os.path.split(images_directory)[-1:][0]
        if os.path.exists(image):
            path = image
        else:
            path = os.path.join(images_directory, image)

        if os.path.exists(path):
            arcname = os.path.join("images", directory, os.path.basename(image))
            _patch_mtime(path)
            zstream.write(path, arcname)
            return

def _export_local_image_zs(image, filelist):
    """
    Exports a local image to the zstandard file

    :param image: image path
    :param filelist: path list to add to tar later
    """

    from ..compute import MODULES
    for module in MODULES:
        try:
            images_directory = module.instance().get_images_directory()
        except NotImplementedError:
            # Some modules don't have images
            continue

        directory = os.path.split(images_directory)[-1:][0]
        if os.path.exists(image):
            path = image
        else:
            path = os.path.join(images_directory, image)

        if os.path.exists(path):
            arcname = os.path.join("images", directory, os.path.basename(image))
            _patch_mtime(path)
            filelist[path]=arcname
            return

@asyncio.coroutine
def _export_remote_images(project, compute_id, image_type, image, project_zipfile, temporary_dir):
    """
    Export specific image from remote compute.
    """

    log.info("Downloading image '{}' from compute server '{}'".format(image, compute_id))

    try:
        compute = [compute for compute in project.computes if compute.id == compute_id][0]
    except IndexError:
        raise aiohttp.web.HTTPConflict(text="Cannot export image from '{}' compute. Compute doesn't exist.".format(compute_id))

    (fd, temp_path) = tempfile.mkstemp(dir=temporary_dir)
    f = open(fd, "wb", closefd=True)
    response = yield from compute.download_image(image_type, image)

    if response.status != 200:
        raise aiohttp.web.HTTPConflict(text="Cannot export image from '{}' compute. Compute returned status code {}.".format(compute_id, response.status))

    while True:
        try:
            data = yield from response.content.read(1024)
        except asyncio.TimeoutError:
            raise aiohttp.web.HTTPRequestTimeout(text="Timeout when downloading image '{}' from remote compute server {}:{}".format(image, compute.host, compute.port))
        if not data:
            break
        f.write(data)
    response.close()
    f.close()
    arcname = os.path.join("images", image_type, image)
    log.info("Saved {}".format(arcname))
    project_zipfile.write(temp_path, arcname=arcname, compress_type=zipfile.ZIP_DEFLATED)

@asyncio.coroutine
def _export_remote_images_zs(project, compute_id, image_type, image, project_filelist, temporary_dir):
    """
    Export specific image from remote compute.
    """

    log.info("Downloading image '{}' from compute server '{}'".format(image, compute_id))

    try:
        compute = [compute for compute in project.computes if compute.id == compute_id][0]
    except IndexError:
        raise aiohttp.web.HTTPConflict(text="Cannot export image from '{}' compute. Compute doesn't exist.".format(compute_id))

    (fd, temp_path) = tempfile.mkstemp(dir=temporary_dir)
    f = open(fd, "wb", closefd=True)
    response = yield from compute.download_image(image_type, image)

    if response.status != 200:
        raise aiohttp.web.HTTPConflict(text="Cannot export image from '{}' compute. Compute returned status code {}.".format(compute_id, response.status))

    while True:
        try:
            data = yield from response.content.read(1024)
        except asyncio.TimeoutError:
            raise aiohttp.web.HTTPRequestTimeout(text="Timeout when downloading image '{}' from remote compute server {}:{}".format(image, compute.host, compute.port))
        if not data:
            break
        f.write(data)
    response.close()
    f.close()
    arcname = os.path.join("images", image_type, image)
    log.info("Saved {}".format(arcname))
    project_filelist[temp_path]=arcname
