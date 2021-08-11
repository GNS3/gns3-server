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

import os
import shutil
import json
import uuid
import asyncio

from .appliance import Appliance
from ..config import Config
from ..utils.asyncio import locking
from ..utils.get_resource import get_resource
from ..utils.http_client import HTTPClient
from .controller_error import ControllerError

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

    def appliances_path(self):
        """
        Get the image storage directory
        """

        server_config = Config.instance().settings.Server
        appliances_path = os.path.expanduser(server_config.appliances_path)
        os.makedirs(appliances_path, exist_ok=True)
        return appliances_path

    #TODO: finish
    def find_appliance_with_image(self, image_checksum):

        for appliance in self._appliances.values():
            if appliance.images:
                for image in appliance.images:
                    if image["md5sum"] == image_checksum:
                        print(f"APPLIANCE FOUND {appliance.name}")
                        version = image["version"]
                        print(f"IMAGE VERSION {version}")
                        if image.versions:
                            for version in image.versions:
                                pass

    def load_appliances(self, symbol_theme="Classic"):
        """
        Loads appliance files from disk.
        """

        self._appliances = {}
        for directory, builtin in (
            (
                get_resource("appliances"),
                True,
            ),
            (
                self.appliances_path(),
                False,
            ),
        ):
            if directory and os.path.isdir(directory):
                for file in os.listdir(directory):
                    if not file.endswith(".gns3a") and not file.endswith(".gns3appliance"):
                        continue
                    path = os.path.join(directory, file)
                    appliance_id = uuid.uuid3(
                        uuid.NAMESPACE_URL, path
                    )  # Generate UUID from path to avoid change between reboots
                    try:
                        with open(path, encoding="utf-8") as f:
                            appliance = Appliance(appliance_id, json.load(f), builtin=builtin)
                            json_data = appliance.asdict()  # Check if loaded without error
                            if appliance.status != "broken":
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

        symbol_url = f"https://raw.githubusercontent.com/GNS3/gns3-registry/master/symbols/{symbol}"
        async with HTTPClient.get(symbol_url) as response:
            if response.status != 200:
                log.warning(
                    f"Could not retrieve appliance symbol {symbol} from GitHub due to HTTP error code {response.status}"
                )
            else:
                try:
                    symbol_data = await response.read()
                    log.info(f"Saving {symbol} symbol to {destination_path}")
                    with open(destination_path, "wb") as f:
                        f.write(symbol_data)
                except asyncio.TimeoutError:
                    log.warning(f"Timeout while downloading '{symbol_url}'")
                except OSError as e:
                    log.warning(f"Could not write appliance symbol '{destination_path}': {e}")

    @locking
    async def download_appliances(self):
        """
        Downloads appliance files from GitHub registry repository.
        """

        try:
            headers = {}
            if self._appliances_etag:
                log.info(f"Checking if appliances are up-to-date (ETag {self._appliances_etag})")
                headers["If-None-Match"] = self._appliances_etag

            async with HTTPClient.get(
                "https://api.github.com/repos/GNS3/gns3-registry/contents/appliances", headers=headers
            ) as response:
                if response.status == 304:
                    log.info(f"Appliances are already up-to-date (ETag {self._appliances_etag})")
                    return
                elif response.status != 200:
                    raise ControllerError(
                        f"Could not retrieve appliances from GitHub due to HTTP error code {response.status}"
                    )
                etag = response.headers.get("ETag")
                if etag:
                    self._appliances_etag = etag
                    from . import Controller

                    Controller.instance().save()
                json_data = await response.json()
            appliances_dir = get_resource("appliances")
            downloaded_appliance_files = []
            for appliance in json_data:
                if appliance["type"] == "file":
                    appliance_name = appliance["name"]
                    log.info("Download appliance file from '{}'".format(appliance["download_url"]))
                    async with HTTPClient.get(appliance["download_url"]) as response:
                        if response.status != 200:
                            log.warning(
                                "Could not download '{}' due to HTTP error code {}".format(
                                    appliance["download_url"], response.status
                                )
                            )
                            continue
                        try:
                            appliance_data = await response.read()
                        except asyncio.TimeoutError:
                            log.warning("Timeout while downloading '{}'".format(appliance["download_url"]))
                            continue
                        path = os.path.join(appliances_dir, appliance_name)
                        try:
                            log.info(f"Saving {appliance_name} file to {path}")
                            with open(path, "wb") as f:
                                f.write(appliance_data)
                        except OSError as e:
                            raise ControllerError(f"Could not write appliance file '{path}': {e}")
                        downloaded_appliance_files.append(appliance_name)

            # delete old appliance files
            for filename in os.listdir(appliances_dir):
                file_path = os.path.join(appliances_dir, filename)
                if filename in downloaded_appliance_files:
                    continue
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        log.info(f"Deleting old appliance file {file_path}")
                        os.unlink(file_path)
                except OSError as e:
                    log.warning(f"Could not delete old appliance file '{file_path}': {e}")
                    continue

        except ValueError as e:
            raise ControllerError(f"Could not read appliances information from GitHub: {e}")

        # download the custom symbols
        await self.download_custom_symbols()
