#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

import copy
import uuid

from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder
from gns3server import schemas

import logging
log = logging.getLogger(__name__)

ID_TO_CATEGORY = {
    3: "firewall",
    2: "guest",
    1: "switch",
    0: "router"
}

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


class Template:

    def __init__(self, template_id, settings, builtin=False):

        if template_id is None:
            self._id = str(uuid.uuid4())
        elif isinstance(template_id, uuid.UUID):
            self._id = str(template_id)
        else:
            self._id = template_id

        self._settings = copy.deepcopy(settings)

        # Version of the gui before 2.1 use linked_base
        # and the server linked_clone
        if "linked_base" in self.settings:
            linked_base = self._settings.pop("linked_base")
            if "linked_clone" not in self._settings:
                self._settings["linked_clone"] = linked_base

        # Convert old GUI category to text category
        try:
            self._settings["category"] = ID_TO_CATEGORY[self._settings["category"]]
        except KeyError:
            pass

        # The "server" setting has been replaced by "compute_id" setting in version 2.2
        if "server" in self._settings:
            self._settings["compute_id"] = self._settings.pop("server")

        # The "node_type" setting has been replaced by "template_type" setting in version 2.2
        if "node_type" in self._settings:
            self._settings["template_type"] = self._settings.pop("node_type")

        # Remove an old IOU setting
        if self._settings["template_type"] == "iou" and "image" in self._settings:
            del self._settings["image"]

        self._builtin = builtin

        if builtin is False:
            try:
                template_schema = TEMPLATE_TYPE_TO_SHEMA[self.template_type]
                template_settings_with_defaults = template_schema .parse_obj(self.__json__())
                self._settings = jsonable_encoder(template_settings_with_defaults.dict())
                if self.template_type == "dynamips":
                    # special case for Dynamips to cover all platform types that contain specific settings
                    dynamips_template_schema = DYNAMIPS_PLATFORM_TO_SHEMA[self._settings["platform"]]
                    dynamips_template_settings_with_defaults = dynamips_template_schema.parse_obj(self.__json__())
                    self._settings = jsonable_encoder(dynamips_template_settings_with_defaults.dict())
            except ValidationError as e:
                print(e) #TODO: handle errors
                raise

        log.debug('Template "{name}" [{id}] loaded'.format(name=self.name, id=self._id))

    @property
    def id(self):
        return self._id

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, settings):
        self._settings.update(settings)

    @property
    def name(self):
        return self._settings["name"]

    @property
    def compute_id(self):
        return self._settings["compute_id"]

    @property
    def template_type(self):
        return self._settings["template_type"]

    @property
    def builtin(self):
        return self._builtin

    def update(self, **kwargs):

        from gns3server.controller import Controller
        controller = Controller.instance()
        Controller.instance().check_can_write_config()
        self._settings.update(kwargs)
        controller.notification.controller_emit("template.updated", self.__json__())
        controller.save()

    def __json__(self):
        """
        Template settings.
        """

        settings = self._settings
        settings.update({"template_id": self._id,
                         "builtin": self.builtin})

        if self.builtin:
            # builin templates have compute_id set to None to tell clients
            # to select a compute
            settings["compute_id"] = None
        else:
            settings["compute_id"] = self.compute_id

        return settings
