#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
import json
import jsonschema

from gns3server.schemas.cloud_appliance import CLOUD_APPLIANCE_OBJECT_SCHEMA
from gns3server.schemas.ethernet_switch_appliance import ETHERNET_SWITCH_APPLIANCE_OBJECT_SCHEMA
from gns3server.schemas.ethernet_hub_appliance import ETHERNET_HUB_APPLIANCE_OBJECT_SCHEMA
from gns3server.schemas.docker_appliance import DOCKER_APPLIANCE_OBJECT_SCHEMA
from gns3server.schemas.vpcs_appliance import VPCS_APPLIANCE_OBJECT_SCHEMA
from gns3server.schemas.traceng_appliance import TRACENG_APPLIANCE_OBJECT_SCHEMA
from gns3server.schemas.virtualbox_appliance import VIRTUALBOX_APPLIANCE_OBJECT_SCHEMA
from gns3server.schemas.vmware_appliance import VMWARE_APPLIANCE_OBJECT_SCHEMA
from gns3server.schemas.iou_appliance import IOU_APPLIANCE_OBJECT_SCHEMA
from gns3server.schemas.qemu_appliance import QEMU_APPLIANCE_OBJECT_SCHEMA

from gns3server.schemas.dynamips_appliance import (
    DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    C7200_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    C3745_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    C3725_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    C3600_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    C2691_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    C2600_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    C1700_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA
)

import logging
log = logging.getLogger(__name__)


# Add default values for missing entries in a request, largely taken from jsonschema documentation example
# https://python-jsonschema.readthedocs.io/en/latest/faq/#why-doesn-t-my-schema-s-default-property-set-the-default-on-my-instance
def extend_with_default(validator_class):

    validate_properties = validator_class.VALIDATORS["properties"]
    def set_defaults(validator, properties, instance, schema):
        if jsonschema.Draft4Validator(schema).is_valid(instance):
            # only add default for the matching sub-schema (e.g. when using 'oneOf')
            for property, subschema in properties.items():
                if "default" in subschema:
                    instance.setdefault(property, subschema["default"])

        for error in validate_properties(validator, properties, instance, schema,):
            yield error

    return jsonschema.validators.extend(
        validator_class, {"properties" : set_defaults},
    )


ValidatorWithDefaults = extend_with_default(jsonschema.Draft4Validator)

ID_TO_CATEGORY = {
    3: "firewall",
    2: "guest",
    1: "switch",
    0: "router"
}

APPLIANCE_TYPE_TO_SHEMA = {
    "cloud": CLOUD_APPLIANCE_OBJECT_SCHEMA,
    "ethernet_hub": ETHERNET_HUB_APPLIANCE_OBJECT_SCHEMA,
    "ethernet_switch": ETHERNET_SWITCH_APPLIANCE_OBJECT_SCHEMA,
    "docker": DOCKER_APPLIANCE_OBJECT_SCHEMA,
    "dynamips": DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    "vpcs": VPCS_APPLIANCE_OBJECT_SCHEMA,
    "traceng": TRACENG_APPLIANCE_OBJECT_SCHEMA,
    "virtualbox": VIRTUALBOX_APPLIANCE_OBJECT_SCHEMA,
    "vmware": VMWARE_APPLIANCE_OBJECT_SCHEMA,
    "iou": IOU_APPLIANCE_OBJECT_SCHEMA,
    "qemu": QEMU_APPLIANCE_OBJECT_SCHEMA
}

DYNAMIPS_PLATFORM_TO_SHEMA = {
    "c7200": C7200_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    "c3745": C3745_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    "c3725": C3725_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    "c3600": C3600_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    "c2691": C2691_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    "c2600": C2600_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA,
    "c1700": C1700_DYNAMIPS_APPLIANCE_OBJECT_SCHEMA
}


class Appliance:

    def __init__(self, appliance_id, settings, builtin=False):

        if appliance_id is None:
            self._id = str(uuid.uuid4())
        elif isinstance(appliance_id, uuid.UUID):
            self._id = str(appliance_id)
        else:
            self._id = appliance_id

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

        # The "node_type" setting has been replaced by "appliance_type" setting in version 2.2
        if "node_type" in self._settings:
            self._settings["appliance_type"] = self._settings.pop("node_type")

        # Remove an old IOU setting
        if self._settings["appliance_type"] == "iou" and "image" in self._settings:
            del self._settings["image"]

        self._builtin = builtin

        if builtin is False:
            self.validate_and_apply_defaults(APPLIANCE_TYPE_TO_SHEMA[self.appliance_type])

            if self.appliance_type == "dynamips":
                # special case for Dynamips to cover all platform types that contain specific settings
                self.validate_and_apply_defaults(DYNAMIPS_PLATFORM_TO_SHEMA[self._settings["platform"]])

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
    def appliance_type(self):
        return self._settings["appliance_type"]

    @property
    def builtin(self):
        return self._builtin

    def update(self, **kwargs):

        self._settings.update(kwargs)
        from gns3server.controller import Controller
        controller = Controller.instance()
        controller.notification.controller_emit("appliance.updated", self.__json__())
        controller.save()

    def validate_and_apply_defaults(self, schema):

        validator = ValidatorWithDefaults(schema)
        try:
            validator.validate(self.__json__())
        except jsonschema.ValidationError as e:
            message = "JSON schema error {}".format(e.message)
            log.error(message)
            log.debug("Input schema: {}".format(json.dumps(schema)))
            raise

    def __json__(self):
        """
        Appliance settings.
        """

        settings = self._settings
        settings.update({"appliance_id": self._id,
                         "builtin": self.builtin})

        if not self.builtin:
            settings["compute_id"] = self.compute_id

        return settings
