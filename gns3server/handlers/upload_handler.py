# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
import aiohttp
import stat
import io
import tarfile
import asyncio

from ..config import Config
from ..web.route import Route
from ..utils.images import remove_checksum, md5sum


class UploadHandler:

    @classmethod
    @Route.get(
        r"/upload",
        description="Manage upload of GNS3 images",
        api_version=None
    )
    def index(request, response):
        uploaded_files = []
        try:
            for root, _, files in os.walk(UploadHandler.image_directory()):
                for filename in files:
                    if not filename.startswith(".") and not filename.endswith(".md5sum"):
                        image_file = os.path.join(root, filename)
                        uploaded_files.append(image_file)
        except OSError:
            pass
        iourc_path = os.path.join(os.path.expanduser("~/"), ".iourc")
        if os.path.exists(iourc_path):
            uploaded_files.append(iourc_path)
        response.template("upload.html", files=uploaded_files)

    @classmethod
    @Route.post(
        r"/upload",
        description="Manage upload of GNS3 images",
        api_version=None
    )
    def upload(request, response):
        data = yield from request.post()

        if not data["file"]:
            response.redirect("/upload")
            return

        if data["type"] not in ["IOU", "IOURC", "QEMU", "IOS", "IMAGES", "PROJECTS"]:
            raise aiohttp.web.HTTPForbidden(text="You are not authorized to upload this kind of image {}".format(data["type"]))

        try:
            if data["type"] == "IMAGES":
                UploadHandler._restore_directory(data["file"], UploadHandler.image_directory())
            elif data["type"] == "PROJECTS":
                UploadHandler._restore_directory(data["file"], UploadHandler.project_directory())
            else:
                if data["type"] == "IOURC":
                    destination_dir = os.path.expanduser("~/")
                    destination_path = os.path.join(destination_dir, ".iourc")
                else:
                    destination_dir = os.path.join(UploadHandler.image_directory(), data["type"])
                    destination_path = os.path.join(destination_dir, data["file"].filename)
                os.makedirs(destination_dir, exist_ok=True)
                remove_checksum(destination_path)
                with open(destination_path, "wb+") as f:
                    while True:
                        chunk = data["file"].file.read(512)
                        if not chunk:
                            break
                        f.write(chunk)
                md5sum(destination_path)
                st = os.stat(destination_path)
                os.chmod(destination_path, st.st_mode | stat.S_IXUSR)
        except OSError as e:
            response.html("Could not upload file: {}".format(e))
            response.set_status(200)
            return
        response.redirect("/upload")

    @classmethod
    @Route.get(
        r"/backup/images.tar",
        description="Backup GNS3 images",
        api_version=None
    )
    def backup_images(request, response):
        yield from UploadHandler._backup_directory(request, response, UploadHandler.image_directory())

    @classmethod
    @Route.get(
        r"/backup/projects.tar",
        description="Backup GNS3 projects",
        api_version=None
    )
    def backup_projects(request, response):
        yield from UploadHandler._backup_directory(request, response, UploadHandler.project_directory())

    @staticmethod
    def _restore_directory(file, directory):
        """
        Extract from HTTP stream the content of a tar
        """
        destination_path = os.path.join(directory, "archive.tar")
        os.makedirs(directory, exist_ok=True)
        with open(destination_path, "wb+") as f:
            chunk = file.file.read()
            f.write(chunk)
        t = tarfile.open(destination_path)
        t.extractall(directory)
        t.close()
        os.remove(destination_path)

    @staticmethod
    @asyncio.coroutine
    def _backup_directory(request, response, directory):
        """
        Return a tar archive from a directory
        """
        response.content_type = 'application/x-gtar'
        response.set_status(200)
        response.enable_chunked_encoding()
        # Very important: do not send a content length otherwise QT close the connection but curl can consume the Feed
        response.content_length = None
        response.start(request)

        buffer = io.BytesIO()
        with tarfile.open('arch.tar', 'w', fileobj=buffer) as tar:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    path = os.path.join(root, file)
                    tar.add(os.path.join(root, file), arcname=os.path.relpath(path, directory))
                    response.write(buffer.getvalue())
                    yield from response.drain()
                    buffer.truncate(0)
                    buffer.seek(0)
        yield from response.write_eof()

    @staticmethod
    def image_directory():
        server_config = Config.instance().get_section_config("Server")
        return os.path.expanduser(server_config.get("images_path", "~/GNS3/images"))

    @staticmethod
    def project_directory():
        server_config = Config.instance().get_section_config("Server")
        return os.path.expanduser(server_config.get("projects_path", "~/GNS3/projects"))
