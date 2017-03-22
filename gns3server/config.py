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
Reads the configuration file and store the settings for the controller & compute.
"""

import sys
import os
import configparser
import asyncio

from .utils.file_watcher import FileWatcher

import logging
log = logging.getLogger(__name__)


class Config:

    """
    Configuration file management using configparser.

    :param files: Array of configuration files (optional)
    :param profile: Profile settings (default use standard settings file)
    """

    def __init__(self, files=None, profile=None):

        self._files = files
        self._profile = profile
        if files and len(files):
            self._main_config_file = files[0]
        else:
            self._main_config_file = None

        # Monitor configuration files for changes
        self._watched_files = {}
        self._watch_callback = []

        if sys.platform.startswith("win"):

            appname = "GNS3"

            # On windows, the configuration file location can be one of the following:
            # 1: %APPDATA%/GNS3/gns3_server.ini
            # 2: %APPDATA%/GNS3.ini
            # 3: %COMMON_APPDATA%/GNS3/gns3_server.ini
            # 4: %COMMON_APPDATA%/GNS3.ini
            # 5: server.ini in the current working directory

            appdata = os.path.expandvars("%APPDATA%")
            common_appdata = os.path.expandvars("%COMMON_APPDATA%")

            if self._profile:
                user_dir = os.path.join(appdata, appname, "profiles", self._profile)
            else:
                user_dir = os.path.join(appdata, appname)

            filename = "gns3_server.ini"
            if self._files is None and not hasattr(sys, "_called_from_test"):
                self._files = [os.path.join(os.getcwd(), filename),
                               os.path.join(user_dir, filename),
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

            if self._profile:
                user_dir = os.path.join(home, ".config", appname, "profiles", self._profile)
            else:
                user_dir = os.path.join(home, ".config", appname)

            if self._files is None and not hasattr(sys, "_called_from_test"):
                self._files = [os.path.join(os.getcwd(), filename),
                               os.path.join(user_dir, filename),
                               os.path.join(home, ".config", appname + ".conf"),
                               os.path.join("/etc/gns3", filename),
                               os.path.join("/etc/xdg", appname, filename),
                               os.path.join("/etc/xdg", appname + ".conf")]

        if self._files is None:
            self._files = []

        if self._main_config_file is None:
            self._main_config_file = os.path.join(user_dir, filename)
            for file in self._files:
                if os.path.exists(file):
                    self._main_config_file = file
                    break

        self.clear()
        self._watch_config_file()

    def listen_for_config_changes(self, callback):
        """
        Call the callback when the configuration file change
        """
        self._watch_callback.append(callback)

    @property
    def profile(self):
        """
        Settings profile
        """
        return self._profile

    @property
    def config_dir(self):
        return os.path.dirname(self._main_config_file)

    def clear(self):
        """Restart with a clean config"""
        self._config = configparser.RawConfigParser()
        # Override config from command line even if we modify the config file and live reload it.
        self._override_config = {}

        self.read_config()

    def _watch_config_file(self):
        for file in self._files:
            self._watched_files[file] = FileWatcher(file, self._config_file_change)

    def _config_file_change(self, path):
        self.read_config()
        for section in self._override_config:
            self.set_section_config(section, self._override_config[section])
        for callback in self._watch_callback:
            callback()

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
    def instance(*args, **kwargs):
        """
        Singleton to return only one instance of Config.

        :returns: instance of Config
        """

        if not hasattr(Config, "_instance") or Config._instance is None:
            Config._instance = Config(*args, **kwargs)
        return Config._instance

    @staticmethod
    def reset():
        """
        Reset singleton
        """

        Config._instance = None
