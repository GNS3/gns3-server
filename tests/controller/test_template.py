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

import pytest
import jsonschema

from gns3server.controller.template import Template


def test_template_json():
    a = Template(None, {
        "node_type": "qemu",
        "name": "Test",
        "default_name_format": "{name}-{0}",
        "category": 0,
        "symbol": "qemu.svg",
        "server": "local",
        "platform": "i386"
    })
    settings = a.__json__()
    assert settings["template_id"] == a.id
    assert settings["template_type"] == "qemu"
    assert settings["builtin"] == False


def test_template_json_with_not_known_category():

    with pytest.raises(jsonschema.ValidationError):
        Template(None, {
            "node_type": "qemu",
            "name": "Test",
            "default_name_format": "{name}-{0}",
            "category": 'Not known',
            "symbol": "qemu.svg",
            "server": "local",
            "platform": "i386"
        })


def test_template_json_with_platform():

    a = Template(None, {
        "node_type": "dynamips",
        "name": "Test",
        "default_name_format": "{name}-{0}",
        "category": 0,
        "symbol": "dynamips.svg",
        "image": "IOS_image.bin",
        "server": "local",
        "platform": "c3725"
    })
    settings = a.__json__()
    assert settings["template_id"] == a.id
    assert settings["template_type"] == "dynamips"
    assert settings["builtin"] == False
    assert settings["platform"] == "c3725"


def test_template_fix_linked_base():
    """
    Version of the gui before 2.1 use linked_base and the server
    linked_clone
    """

    a = Template(None, {
        "node_type": "qemu",
        "name": "Test",
        "default_name_format": "{name}-{0}",
        "category": 0,
        "symbol": "qemu.svg",
        "server": "local",
        "linked_base": True
    })
    assert a.settings["linked_clone"]
    assert "linked_base" not in a.settings
