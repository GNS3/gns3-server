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
import aiohttp

from ..config import Config


def get_default_project_directory():
    """
    Return the default location for the project directory
    depending of the operating system
    """

    server_config = Config.instance().get_section_config("Server")
    path = os.path.expanduser(server_config.get("projects_path", "~/GNS3/projects"))
    path = os.path.normpath(path)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        raise aiohttp.web.HTTPInternalServerError(text="Could not create project directory: {}".format(e))
    return path


def check_path_allowed(path):
    """
    If the server is non local raise an error if
    the path is outside project directories

    Raise a 403 in case of error
    """

    config = Config.instance().get_section_config("Server")

    project_directory = get_default_project_directory()
    if len(os.path.commonprefix([project_directory, path])) == len(project_directory):
        return

    if "local" in config and config.getboolean("local") is False:
        raise aiohttp.web.HTTPForbidden(text="The path is not allowed")
