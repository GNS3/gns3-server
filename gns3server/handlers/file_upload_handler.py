# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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

"""
Simple file upload & listing handler.
"""


import os
import stat
import tornado.web
from .auth_handler import GNS3BaseHandler
from ..version import __version__
from ..config import Config

import logging
log = logging.getLogger(__name__)


class FileUploadHandler(GNS3BaseHandler):
    """
    File upload handler.

    :param application: Tornado Application instance
    :param request: Tornado Request instance
    """

    def __init__(self, application, request, **kwargs):

        super().__init__(application, request, **kwargs)
        config = Config.instance()
        server_config = config.get_default_section()
        self._upload_dir = os.path.expandvars(
            os.path.expanduser(server_config.get("upload_directory", "~/GNS3/images")))
        self._host = request.host
        try:
            os.makedirs(self._upload_dir)
            log.info("upload directory '{}' created".format(self._upload_dir))
        except FileExistsError:
            pass
        except OSError as e:
            log.error("could not create the upload directory {}: {}".format(self._upload_dir, e))

    @tornado.web.authenticated
    def get(self):
        """
        Invoked on GET request.
        """

        items = []
        path = self._upload_dir
        for filename in os.listdir(path):
            items.append(filename)

        self.render("upload.html",
                    version=__version__,
                    host=self._host,
                    path=path,
                    items=items)

    @tornado.web.authenticated
    def post(self):
        """
        Invoked on POST request.
        """

        if "file" in self.request.files:
            fileinfo = self.request.files["file"][0]
            destination_path = os.path.join(self._upload_dir, fileinfo['filename'])
            try:
                with open(destination_path, 'wb') as f:
                    f.write(fileinfo['body'])
            except OSError as e:
                self.write("Could not upload {}: {}".format(fileinfo['filename'], e))
                return
            st = os.stat(destination_path)
            os.chmod(destination_path, st.st_mode | stat.S_IXUSR)
        self.redirect("/upload")
