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
import asyncio
import aiofiles
import shutil
import platformdirs


from typing import Tuple, List
from aiohttp.client_exceptions import ClientError

from uuid import UUID
from pydantic import ValidationError

from .appliance import Appliance
from ..config import Config
from ..utils.asyncio import locking
from ..utils.http_client import HTTPClient
from .controller_error import ControllerBadRequestError, ControllerNotFoundError, ControllerError
from .appliance_to_template import ApplianceToTemplate
from ..utils.images import InvalidImageError, write_image, md5sum
from ..utils.asyncio import wait_run_in_executor

from gns3server import schemas
from gns3server.utils.images import default_images_directory
from gns3server.db.repositories.images import ImagesRepository
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.services.templates import TemplatesService
from gns3server.db.repositories.rbac import RbacRepository

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
    def appliances_etag(self) -> str:
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
    def appliances(self) -> dict:
        """
        :returns: The dictionary of appliances managed by GNS3
        """

        return self._appliances

    def _custom_appliances_path(self) -> str:
        """
        Get the custom appliance storage directory
        """

        server_config = Config.instance().settings.Server
        appliances_path = os.path.expanduser(server_config.appliances_path)
        os.makedirs(appliances_path, exist_ok=True)
        return appliances_path

    def builtin_appliances_path(self, delete_first=False):
        """
        Get the built-in appliance storage directory
        """

        appname = vendor = "GNS3"
        appliances_dir = os.path.join(platformdirs.user_data_dir(appname, vendor, roaming=True), "appliances")
        if delete_first:
            shutil.rmtree(appliances_dir, ignore_errors=True)
        os.makedirs(appliances_dir, exist_ok=True)
        return appliances_dir

    def install_builtin_appliances(self):
        """
        At startup we copy the built-in appliances files.
        """

        dst_path = self.builtin_appliances_path(delete_first=True)
        log.info(f"Installing built-in appliances in '{dst_path}'")
        from . import Controller
        try:
            Controller.instance().install_resource_files(dst_path, "appliances")
        except OSError as e:
            log.error(f"Could not install built-in appliance files to {dst_path}: {e}")

    def _find_appliances_from_image_checksum(self, image_checksum: str) -> List[Tuple[Appliance, str]]:
        """
        Find appliances that matches an image checksum.
        """

        appliances = []
        for appliance in self._appliances.values():
            if appliance.images:
                for image in appliance.images:
                    if image.get("md5sum") == image_checksum:
                        appliances.append((appliance, image.get("version")))
        return appliances

    async def _download_image(
            self,
            image_dir: str,
            image_name: str,
            image_type: str,
            image_url: str,
            images_repo: ImagesRepository
    ) -> None:
        """
        Download an image.
        """

        log.info(f"Downloading image '{image_name}' from '{image_url}'")
        image_path = os.path.join(image_dir, image_name)
        try:
            async with HTTPClient.get(image_url) as response:
                if response.status != 200:
                    raise ControllerError(f"Could not download '{image_name}' due to HTTP error code {response.status}")
                await write_image(image_name, image_path, response.content.iter_any(), images_repo, allow_raw_image=True)
        except (OSError, InvalidImageError) as e:
            raise ControllerError(f"Could not save {image_type} image '{image_path}': {e}")
        except ClientError as e:
            raise ControllerError(f"Could not connect to download '{image_name}': {e}")
        except asyncio.TimeoutError:
            raise ControllerError(f"Timeout while downloading '{image_name}' from '{image_url}'")

    async def _find_appliance_version_images(
            self,
            appliance: Appliance,
            version: dict,
            images_repo: ImagesRepository,
            image_dir: str
    ) -> None:
        """
        Find all the images belonging to a specific appliance version.
        """

        version_images = version.get("images")
        if version_images:
            for appliance_key, appliance_file in version_images.items():
                for image in appliance.images:
                    if appliance_file == image.get("filename"):
                        image_checksum = image.get("md5sum")
                        image_in_db = await images_repo.get_image_by_checksum(image_checksum)
                        if image_in_db:
                            version_images[appliance_key] = image_in_db.filename
                        else:
                            # check if the image is on disk
                            # FIXME: still necessary? the image should have been discovered and saved in the db already
                            image_path = os.path.join(image_dir, appliance_file)
                            if os.path.exists(image_path) and \
                                    await wait_run_in_executor(
                                        md5sum,
                                        image_path,
                                        cache_to_md5file=False
                                    ) == image_checksum:
                                async with aiofiles.open(image_path, "rb") as f:
                                    await write_image(appliance_file, image_path, f, images_repo, allow_raw_image=True)
                            else:
                                # download the image if there is a direct download URL
                                direct_download_url = image.get("direct_download_url")
                                if direct_download_url:
                                    await self._download_image(
                                        image_dir,
                                        appliance_file,
                                        appliance.type,
                                        direct_download_url,
                                        images_repo)
                                else:
                                    raise ControllerError(f"Could not find '{appliance_file}'")

    async def _create_template(self, template_data, templates_repo, rbac_repo, current_user):
        """
        Create a new template
        """

        try:
            template_create = schemas.TemplateCreate(**template_data)
        except ValidationError as e:
            raise ControllerError(message=f"Could not validate template data: {e}")
        template = await TemplatesService(templates_repo).create_template(template_create)
        #template_id = template.get("template_id")
        #await rbac_repo.add_permission_to_user_with_path(current_user.user_id, f"/templates/{template_id}/*")
        log.info(f"Template '{template.get('name')}' has been created")

    async def _appliance_to_template(self, appliance: Appliance, version: str = None) -> dict:
        """
        Get template data from appliance
        """

        from . import Controller

        # downloading missing custom symbol for this appliance
        if appliance.symbol and not appliance.symbol.startswith(":/symbols/"):
            destination_path = os.path.join(Controller.instance().symbols.symbols_path(), appliance.symbol)
            if not os.path.exists(destination_path):
                await self._download_symbol(appliance.symbol, destination_path)
        return ApplianceToTemplate().new_template(appliance.asdict(), version, "local")  # FIXME: "local"

    async def install_appliances_from_image(
            self,
            image_path: str,
            image_checksum: str,
            images_repo: ImagesRepository,
            templates_repo: TemplatesRepository,
            rbac_repo: RbacRepository,
            current_user: schemas.User,
            image_dir: str
    ) -> None:
        """
        Install appliances using an image checksum
        """

        appliances_info = self._find_appliances_from_image_checksum(image_checksum)
        for appliance, image_version in appliances_info:
            try:
                schemas.Appliance.model_validate(appliance.asdict())
            except ValidationError as e:
                log.warning(f"Could not validate appliance '{appliance.id}': {e}")
            if appliance.versions:
                for version in appliance.versions:
                    if version.get("name") == image_version:
                        try:
                            await self._find_appliance_version_images(appliance, version, images_repo, image_dir)
                            template_data = await self._appliance_to_template(appliance, version)
                            await self._create_template(template_data, templates_repo, rbac_repo, current_user)
                        except (ControllerError, InvalidImageError) as e:
                            log.warning(f"Could not automatically create template using image '{image_path}': {e}")

    async def install_appliance(
            self,
            appliance_id: UUID,
            version: str,
            images_repo: ImagesRepository,
            templates_repo: TemplatesRepository,
            rbac_repo: RbacRepository,
            current_user: schemas.User
    ) -> None:
        """
        Install a new appliance
        """

        appliance = self._appliances.get(str(appliance_id))
        if not appliance:
            raise ControllerNotFoundError(message=f"Could not find appliance '{appliance_id}'")

        try:
            schemas.Appliance.model_validate(appliance.asdict())
        except ValidationError as e:
            raise ControllerError(message=f"Could not validate appliance '{appliance_id}': {e}")

        if version:
            if not appliance.versions:
                raise ControllerBadRequestError(message=f"Appliance '{appliance_id}' do not have versions")

            image_dir = default_images_directory(appliance.type)
            for appliance_version_info in appliance.versions:
                if appliance_version_info.get("name") == version:
                    try:
                        await self._find_appliance_version_images(appliance, appliance_version_info, images_repo, image_dir)
                    except InvalidImageError as e:
                        raise ControllerError(message=f"Image error: {e}")
                    template_data = await self._appliance_to_template(appliance, appliance_version_info)
                    return await self._create_template(template_data, templates_repo, rbac_repo, current_user)

            raise ControllerNotFoundError(message=f"Could not find version '{version}' in appliance '{appliance_id}'")

        else:
            if appliance.versions:
                # TODO: install appliance versions based on available images
                raise ControllerBadRequestError(message=f"Selecting a version is required to install "
                                                        f"appliance '{appliance_id}'")

            template_data = await self._appliance_to_template(appliance)
            await self._create_template(template_data, templates_repo, rbac_repo, current_user)

    def load_appliances(self, symbol_theme: str = None) -> None:
        """
        Loads appliance files from disk.
        """

        self._appliances = {}
        for directory, builtin in (
            (
                self.builtin_appliances_path(),
                True,
            ),
            (
                self._custom_appliances_path(),
                False,
            ),
        ):
            if directory and os.path.isdir(directory):
                for file in os.listdir(directory):
                    if not file.endswith(".gns3a") and not file.endswith(".gns3appliance"):
                        continue
                    path = os.path.join(directory, file)
                    try:
                        with open(path, encoding="utf-8") as f:
                            appliance = Appliance(path, json.load(f), builtin=builtin)
                            json_data = appliance.asdict()  # Check if loaded without error
                            if appliance.status != "broken":
                                schemas.Appliance.model_validate(json_data)
                                self._appliances[appliance.id] = appliance
                            if not appliance.symbol or appliance.symbol.startswith(":/symbols/"):
                                # apply a default symbol if the appliance has none or a default symbol
                                default_symbol = self._get_default_symbol(json_data, symbol_theme)
                                if default_symbol:
                                    appliance.symbol = default_symbol
                    except (ValueError, OSError, KeyError, ValidationError) as e:
                        print(f"Cannot load appliance file '{path}': {e}")
                        continue

    def _get_default_symbol(self, appliance: dict, symbol_theme: str) -> str:
        """
        Returns the default symbol for a given appliance.
        """

        from . import Controller

        controller = Controller.instance()
        if not symbol_theme:
            symbol_theme = controller.symbols.theme
        category = appliance["category"]
        if category == "guest":
            if "docker" in appliance:
                return controller.symbols.get_default_symbol("docker_guest", symbol_theme)
            elif "qemu" in appliance:
                return controller.symbols.get_default_symbol("qemu_guest", symbol_theme)
        return controller.symbols.get_default_symbol(category, symbol_theme)

    async def download_custom_symbols(self) -> None:
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

    async def _download_symbol(self, symbol: str, destination_path: str) -> None:
        """
        Download a custom appliance symbol from our GitHub registry repository.
        """

        symbol_url = f"https://raw.githubusercontent.com/GNS3/gns3-registry/master/symbols/{symbol}"
        log.info(f"Downloading symbol '{symbol}'")
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
    async def download_appliances(self) -> None:
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
            appliances_dir = self.builtin_appliances_path()
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
