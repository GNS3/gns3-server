#!/usr/bin/env python
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

import uuid

from uuid import UUID
from typing import List
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.session import make_transient

from .base import BaseRepository

import gns3server.db.models as models
from gns3server import schemas

TEMPLATE_TYPE_TO_SHEMA = {
    "cloud": schemas.CloudTemplate,
    "ethernet_hub": schemas.EthernetHubTemplate,
    "ethernet_switch": schemas.EthernetSwitchTemplate,
    "docker": schemas.DockerTemplate,
    "dynamips": schemas.DynamipsTemplate,
    "vpcs": schemas.VPCSTemplate,
    "virtualbox": schemas.VirtualBoxTemplate,
    "vmware": schemas.VMwareTemplate,
    "iou": schemas.IOUTemplate,
    "qemu": schemas.QemuTemplate
}

DYNAMIPS_PLATFORM_TO_SHEMA = {
    "c7200": schemas.C7200DynamipsTemplate,
    "c3745": schemas.C3745DynamipsTemplate,
    "c3725": schemas.C3725DynamipsTemplate,
    "c3600": schemas.C3600DynamipsTemplate,
    "c2691": schemas.C2691DynamipsTemplate,
    "c2600": schemas.C2600DynamipsTemplate,
    "c1700": schemas.C1700DynamipsTemplate
}

TEMPLATE_TYPE_TO_MODEL = {
    "cloud": models.CloudTemplate,
    "docker": models.DockerTemplate,
    "dynamips": models.DynamipsTemplate,
    "ethernet_hub": models.EthernetHubTemplate,
    "ethernet_switch": models.EthernetSwitchTemplate,
    "iou": models.IOUTemplate,
    "qemu": models.QemuTemplate,
    "virtualbox": models.VirtualBoxTemplate,
    "vmware": models.VMwareTemplate,
    "vpcs": models.VPCSTemplate
}

# built-in templates have their compute_id set to None to tell clients to select a compute
BUILTIN_TEMPLATES = [
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "cloud"),
        "template_type": "cloud",
        "name": "Cloud",
        "default_name_format": "Cloud{0}",
        "category": "guest",
        "symbol": ":/symbols/cloud.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "nat"),
        "template_type": "nat",
        "name": "NAT",
        "default_name_format": "NAT{0}",
        "category": "guest",
        "symbol": ":/symbols/cloud.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "vpcs"),
        "template_type": "vpcs",
        "name": "VPCS",
        "default_name_format": "PC{0}",
        "category": "guest",
        "symbol": ":/symbols/vpcs_guest.svg",
        "base_script_file": "vpcs_base_config.txt",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "ethernet_switch"),
        "template_type": "ethernet_switch",
        "name": "Ethernet switch",
        "console_type": "none",
        "default_name_format": "Switch{0}",
        "category": "switch",
        "symbol": ":/symbols/ethernet_switch.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "ethernet_hub"),
        "template_type": "ethernet_hub",
        "name": "Ethernet hub",
        "default_name_format": "Hub{0}",
        "category": "switch",
        "symbol": ":/symbols/hub.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "frame_relay_switch"),
        "template_type": "frame_relay_switch",
        "name": "Frame Relay switch",
        "default_name_format": "FRSW{0}",
        "category": "switch",
        "symbol": ":/symbols/frame_relay_switch.svg",
        "compute_id": None,
        "builtin": True
    },
    {
        "template_id": uuid.uuid3(uuid.NAMESPACE_DNS, "atm_switch"),
        "template_type": "atm_switch",
        "name": "ATM switch",
        "default_name_format": "ATMSW{0}",
        "category": "switch",
        "symbol": ":/symbols/atm_switch.svg",
        "compute_id": None,
        "builtin": True
    },
]


class TemplatesRepository(BaseRepository):

    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)

    def get_builtin_template(self, template_id: UUID) -> dict:

        for builtin_template in BUILTIN_TEMPLATES:
            if builtin_template["template_id"] == template_id:
                return jsonable_encoder(builtin_template)

    async def get_template(self, template_id: UUID) -> dict:

        query = select(models.Template).where(models.Template.template_id == template_id)
        result = (await self._db_session.execute(query)).scalars().first()
        if result:
            return result._asjson()
        else:
            return self.get_builtin_template(template_id)

    async def get_templates(self) -> List[dict]:

        templates = []
        query = select(models.Template)
        result = await self._db_session.execute(query)
        for db_template in result.scalars().all():
            templates.append(db_template._asjson())
        for builtin_template in BUILTIN_TEMPLATES:
            templates.append(jsonable_encoder(builtin_template))
        return templates

    async def create_template(self, template_create: schemas.TemplateCreate) -> dict:

        # get the default template settings
        template_settings = jsonable_encoder(template_create, exclude_unset=True)
        template_schema = TEMPLATE_TYPE_TO_SHEMA[template_create.template_type]
        template_settings_with_defaults = template_schema.parse_obj(template_settings)
        settings = template_settings_with_defaults.dict()
        if template_create.template_type == "dynamips":
            # special case for Dynamips to cover all platform types that contain specific settings
            dynamips_template_schema = DYNAMIPS_PLATFORM_TO_SHEMA[settings["platform"]]
            dynamips_template_settings_with_defaults = dynamips_template_schema.parse_obj(template_settings)
            settings = dynamips_template_settings_with_defaults.dict()

        model = TEMPLATE_TYPE_TO_MODEL[template_create.template_type]
        db_template = model(**settings)
        self._db_session.add(db_template)
        await self._db_session.commit()
        await self._db_session.refresh(db_template)
        template = db_template._asjson()
        self._controller.notification.controller_emit("template.created", template)
        return template

    async def update_template(
            self,
            template_id: UUID,
            template_update: schemas.TemplateUpdate) -> dict:

        update_values = template_update.dict(exclude_unset=True)

        query = update(models.Template) \
            .where(models.Template.template_id == template_id) \
            .values(update_values)

        await self._db_session.execute(query)
        await self._db_session.commit()
        template = await self.get_template(template_id)
        if template:
            self._controller.notification.controller_emit("template.updated", template)
        return template

    async def delete_template(self, template_id: UUID) -> bool:

        query = delete(models.Template).where(models.Template.template_id == template_id)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        if result.rowcount > 0:
            self._controller.notification.controller_emit("template.deleted", {"template_id": str(template_id)})
            return True
        return False

    async def duplicate_template(self, template_id: UUID) -> dict:

        query = select(models.Template).where(models.Template.template_id == template_id)
        db_template = (await self._db_session.execute(query)).scalars().first()
        if not db_template:
            return db_template

        # duplicate db object with new primary key (template_id)
        self._db_session.expunge(db_template)
        make_transient(db_template)
        db_template.template_id = None
        self._db_session.add(db_template)
        await self._db_session.commit()
        await self._db_session.refresh(db_template)
        template = db_template._asjson()
        self._controller.notification.controller_emit("template.created", template)
        return template
