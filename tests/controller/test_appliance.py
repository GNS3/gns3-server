#!/usr/bin/env python
#
# Copyright (C) 2026 GNS3 Technologies Inc.
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

import pydantic
import pytest

from gns3server.controller.appliance import Appliance
from gns3server.controller.appliance_to_template import ApplianceToTemplate
from gns3server.schemas.controller.appliances import ApplianceModel


# v8 mirror of the XRd Control Plane appliance shape (docker, custom_adapters, no versions)
XRD_V8 = {
    "registry_version": 8,
    "appliance_id": "e4a3a5fe-3a13-521b-abd1-ab9483e83aa2",
    "name": "XRd Control Plane",
    "category": "router",
    "description": "Cisco IOS XRd Control Plane",
    "vendor_name": "Cisco",
    "vendor_url": "https://www.cisco.com/",
    "product_name": "XRd Control Plane",
    "status": "experimental",
    "availability": "service-contract",
    "maintainer": "GNS3 Team",
    "maintainer_email": "developers@gns3.net",
    "usage": "XRd usage",
    "symbol": ":/symbols/router.svg",
    "settings": [
        {
            "name": "Default template settings",
            "default": True,
            "template_type": "docker",
            "template_properties": {
                "adapters": 24,
                "image": "ios-xr/xrd-control-plane:24.4.1",
                "console_type": "docker_exec",
                "environment": "GNS3_SKIP_INIT=1\nGNS3_CONSOLE_CMD=/pkg/bin/xr_cli.sh",
                "extra_volumes": ["/xr-storage"],
                "custom_adapters": [
                    {"adapter_number": 0, "port_name": "MgmtEth0/RP0/CPU0/0"},
                    {"adapter_number": 1, "port_name": "Gi0/0/0/0"},
                ],
                "extra_configs": [
                    {"target": "/firstboot.cfg", "content": "!\nend\n"}
                ],
            },
        }
    ],
}


def _appliance(data, builtin=True):
    return Appliance("test.gns3a", data, builtin=builtin)


def test_v8_docker_appliance_validates_with_custom_adapters():
    # the discriminated union routes to ApplianceV8 and accepts custom_adapters
    model = ApplianceModel.model_validate(XRD_V8)
    assert model.registry_version == 8
    assert model.settings[0].template_properties.custom_adapters[0].port_name == "MgmtEth0/RP0/CPU0/0"


def test_v8_docker_appliance_type():
    assert _appliance(XRD_V8).type == "docker"


def test_v8_type_from_default_settings():
    # the default set wins over the other sets
    appliance = dict(
        XRD_V8,
        settings=[
            {"name": "a", "template_type": "docker", "template_properties": {"image": "test:latest"}},
            {"name": "b", "default": True, "template_type": "qemu", "template_properties": {"ram": 512}},
        ],
    )
    # the fixture must be a loadable appliance, not an unreachable shape
    ApplianceModel.model_validate(appliance)
    assert _appliance(appliance).type == "qemu"


def test_v8_qemu_appliance_type_without_default():
    appliance = dict(
        XRD_V8,
        settings=[{"name": "a", "template_type": "qemu", "template_properties": {"ram": 512}}],
    )
    ApplianceModel.model_validate(appliance)
    assert _appliance(appliance).type == "qemu"


def test_v6_docker_appliance_type():
    appliance = {
        "registry_version": 6,
        "name": "v6 docker",
        "status": "stable",
        "docker": {"image": "test:latest"},
    }
    assert _appliance(appliance).type == "docker"


def test_v8_docker_install_conversion():
    """
    The vendor NOS v8 shape (docker_exec console, env knobs, extra volumes,
    custom adapters, extra configs) converts into a docker template.
    """

    template = ApplianceToTemplate().new_template(_appliance(XRD_V8).asdict(), None, "local")

    assert template["template_type"] == "docker"
    assert template["image"] == "ios-xr/xrd-control-plane:24.4.1"
    assert template["console_type"] == "docker_exec"
    assert template["environment"] == "GNS3_SKIP_INIT=1\nGNS3_CONSOLE_CMD=/pkg/bin/xr_cli.sh"
    assert template["extra_volumes"] == ["/xr-storage"]
    assert template["custom_adapters"] == [
        {"adapter_number": 0, "port_name": "MgmtEth0/RP0/CPU0/0"},
        {"adapter_number": 1, "port_name": "Gi0/0/0/0"},
    ]
    assert template["extra_configs"] == [{"target": "/firstboot.cfg", "content": "!\nend\n"}]


def test_v8_docker_settings_require_image():
    """
    template_properties must be validated against the model matching
    template_type: a docker settings set without the required image is
    rejected instead of being silently misrouted to another union member.
    """

    appliance = dict(
        XRD_V8,
        settings=[
            {"name": "only", "default": True, "template_type": "docker",
             "template_properties": {"adapters": 2}},
        ],
    )
    with pytest.raises(pydantic.ValidationError):
        ApplianceModel.model_validate(appliance)


def test_v8_template_properties_validated_against_template_type():
    """
    Invalid enum values in qemu properties must be rejected at load time,
    not silently discarded by a misrouted union member.
    """

    appliance = dict(
        XRD_V8,
        settings=[
            {"name": "only", "default": True, "template_type": "qemu",
             "template_properties": {"ram": 512, "boot_priority": "zzz"}},
        ],
    )
    with pytest.raises(pydantic.ValidationError):
        ApplianceModel.model_validate(appliance)


def test_v8_qemu_kvm_property_validates():
    appliance = dict(
        XRD_V8,
        settings=[
            {"name": "only", "default": True, "template_type": "qemu",
             "template_properties": {"ram": 512, "kvm": "disable"}},
        ],
    )
    model = ApplianceModel.model_validate(appliance)
    assert model.settings[0].template_properties.kvm == "disable"


def test_v8_qemu_cpu_throttling_range():
    """
    cpu_throttling in v8 properties uses the same type and range as the
    qemu template (int, 0-800).
    """

    settings = {"name": "only", "default": True, "template_type": "qemu",
                "template_properties": {"ram": 512, "cpu_throttling": 500}}
    model = ApplianceModel.model_validate(dict(XRD_V8, settings=[settings]))
    assert model.settings[0].template_properties.cpu_throttling == 500

    for bad in (150.5, 900):
        bad_settings = dict(settings, template_properties={"ram": 512, "cpu_throttling": bad})
        with pytest.raises(pydantic.ValidationError):
            ApplianceModel.model_validate(dict(XRD_V8, settings=[bad_settings]))


def test_v8_version_idlepc_validates():
    appliance = dict(XRD_V8, versions=[{"name": "1.0", "idlepc": "0x613080c0"}])
    ApplianceModel.model_validate(appliance)

    bad = dict(XRD_V8, versions=[{"name": "1.0", "idlepc": "not-an-idlepc"}])
    with pytest.raises(pydantic.ValidationError):
        ApplianceModel.model_validate(bad)


def test_v8_netmiko_device_type_empty_string_clears():
    appliance = dict(XRD_V8, netmiko_device_type="")
    model = ApplianceModel.model_validate(appliance)
    assert model.netmiko_device_type == ""
