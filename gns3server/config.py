#
# Copyright (C) 2021 GNS3 Technologies Inc.
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
Reads the configuration file and store the settings for the server.
"""

import sys
import os
import shutil
import secrets
import configparser

from pydantic import ValidationError
from .schemas import ServerConfig
from .version import __version_info__
from .utils.file_watcher import FileWatcher

import logging

log = logging.getLogger(__name__)


class Config:
    """
    Configuration file management using configparser.

    :param files: Array of configuration files (optional)
    :param profile: Profile settings (default use standard config file)
    """

    def __init__(self, files=None, profile=None):

        self._settings = None
        self._files = files
        self._profile = profile

        if files and len(files):
            if not os.access(files[0], os.R_OK) or not os.path.isfile(files[0]):
                raise SystemExit(f"Unable to read configuration file: {files[0]}")
            directory_name = os.path.dirname(files[0])
            if not directory_name or directory_name == "":
                files[0] = os.path.dirname(os.path.abspath(files[0])) + os.path.sep + files[0]
            self._main_config_file = files[0]
        else:
            self._main_config_file = None

        # Monitor configuration files for changes
        self._watched_files = {}
        self._watch_callback = []

        appname = "GNS3"
        version = f"{__version_info__[0]}.{__version_info__[1]}"

        # On UNIX-like platforms, the configuration file location can be one of the following:
        # 1: $HOME/.config/GNS3/gns3_server.conf
        # 2: $HOME/.config/GNS3.conf
        # 3: /etc/xdg/GNS3/gns3_server.conf
        # 4: /etc/xdg/GNS3.conf
        # 5: gns3_server.conf in the current working directory

        home = os.path.expanduser("~")
        server_filename = "gns3_server.conf"

        if self._profile:
            legacy_user_dir = os.path.join(home, ".config", appname, "profiles", self._profile)
            versioned_user_dir = os.path.join(home, ".config", appname, version, "profiles", self._profile)
        else:
            legacy_user_dir = os.path.join(home, ".config", appname)
            versioned_user_dir = os.path.join(home, ".config", appname, version)

        if self._files is None and not hasattr(sys, "_called_from_test"):
            self._files = [
                os.path.join(os.getcwd(), server_filename),
                os.path.join(versioned_user_dir, server_filename),
                os.path.join(home, ".config", appname + ".conf"),
                os.path.join("/etc/gns3", server_filename),
                os.path.join("/etc/xdg", appname, server_filename),
                os.path.join("/etc/xdg", appname + ".conf"),
            ]

        if self._files is None:
            self._files = []

        if self._main_config_file is None:

            # TODO: migrate versioned config file from a previous version of GNS3 (for instance 2.2 -> 3.0) + support profiles
            # migrate post version 2.2.0 config files if they exist
            os.makedirs(versioned_user_dir, exist_ok=True)
            try:
                # migrate the server config file
                old_server_config = os.path.join(legacy_user_dir, server_filename)
                new_server_config = os.path.join(versioned_user_dir, server_filename)
                if not os.path.exists(new_server_config) and os.path.exists(old_server_config):
                    shutil.copyfile(old_server_config, new_server_config)
            except OSError as e:
                log.error(f"Cannot migrate old config files: {e}")

            self._main_config_file = os.path.join(versioned_user_dir, server_filename)
            for file in self._files:
                if os.path.exists(file):
                    self._main_config_file = file
                    break

        self.clear()
        self._watch_config_file()

    @property
    def settings(self) -> ServerConfig:
        """
        Return the settings.
        """

        return self._settings

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
        """
        Return the directory where the configuration file is located.
        """

        return os.path.dirname(self._main_config_file)

    @property
    def controller_vars(self):
        """
        Return the controller variables file path.
        """

        controller_vars_filename = "gns3_controller.vars"
        return os.path.join(self.config_dir, controller_vars_filename)

    @property
    def server_config(self):
        """
        Return the server configuration file path.
        """

        server_config_filename = "gns3_server.conf"
        return os.path.join(self.config_dir, server_config_filename)

    def clear(self):
        """
        Restart with a clean config
        """

        self.read_config()

    def _watch_config_file(self):
        """
        Add config files to be monitored for changes.
        """

        for file in self._files:
            if os.path.exists(file):
                self._watched_files[file] = FileWatcher(file, self._config_file_change)

    def _config_file_change(self, file_path):
        """
        Callback when a config file has been updated.
        """

        log.info(f"'{file_path}' has been updated, reloading the config...")
        self.read_config()
        for callback in self._watch_callback:
            callback()

    def reload(self):
        """
        Reload configuration
        """

        self.read_config()

    def get_config_files(self):
        """
        Return the config files in use.
        """

        return self._watched_files

    def _load_jwt_secret_key(self):
        """
        Load the JWT secret key.
        """

        jwt_secret_key_path = os.path.join(self._settings.Server.secrets_dir, "gns3_jwt_secret_key")
        if not os.path.exists(jwt_secret_key_path):
            log.info(f"No JWT secret key configured, generating one in '{jwt_secret_key_path}'...")
            try:
                with open(jwt_secret_key_path, "w+", encoding="utf-8") as fd:
                    fd.write(secrets.token_hex(32))
            except OSError as e:
                log.error(f"Could not create JWT secret key file '{jwt_secret_key_path}': {e}")
        try:
            with open(jwt_secret_key_path, encoding="utf-8") as fd:
                jwt_secret_key_content = fd.read()
                self._settings.Controller.jwt_secret_key = jwt_secret_key_content
        except OSError as e:
            log.error(f"Could not read JWT secret key file '{jwt_secret_key_path}': {e}")

    def _load_secret_files(self):
        """
        Load the secret files.
        """

        if not self._settings.Server.secrets_dir:
            self._settings.Server.secrets_dir = os.path.dirname(self.server_config)

        self._load_jwt_secret_key()

    def read_config(self):
        """
        Read the configuration files and validate the settings.
        """

        config = configparser.ConfigParser(interpolation=None)
        try:
            parsed_files = config.read(self._files, encoding="utf-8")
        except configparser.Error as e:
            log.error("Can't parse configuration file: %s", str(e))
            return
        if not parsed_files:
            log.warning("No configuration file could be found or read")
            self._settings = ServerConfig()
            return

        for file in parsed_files:
            log.info(f"Configuration file '{file}' loaded")
            self._watched_files[file] = os.stat(file).st_mtime

        try:
            self._settings = ServerConfig(**config._sections)
        except ValidationError as e:
            log.critical(f"Could not validate configuration file settings: {e}")
            raise

        self._load_secret_files()

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
