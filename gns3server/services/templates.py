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

import os
import uuid
import pydantic

from uuid import UUID
from fastapi.encoders import jsonable_encoder
from typing import List

from gns3server import schemas
from gns3server.config import Config
import gns3server.db.models as models
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerBadRequestError,
    ControllerNotFoundError,
    ControllerForbiddenError,
)

TEMPLATE_TYPE_TO_SCHEMA = {
    "cloud": schemas.CloudTemplate,
    "ethernet_hub": schemas.EthernetHubTemplate,
    "ethernet_switch": schemas.EthernetSwitchTemplate,
    "docker": schemas.DockerTemplate,
    "dynamips": schemas.DynamipsTemplate,
    "vpcs": schemas.VPCSTemplate,
    "virtualbox": schemas.VirtualBoxTemplate,
    "vmware": schemas.VMwareTemplate,
    "iou": schemas.IOUTemplate,
    "qemu": schemas.QemuTemplate,
}

TEMPLATE_TYPE_TO_UPDATE_SCHEMA = {
    "cloud": schemas.CloudTemplateUpdate,
    "ethernet_hub": schemas.EthernetHubTemplateUpdate,
    "ethernet_switch": schemas.EthernetSwitchTemplateUpdate,
    "docker": schemas.DockerTemplateUpdate,
    "vpcs": schemas.VPCSTemplateUpdate,
    "virtualbox": schemas.VirtualBoxTemplateUpdate,
    "vmware": schemas.VMwareTemplateUpdate,
    "iou": schemas.IOUTemplateUpdate,
    "qemu": schemas.QemuTemplateUpdate,
}

DYNAMIPS_PLATFORM_TO_SCHEMA = {
    "c7200": schemas.C7200DynamipsTemplate,
    "c3745": schemas.C3745DynamipsTemplate,
    "c3725": schemas.C3725DynamipsTemplate,
    "c3600": schemas.C3600DynamipsTemplate,
    "c2691": schemas.C2691DynamipsTemplate,
    "c2600": schemas.C2600DynamipsTemplate,
    "c1700": schemas.C1700DynamipsTemplate,
}

DYNAMIPS_PLATFORM_TO_UPDATE_SCHEMA = {
    "c7200": schemas.C7200DynamipsTemplateUpdate,
    "c3745": schemas.C3745DynamipsTemplateUpdate,
    "c3725": schemas.C3725DynamipsTemplateUpdate,
    "c3600": schemas.C3600DynamipsTemplateUpdate,
    "c2691": schemas.C2691DynamipsTemplateUpdate,
    "c2600": schemas.C2600DynamipsTemplateUpdate,
    "c1700": schemas.C1700DynamipsTemplateUpdate,
}

# built-in templates have their compute_id set to None to tell clients to select a compute
BUILTIN_TEMPLATES = [
    {
        "template_id": uuid.uuid5(uuid.NAMESPACE_X500, "cloud"),
        "template_type": "cloud",
        "name": "Cloud",
        "default_name_format": "Cloud{0}",
        "category": "guest",
        "symbol": "cloud",
        "compute_id": None,
        "builtin": True,
    },
    {
        "template_id": uuid.uuid5(uuid.NAMESPACE_X500, "nat"),
        "template_type": "nat",
        "name": "NAT",
        "default_name_format": "NAT{0}",
        "category": "guest",
        "symbol": "nat",
        "compute_id": None,
        "builtin": True,
    },
    {
        "template_id": uuid.uuid5(uuid.NAMESPACE_X500, "vpcs"),
        "template_type": "vpcs",
        "name": "VPCS",
        "default_name_format": "PC{0}",
        "category": "guest",
        "symbol": "vpcs_guest",
        "base_script_file": "vpcs_base_config.txt",
        "compute_id": None,
        "builtin": True,
    },
    {
        "template_id": uuid.uuid5(uuid.NAMESPACE_X500, "ethernet_switch"),
        "template_type": "ethernet_switch",
        "name": "Ethernet switch",
        "console_type": "none",
        "default_name_format": "Switch{0}",
        "category": "switch",
        "symbol": "ethernet_switch",
        "compute_id": None,
        "builtin": True,
    },
    {
        "template_id": uuid.uuid5(uuid.NAMESPACE_X500, "ethernet_hub"),
        "template_type": "ethernet_hub",
        "name": "Ethernet hub",
        "default_name_format": "Hub{0}",
        "category": "switch",
        "symbol": "hub",
        "compute_id": None,
        "builtin": True,
    },
    {
        "template_id": uuid.uuid5(uuid.NAMESPACE_X500, "frame_relay_switch"),
        "template_type": "frame_relay_switch",
        "name": "Frame Relay switch",
        "default_name_format": "FRSW{0}",
        "category": "switch",
        "symbol": "frame_relay_switch",
        "compute_id": None,
        "builtin": True,
    },
    {
        "template_id": uuid.uuid5(uuid.NAMESPACE_X500, "atm_switch"),
        "template_type": "atm_switch",
        "name": "ATM switch",
        "default_name_format": "ATMSW{0}",
        "category": "switch",
        "symbol": "atm_switch",
        "compute_id": None,
        "builtin": True,
    },
]


class TemplatesService:

    def __init__(self, templates_repo: TemplatesRepository):

        self._templates_repo = templates_repo
        from gns3server.controller import Controller
        self._controller = Controller.instance()

        # resolve built-in template symbols
        for builtin_template in BUILTIN_TEMPLATES:
            builtin_template["symbol"] = self._controller.symbols.resolve_symbol(builtin_template["symbol"])

    def get_builtin_template(self, template_id: UUID) -> dict:

        for builtin_template in BUILTIN_TEMPLATES:
            if builtin_template["template_id"] == template_id:
                return jsonable_encoder(builtin_template)

    async def get_templates(self) -> List[dict]:

        templates = []
        db_templates = await self._templates_repo.get_templates()
        for db_template in db_templates:
            templates.append(db_template.asjson())
        if Config.instance().settings.Server.enable_builtin_templates:
            for builtin_template in BUILTIN_TEMPLATES:
                templates.append(jsonable_encoder(builtin_template))
        return templates

    async def _find_image(self, image_path: str):

        image = await self._templates_repo.get_image(image_path)
        if not image:
            raise ControllerNotFoundError(f"Image '{image_path}' could not be found in the controller database")
        if not os.path.exists(image.path):
            raise ControllerNotFoundError(f"Image '{image.path}' could not be found on disk")
        return image

    async def _find_images(self, template_type: str, settings: dict) -> List[models.Image]:

        images_to_add_to_template = []
        if template_type == "dynamips":
            if settings["image"]:
                image = await self._find_image(settings["image"])
                if image.image_type != "ios":
                    raise ControllerBadRequestError(
                        f"Image '{image.filename}' type is not 'ios' but '{image.image_type}'"
                    )
                images_to_add_to_template.append(image)
        elif template_type == "iou":
            if settings["path"]:
                image = await self._find_image(settings["path"])
                if image.image_type != "iou":
                    raise ControllerBadRequestError(
                        f"Image '{image.filename}' type is not 'iou' but '{image.image_type}'"
                    )
                images_to_add_to_template.append(image)
        elif template_type == "qemu":
            for key, value in settings.items():
                if key.endswith("_image") and value:
                    image = await self._find_image(value)
                    if image.image_type != "qemu":
                        raise ControllerBadRequestError(
                            f"Image '{image.filename}' type is not 'qemu' but '{image.image_type}'"
                        )
                    if image not in images_to_add_to_template:
                        images_to_add_to_template.append(image)
        return images_to_add_to_template

    async def create_template(self, template_create: schemas.TemplateCreate) -> dict:

        if await self._templates_repo.get_template_by_name_and_version(template_create.name, template_create.version):
            if template_create.version:
                raise ControllerError(f"A template with name '{template_create.name}' and "
                                      f"version {template_create.version} already exists")
            else:
                raise ControllerError(f"A template with name '{template_create.name}' already exists")

        try:
            # get the default template settings
            create_settings = jsonable_encoder(template_create, exclude_unset=True)
            template_schema = TEMPLATE_TYPE_TO_SCHEMA[template_create.template_type]
            template_settings = template_schema.model_validate(create_settings).model_dump()
            if template_create.template_type == "dynamips":
                # special case for Dynamips to cover all platform types that contain specific settings
                dynamips_template_schema = DYNAMIPS_PLATFORM_TO_SCHEMA[template_settings["platform"]]
                template_settings = dynamips_template_schema.model_validate(create_settings).model_dump()
        except pydantic.ValidationError as e:
            raise ControllerBadRequestError(f"JSON schema error received while creating new template: {e}")

        # resolve the template symbol
        template_settings["symbol"] = self._controller.symbols.resolve_symbol(template_settings["symbol"])
        images_to_add_to_template = await self._find_images(template_create.template_type, template_settings)
        db_template = await self._templates_repo.create_template(template_create.template_type, template_settings)
        for image in images_to_add_to_template:
            await self._templates_repo.add_image_to_template(db_template.template_id, image)
        template = db_template.asjson()
        self._controller.notification.controller_emit("template.created", template)
        return template

    async def get_template(self, template_id: UUID) -> dict:

        db_template = await self._templates_repo.get_template(template_id)
        if db_template:
            template = db_template.asjson()
        else:
            template = self.get_builtin_template(template_id)
        if not template:
            raise ControllerNotFoundError(f"Template '{template_id}' not found")
        return template

    async def _remove_image(self, template_id: UUID, image_path:str) -> None:

        image = await self._templates_repo.get_image(image_path)
        await self._templates_repo.remove_image_from_template(template_id, image)

    async def update_template(self, template_id: UUID, template_update: schemas.TemplateUpdate) -> dict:

        if self.get_builtin_template(template_id):
            raise ControllerForbiddenError(f"Template '{template_id}' cannot be updated because it is built-in")

        db_template = await self._templates_repo.get_template(template_id)
        if not db_template:
            raise ControllerNotFoundError(f"Template '{template_id}' not found")

        try:
            # validate the update settings
            update_settings = jsonable_encoder(template_update, exclude_unset=True)
            if db_template.template_type == "dynamips":
                template_schema = DYNAMIPS_PLATFORM_TO_UPDATE_SCHEMA[db_template.platform]
            else:
                template_schema = TEMPLATE_TYPE_TO_UPDATE_SCHEMA[db_template.template_type]
            template_settings = template_schema.model_validate(update_settings).model_dump(exclude_unset=True)
        except pydantic.ValidationError as e:
            raise ControllerBadRequestError(f"JSON schema error received while updating template: {e}")

        images_to_add_to_template = await self._find_images(db_template.template_type, template_settings)
        if db_template.template_type == "dynamips" and "image" in template_settings:
            await self._remove_image(db_template.template_id, db_template.image)
        elif db_template.template_type == "iou" and "path" in template_settings:
            await self._remove_image(db_template.template_id, db_template.path)
        elif db_template.template_type == "qemu":
            for key in template_update.model_dump().keys():
                if key.endswith("_image") and key in template_settings:
                    await self._remove_image(db_template.template_id, db_template.__dict__[key])

        db_template = await self._templates_repo.update_template(db_template, template_settings)
        for image in images_to_add_to_template:
            await self._templates_repo.add_image_to_template(db_template.template_id, image)
        template = db_template.asjson()
        self._controller.notification.controller_emit("template.updated", template)
        return template

    async def duplicate_template(self, template_id: UUID) -> dict:

        if self.get_builtin_template(template_id):
            raise ControllerForbiddenError(f"Template '{template_id}' cannot be duplicated because it is built-in")
        db_template = await self._templates_repo.duplicate_template(template_id)
        if not db_template:
            raise ControllerNotFoundError(f"Template '{template_id}' not found")
        template = db_template.asjson()
        self._controller.notification.controller_emit("template.created", template)
        return template

    async def delete_template(self, template_id: UUID) -> None:

        if self.get_builtin_template(template_id):
            raise ControllerForbiddenError(f"Template '{template_id}' cannot be deleted because it is built-in")
        if await self._templates_repo.delete_template(template_id):
            self._controller.notification.controller_emit("template.deleted", {"template_id": str(template_id)})
        else:
            raise ControllerNotFoundError(f"Template '{template_id}' not found")
