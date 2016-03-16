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

"""
Reads the configuration file and store the settings for the server & modules.
"""

import sys
import os
import configparser
import asyncio

import logging
log = logging.getLogger(__name__)

CLOUD_SERVER = 'CLOUD_SERVER'


class Config(object):

    """
    Configuration file management using configparser.

    :params files: Array of configuration files (optional)
    :params config_directory: Path of the configuration directory. If None default OS directory
    """

    def __init__(self, files=None, config_directory=None):

        self._files = files

        # Monitor configuration files for changes
        self._watched_files = {}

        if hasattr(sys, "_called_from_test"):
            self._files = files
        elif sys.platform.startswith("win"):

            appname = "GNS3"

            # On windows, the configuration file location can be one of the following:
            # 1: %APPDATA%/GNS3/gns3_server.ini
            # 2: %APPDATA%/GNS3.ini
            # 3: %COMMON_APPDATA%/GNS3/gns3_server.ini
            # 4: %COMMON_APPDATA%/GNS3.ini
            # 5: server.ini in the current working directory

            appdata = os.path.expandvars("%APPDATA%")
            common_appdata = os.path.expandvars("%COMMON_APPDATA%")
            filename = "gns3_server.ini"
            if self._files is None:
                self._files = [os.path.join(os.getcwd(), filename),
                               os.path.join(appdata, appname, filename),
                               os.path.join(appdata, appname + ".ini"),
                               os.path.join(common_appdata, appname, filename),
                               os.path.join(common_appdata, appname + ".ini")]
        else:

            # On UNIX-like platforms, the configuration file location can be one of the following:
            # 1: $HOME/.config/GNS3/gns3_server.conf
            # 2: $HOME/.config/GNS3.conf
            # 3: /etc/xdg/GNS3/gns3_server.conf
            # 4: /etc/xdg/GNS3.conf
            # 5: gns3_server.conf in the current working directory

            appname = "GNS3"
            home = os.path.expanduser("~")
            filename = "gns3_server.conf"
            if self._files is None:
                self._files = [os.path.join(os.getcwd(), filename),
                               os.path.join(home, ".config", appname, filename),
                               os.path.join(home, ".config", appname + ".conf"),
                               os.path.join("/etc/gns3", filename),
                               os.path.join("/etc/xdg", appname, filename),
                               os.path.join("/etc/xdg", appname + ".conf")]

        if self._files is None:
            self._files = []
        self.clear()
        self._watch_config_file()

    def clear(self):
        """Restart with a clean config"""
        self._config = configparser.RawConfigParser()
        # Override config from command line even if we modify the config file and live reload it.
        self._override_config = {}

        self.read_config()

    def _watch_config_file(self):
        asyncio.get_event_loop().call_later(1, self._check_config_file_change)

    def _check_config_file_change(self):
        """
        Check if configuration file has changed on the disk
        """
        changed = False
        for file in self._watched_files:
            try:
                if os.stat(file).st_mtime != self._watched_files[file]:
                    changed = True
            except OSError:
                continue
        if changed:
            self.read_config()
            for section in self._override_config:
                self.set_section_config(section, self._override_config[section])
        self._watch_config_file()

    def reload(self):
        """
        Reload configuration
        """

        self.read_config()
        for section in self._override_config:
            self.set_section_config(section, self._override_config[section])

    def get_config_files(self):
        return self._watched_files

    def read_config(self):
        """
        Read the configuration files.
        """

        try:
            parsed_files = self._config.read(self._files, encoding="utf-8")
        except configparser.Error as e:
            log.error("Can't parse configuration file: %s", str(e))
            return
        if not parsed_files:
            log.warning("No configuration file could be found or read")
        else:
            for file in parsed_files:
                log.info("Load configuration file {}".format(file))
                self._watched_files[file] = os.stat(file).st_mtime

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

        if section not in self._config:
            return self._config["DEFAULT"]
        return self._config[section]

    def set_section_config(self, section, content):
        """
        Set a specific configuration section. It's not
        dumped on the disk.

        :param section: Section name
        :param content: A dictionary with section content
        """

        if not self._config.has_section(section):
            self._config.add_section(section)
        for key in content:
            if isinstance(content[key], bool):
                content[key] = str(content[key]).lower()
            self._config.set(section, key, content[key])
        self._override_config[section] = content

    def set(self, section, key, value):
        """
        Set a config value.
        It's not dumped on the disk.

        If the section doesn't exists the section is created
        """

        conf = self.get_section_config(section)
        if isinstance(value, bool):
            conf[key] = str(value)
        else:
            conf[key] = value
        self.set_section_config(section, conf)

    @staticmethod
    def instance(files=None):
        """
        Singleton to return only one instance of Config.

        :params files: Array of configuration files (optional)
        :returns: instance of Config
        """

        if not hasattr(Config, "_instance") or Config._instance is None:
            Config._instance = Config(files)
        return Config._instance

    @staticmethod
    def reset():
        """
        Reset singleton
        """

        Config._instance = None
