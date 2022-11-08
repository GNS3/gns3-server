#!/usr/bin/env python
#
# Copyright (C) 2019 GNS3 Technologies Inc.
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

import sys
import os
import json
import uuid
import asyncio
import aiohttp
import importlib_resources
import shutil

from .appliance import Appliance
from ..config import Config
from ..utils.asyncio import locking

import logging
log = logging.getLogger(__name__)


class ApplianceManager:
    """
    Manages appliances
    """

    def __init__(self):

        self._appliances = {}
        self._appliances_etag = None

    @property
    def appliances_etag(self):
        """
        :returns: ETag for downloaded appliances
        """

        return self._appliances_etag

    @appliances_etag.setter
    def appliances_etag(self, etag):
        """
        :param etag: ETag for downloaded appliances
        """

        self._appliances_etag = etag

    @property
    def appliances(self):
        """
        :returns: The dictionary of appliances managed by GNS3
        """

        return self._appliances

    def _custom_appliances_path(self):
        """
        Get the custom appliance storage directory
        """

        server_config = Config.instance().get_section_config("Server")
        appliances_path = os.path.expanduser(server_config.get("appliances_path", "~/GNS3/appliances"))
        os.makedirs(appliances_path, exist_ok=True)
        return appliances_path

    def _builtin_appliances_path(self):
        """
        Get the built-in appliance storage directory
        """

        config = Config.instance()
        appliances_dir = os.path.join(config.config_dir, "appliances")
        os.makedirs(appliances_dir, exist_ok=True)
        return appliances_dir

    def install_builtin_appliances(self):
        """
        At startup we copy the built-in appliances files.
        """

        dst_path = self._builtin_appliances_path()
        try:
            if hasattr(sys, "frozen") and sys.platform.startswith("win"):
                resource_path = os.path.normpath(os.path.join(os.path.dirname(sys.executable), "appliances"))
                for filename in os.listdir(resource_path):
                    if not os.path.exists(os.path.join(dst_path, filename)):
                        shutil.copy(os.path.join(resource_path, filename), os.path.join(dst_path, filename))
            else:
                for entry in importlib_resources.files('gns3server.appliances').iterdir():
                    full_path = os.path.join(dst_path, entry.name)
                    if entry.is_file() and not os.path.exists(full_path):
                        log.debug(f"Installing built-in appliance file {entry.name} to {full_path}")
                        shutil.copy(str(entry), os.path.join(dst_path, entry.name))
        except OSError as e:
            log.error(f"Could not install built-in appliance files to {dst_path}: {e}")

    def load_appliances(self, symbol_theme="Classic"):
        """
        Loads appliance files from disk.
        """

        self._appliances = {}
        for directory, builtin in ((self._builtin_appliances_path(), True,), (self._custom_appliances_path(), False,)):
            if directory and os.path.isdir(directory):
                for file in os.listdir(directory):
                    if not file.endswith('.gns3a') and not file.endswith('.gns3appliance'):
                        continue
                    path = os.path.join(directory, file)
                    appliance_id = uuid.uuid3(uuid.NAMESPACE_URL, path)  # Generate UUID from path to avoid change between reboots
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            appliance = Appliance(appliance_id, json.load(f), builtin=builtin)
                            json_data = appliance.__json__()  # Check if loaded without error
                            if appliance.status != 'broken':
                                self._appliances[appliance.id] = appliance
                            if not appliance.symbol or appliance.symbol.startswith(":/symbols/"):
                                # apply a default symbol if the appliance has none or a default symbol
                                default_symbol = self._get_default_symbol(json_data, symbol_theme)
                                if default_symbol:
                                    appliance.symbol = default_symbol
                    except (ValueError, OSError, KeyError) as e:
                        log.warning("Cannot load appliance file '%s': %s", path, str(e))
                        continue

    def _get_default_symbol(self, appliance, symbol_theme):
        """
        Returns the default symbol for a given appliance.
        """

        from . import Controller
        controller = Controller.instance()
        category = appliance["category"]
        if category == "guest":
            if "docker" in appliance:
                return controller.symbols.get_default_symbol("docker_guest", symbol_theme)
            elif "qemu" in appliance:
                return controller.symbols.get_default_symbol("qemu_guest", symbol_theme)
        return controller.symbols.get_default_symbol(category, symbol_theme)

    async def download_custom_symbols(self):
        """
        Download custom appliance symbols from our GitHub registry repository.
        """

        from . import Controller
        symbol_dir = Controller.instance().symbols.symbols_path()
        self.load_appliances()
        for appliance in self._appliances.values():
            symbol = appliance.symbol
            if symbol and not symbol.startswith(":/symbols/"):
                destination_path = os.path.join(symbol_dir, symbol)
                if not os.path.exists(destination_path):
                    await self._download_symbol(symbol, destination_path)

        # refresh the symbol cache
        Controller.instance().symbols.list()

    async def _download_symbol(self, symbol, destination_path):
        """
        Download a custom appliance symbol from our GitHub registry repository.
        """

        symbol_url = "https://raw.githubusercontent.com/GNS3/gns3-registry/master/symbols/{}".format(symbol)
        async with aiohttp.ClientSession() as session:
            async with session.get(symbol_url) as response:
                if response.status != 200:
                    log.warning("Could not retrieve appliance symbol {} from GitHub due to HTTP error code {}".format(symbol, response.status))
                else:
                    try:
                        symbol_data = await response.read()
                        log.info("Saving {} symbol to {}".format(symbol, destination_path))
                        with open(destination_path, 'wb') as f:
                            f.write(symbol_data)
                    except asyncio.TimeoutError:
                        log.warning("Timeout while downloading '{}'".format(symbol_url))
                    except OSError as e:
                        log.warning("Could not write appliance symbol '{}': {}".format(destination_path, e))

    @locking
    async def download_appliances(self):
        """
        Downloads appliance files from GitHub registry repository.
        """

        try:
            headers = {}
            if self._appliances_etag:
                log.info("Checking if appliances are up-to-date (ETag {})".format(self._appliances_etag))
                headers["If-None-Match"] = self._appliances_etag
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.github.com/repos/GNS3/gns3-registry/contents/appliances', headers=headers) as response:
                    if response.status == 304:
                        log.info("Appliances are already up-to-date (ETag {})".format(self._appliances_etag))
                        return
                    elif response.status != 200:
                        raise aiohttp.web.HTTPConflict(text="Could not retrieve appliances from GitHub due to HTTP error code {}".format(response.status))
                    etag = response.headers.get("ETag")
                    if etag:
                        self._appliances_etag = etag
                        from . import Controller
                        Controller.instance().save()
                    json_data = await response.json()
                appliances_dir = self._builtin_appliances_path()
                downloaded_appliance_files = []
                for appliance in json_data:
                    if appliance["type"] == "file":
                        appliance_name = appliance["name"]
                        log.info("Download appliance file from '{}'".format(appliance["download_url"]))
                        async with session.get(appliance["download_url"]) as response:
                            if response.status != 200:
                                log.warning("Could not download '{}' due to HTTP error code {}".format(appliance["download_url"], response.status))
                                continue
                            try:
                                appliance_data = await response.read()
                            except asyncio.TimeoutError:
                                log.warning("Timeout while downloading '{}'".format(appliance["download_url"]))
                                continue
                            path = os.path.join(appliances_dir, appliance_name)
                            try:
                                log.info("Saving {} file to {}".format(appliance_name, path))
                                with open(path, 'wb') as f:
                                    f.write(appliance_data)
                            except OSError as e:
                                raise aiohttp.web.HTTPConflict(text="Could not write appliance file '{}': {}".format(path, e))
                        downloaded_appliance_files.append(appliance_name)

                # delete old appliance files
                for filename in os.listdir(appliances_dir):
                    file_path = os.path.join(appliances_dir, filename)
                    if filename in downloaded_appliance_files:
                        continue
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            log.info("Deleting old appliance file {}".format(file_path))
                            os.unlink(file_path)
                    except OSError as e:
                        log.warning("Could not delete old appliance file '{}': {}".format(file_path, e))
                        continue

        except ValueError as e:
            raise aiohttp.web.HTTPConflict(text="Could not read appliances information from GitHub: {}".format(e))

        # download the custom symbols
        await self.download_custom_symbols()
