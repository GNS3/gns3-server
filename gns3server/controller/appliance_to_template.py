#!/usr/bin/env python
# -*- coding: utf-8 -*-
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


import logging
log = logging.getLogger(__name__)


class ApplianceToTemplate:
    """
    Appliance installation.
    """

    def new_template(self, appliance_config, version, server):
        """
        Creates a new template from an appliance.
        """

        new_template = {
            "compute_id": server,
            "name": appliance_config["name"],
        }

        if version:
            new_template["version"] = version.get("name")

        if "usage" in appliance_config:
            new_template["usage"] = appliance_config["usage"]

        if appliance_config["category"] == "multilayer_switch":
            new_template["category"] = "switch"
        else:
            new_template["category"] = appliance_config["category"]

        if "symbol" in appliance_config:
            new_template["symbol"] = appliance_config.get("symbol")

        if new_template.get("symbol") is None:
            if appliance_config["category"] == "guest":
                if "docker" in appliance_config:
                    new_template["symbol"] = ":/symbols/docker_guest.svg"
                else:
                    new_template["symbol"] = ":/symbols/qemu_guest.svg"
            elif appliance_config["category"] == "router":
                new_template["symbol"] = ":/symbols/router.svg"
            elif appliance_config["category"] == "switch":
                new_template["symbol"] = ":/symbols/ethernet_switch.svg"
            elif appliance_config["category"] == "multilayer_switch":
                new_template["symbol"] = ":/symbols/multilayer_switch.svg"
            elif appliance_config["category"] == "firewall":
                new_template["symbol"] = ":/symbols/firewall.svg"

        if "qemu" in appliance_config:
            new_template["template_type"] = "qemu"
            self._add_qemu_config(new_template, appliance_config, version)
        elif "iou" in appliance_config:
            new_template["template_type"] = "iou"
            self._add_iou_config(new_template, appliance_config, version)
        elif "dynamips" in appliance_config:
            new_template["template_type"] = "dynamips"
            self._add_dynamips_config(new_template, appliance_config, version)
        elif "docker" in appliance_config:
            new_template["template_type"] = "docker"
            self._add_docker_config(new_template, appliance_config)

        return new_template

    def _add_qemu_config(self, new_config, appliance_config, version):

        new_config.update(appliance_config["qemu"])

        # the following properties are not valid for a template
        new_config.pop("kvm", None)
        new_config.pop("path", None)
        new_config.pop("arch", None)

        options = appliance_config["qemu"].get("options", "")
        if appliance_config["qemu"].get("kvm", "allow") == "disable" and "-machine accel=tcg" not in options:
            options += " -machine accel=tcg"
        new_config["options"] = options.strip()
        new_config.update(version.get("images"))

        if "arch" in appliance_config["qemu"]:
            new_config["platform"] = appliance_config["qemu"]["arch"]

        if "first_port_name" in appliance_config:
            new_config["first_port_name"] = appliance_config["first_port_name"]

        if "port_name_format" in appliance_config:
            new_config["port_name_format"] = appliance_config["port_name_format"]

        if "port_segment_size" in appliance_config:
            new_config["port_segment_size"] = appliance_config["port_segment_size"]

        if "custom_adapters" in appliance_config:
            new_config["custom_adapters"] = appliance_config["custom_adapters"]

        if "linked_clone" in appliance_config:
            new_config["linked_clone"] = appliance_config["linked_clone"]

    def _add_docker_config(self, new_config, appliance_config):

        new_config.update(appliance_config["docker"])

        if "custom_adapters" in appliance_config:
            new_config["custom_adapters"] = appliance_config["custom_adapters"]

    def _add_dynamips_config(self, new_config, appliance_config, version):

        new_config.update(appliance_config["dynamips"])
        new_config["idlepc"] = version.get("idlepc", "")
        new_config["image"] = version.get("images").get("image")

    def _add_iou_config(self, new_config, appliance_config, version):

        new_config.update(appliance_config["iou"])
        new_config["path"] = version.get("images").get("image")
