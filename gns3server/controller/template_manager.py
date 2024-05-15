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

import copy
import uuid
import aiohttp
import jsonschema

from .template import Template
from gns3server.config import Config

import logging
log = logging.getLogger(__name__)


class TemplateManager:
    """
    Manages templates.
    """

    def __init__(self):

        self._templates = {}

    @property
    def templates(self):
        """
        :returns: The dictionary of templates managed by GNS3
        """

        return self._templates

    def load_templates(self, template_settings=None):
        """
        Loads templates from controller settings.
        """

        if template_settings:
            for template_settings in template_settings:
                try:
                    template = Template(template_settings.get("template_id"), template_settings)
                    self._templates[template.id] = template
                except jsonschema.ValidationError as e:
                    message = "Cannot load template with JSON data '{}': {}".format(template_settings, e.message)
                    log.warning(message)
                    continue

        # Add builtins
        builtins = []
        if Config.instance().get_section_config("Server").getboolean("enable_builtin_templates", True):
            builtins.append(Template(uuid.uuid3(uuid.NAMESPACE_DNS, "cloud"), {"template_type": "cloud", "name": "Cloud", "default_name_format": "Cloud{0}", "category": 2, "symbol": ":/symbols/cloud.svg"}, builtin=True))
            builtins.append(Template(uuid.uuid3(uuid.NAMESPACE_DNS, "nat"), {"template_type": "nat", "name": "NAT", "default_name_format": "NAT{0}", "category": 2, "symbol": ":/symbols/nat.svg"}, builtin=True))
            builtins.append(Template(uuid.uuid3(uuid.NAMESPACE_DNS, "vpcs"), {"template_type": "vpcs", "name": "VPCS", "default_name_format": "PC{0}", "category": 2, "symbol": ":/symbols/vpcs_guest.svg", "properties": {"base_script_file": "vpcs_base_config.txt"}}, builtin=True))
            builtins.append(Template(uuid.uuid3(uuid.NAMESPACE_DNS, "ethernet_switch"), {"template_type": "ethernet_switch", "console_type": "none", "name": "Ethernet switch", "default_name_format": "Switch{0}", "category": 1, "symbol": ":/symbols/ethernet_switch.svg"}, builtin=True))
            builtins.append(Template(uuid.uuid3(uuid.NAMESPACE_DNS, "ethernet_hub"), {"template_type": "ethernet_hub", "name": "Ethernet hub", "default_name_format": "Hub{0}", "category": 1, "symbol": ":/symbols/hub.svg"}, builtin=True))
            builtins.append(Template(uuid.uuid3(uuid.NAMESPACE_DNS, "frame_relay_switch"), {"template_type": "frame_relay_switch", "name": "Frame Relay switch", "default_name_format": "FRSW{0}", "category": 1, "symbol": ":/symbols/frame_relay_switch.svg"}, builtin=True))
            builtins.append(Template(uuid.uuid3(uuid.NAMESPACE_DNS, "atm_switch"), {"template_type": "atm_switch", "name": "ATM switch", "default_name_format": "ATMSW{0}", "category": 1, "symbol": ":/symbols/atm_switch.svg"}, builtin=True))

        #FIXME: disable TraceNG
        #if sys.platform.startswith("win"):
        #    builtins.append(Template(uuid.uuid3(uuid.NAMESPACE_DNS, "traceng"), {"template_type": "traceng", "name": "TraceNG", "default_name_format": "TraceNG-{0}", "category": 2, "symbol": ":/symbols/traceng.svg", "properties": {}}, builtin=True))
        for b in builtins:
            self._templates[b.id] = b

    def add_template(self, settings):
        """
        Adds a new template.

        :param settings: template settings

        :returns: Template object
        """

        template_id = settings.get("template_id", "")
        if template_id in self._templates:
            raise aiohttp.web.HTTPConflict(text="Template ID '{}' already exists".format(template_id))
        else:
            template_id = settings.setdefault("template_id", str(uuid.uuid4()))
        try:
            template = Template(template_id, settings)
        except jsonschema.ValidationError as e:
            message = "JSON schema error adding template with JSON data '{}': {}".format(settings, e.message)
            raise aiohttp.web.HTTPBadRequest(text=message)

        from . import Controller
        Controller.instance().check_can_write_config()
        self._templates[template.id] = template
        Controller.instance().save()
        Controller.instance().notification.controller_emit("template.created", template.__json__())
        return template

    def get_template(self, template_id):
        """
        Gets a template.

        :param template_id: template identifier

        :returns: Template object
        """

        template = self._templates.get(template_id)
        if not template:
            raise aiohttp.web.HTTPNotFound(text="Template ID {} doesn't exist".format(template_id))
        return template

    def delete_template(self, template_id):
        """
        Deletes a template.

        :param template_id: template identifier
        """

        template = self.get_template(template_id)
        if template.builtin:
            raise aiohttp.web.HTTPConflict(text="Template ID {} cannot be deleted because it is a builtin".format(template_id))
        from . import Controller
        Controller.instance().check_can_write_config()
        self._templates.pop(template_id)
        Controller.instance().save()
        Controller.instance().notification.controller_emit("template.deleted", template.__json__())

    def duplicate_template(self, template_id):
        """
        Duplicates a template.

        :param template_id: template identifier
        """

        template = self.get_template(template_id)
        if template.builtin:
            raise aiohttp.web.HTTPConflict(text="Template ID {} cannot be duplicated because it is a builtin".format(template_id))
        template_settings = copy.deepcopy(template.settings)
        del template_settings["template_id"]
        return self.add_template(template_settings)


