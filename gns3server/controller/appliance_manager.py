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
import json
import uuid
import asyncio
import aiohttp

from .appliance import Appliance
from ..config import Config
from ..utils.asyncio import locking
from ..utils.get_resource import get_resource

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

        server_config = Config.instance().get_section_config("Server")
        appliances_path = os.path.expanduser(server_config.get("appliances_path", "~/GNS3/projects"))
        os.makedirs(appliances_path, exist_ok=True)
        return appliances_path

    def load_appliances(self):
        """
        Loads appliance files from disk.
        """

        self._appliances = {}
        for directory, builtin in ((get_resource('appliances'), True,), (self.appliances_path(), False,)):
            if directory and os.path.isdir(directory):
                for file in os.listdir(directory):
                    if not file.endswith('.gns3a') and not file.endswith('.gns3appliance'):
                        continue
                    path = os.path.join(directory, file)
                    appliance_id = uuid.uuid3(uuid.NAMESPACE_URL, path)  # Generate UUID from path to avoid change between reboots
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            appliance = Appliance(appliance_id, json.load(f), builtin=builtin)
                            appliance.__json__()  # Check if loaded without error
                        if appliance.status != 'broken':
                            self._appliances[appliance.id] = appliance
                    except (ValueError, OSError, KeyError) as e:
                        log.warning("Cannot load appliance file '%s': %s", path, str(e))
                        continue

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
                        raise aiohttp.web.HTTPConflict(text="Could not retrieve appliances on GitHub due to HTTP error code {}".format(response.status))
                    etag = response.headers.get("ETag")
                    if etag:
                        self._appliances_etag = etag
                        from . import Controller
                        Controller.instance().save()
                    json_data = await response.json()
                appliances_dir = get_resource('appliances')
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
        except ValueError as e:
            raise aiohttp.web.HTTPConflict(text="Could not read appliances information from GitHub: {}".format(e))
