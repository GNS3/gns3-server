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
Reads the configuration file and store the settings for the server & modules.
"""

import sys
import os
import configparser

import logging
log = logging.getLogger(__name__)


class Config(object):
    """
    Configuration file management using configparser.
    """

    def __init__(self):

        appname = "GNS3"
        if sys.platform.startswith("win"):

            # On windows, the configuration file location can be one of the following:
            # 1: %APPDATA%/GNS3/server.ini
            # 2: %APPDATA%/GNS3.ini
            # 3: %COMMON_APPDATA%/GNS3/server.ini
            # 4: %COMMON_APPDATA%/GNS3.ini
            # 5: server.ini in the current working directory

            appdata = os.path.expandvars("%APPDATA%")
            common_appdata = os.path.expandvars("%COMMON_APPDATA%")
            filename = "server.ini"
            self._files = [os.path.join(appdata, appname, filename),
                           os.path.join(appdata, appname + ".ini"),
                           os.path.join(common_appdata, appname, filename),
                           os.path.join(common_appdata, appname + ".ini"),
                           filename]
        else:

            # On UNIX-like platforms, the configuration file location can be one of the following:
            # 1: $HOME/.config/GNS3/server.conf
            # 2: $HOME/.config/GNS3.conf
            # 3: /etc/xdg/GNS3/server.conf
            # 4: /etc/xdg/GNS3.conf
            # 5: server.conf in the current working directory

            home = os.path.expanduser("~")
            self._cloud_config = os.path.join(home, ".config", appname, "cloud.conf")
            filename = "server.conf"
            self._files = [os.path.join(home, ".config", appname, filename),
                           os.path.join(home, ".config", appname + ".conf"),
                           os.path.join("/etc/xdg", appname, filename),
                           os.path.join("/etc/xdg", appname + ".conf"),
                           filename,
                           self._cloud_config]

        self._config = configparser.ConfigParser()
        self.read_config()

    def list_cloud_config_file(self):
        return self._cloud_config

    def read_config(self):
        """
        Read the configuration files.
        """

        parsed_files = self._config.read(self._files)
        if not parsed_files:
            log.warning("no configuration file could be found or read")

    def get_default_section(self):
        """
        Get the default configuration section.

        :returns: configparser section
        """

        return self._config["DEFAULT"]

    def get_section_config(self, section):
        """
        Get a specific configuration section.
        Returns the default section if none can be found.

        :returns: configparser section
        """

        if not section in self._config:
            return self._config["DEFAULT"]
        return self._config[section]

    @staticmethod
    def instance():
        """
        Singleton to return only on instance of Config.

        :returns: instance of Config
        """

        if not hasattr(Config, "_instance"):
            Config._instance = Config()
        return Config._instance
