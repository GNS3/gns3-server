#!/usr/bin/env python
#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Public License as published by
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
import pydantic

from gns3server.controller.appliance_to_template import ApplianceToTemplate
from gns3server.controller.controller_error import ControllerError
from gns3server.schemas.controller.appliances import ApplianceModel


# reduced mirror of the upstream vyos.gns3a (registry version 8, qemu, 2 settings sets)
VYOS_V8 = {
    "registry_version": 8,
    "appliance_id": "f82b74c4-0f30-456f-a582-63daca528502",
    "name": "VyOS Universal Router",
    "category": "router",
    "description": "VyOS",
    "vendor_name": "VyOS Inc.",
    "vendor_url": "https://vyos.io/",
    "product_name": "VyOS Universal Router",
    "status": "stable",
    "maintainer": "VyOS Inc.",
    "maintainer_email": "support@vyos.io",
    "usage": "appliance usage",
    "symbol": "vyos.svg",
    "settings": [
        {
            "name": "default x86_64",
            "default": True,
            "template_type": "qemu",
            "template_properties": {
                "adapter_type": "virtio-net-pci",
                "adapters": 10,
                "port_name_format": "eth{0}",
                "ram": 2048,
                "cpus": 4,
                "hda_disk_interface": "virtio",
                "platform": "x86_64",
                "console_type": "telnet",
                "boot_priority": "c",
                "uefi": False,
                "on_close": "shutdown_signal",
            },
        },
        {
            "name": "1.5 x86_64",
            "inherit_default_properties": True,
            "template_type": "qemu",
            "template_properties": {
                "ram": 8192,
                "cpus": 4,
            },
        },
    ],
    "images": [
        {
            "filename": "vyos-1.5.1-kvm-amd64.qcow2",
            "version": "1.5.1",
            "md5sum": "816ec7c3699a9e4f19e2b8765fd3d7eb",
            "filesize": 667549696,
        },
        {
            "filename": "vyos-1.4.5-kvm-amd64.qcow2",
            "version": "1.4.5",
            "md5sum": "06ccf7e3ed3f948a23c995133b5fbfce",
            "filesize": 557645824,
        },
    ],
    "versions": [
        {
            "name": "1.5.1",
            "settings": "1.5 x86_64",
            "images": {"hda_disk_image": "vyos-1.5.1-kvm-amd64.qcow2"},
        },
        {
            "name": "1.4.5",
            "images": {"hda_disk_image": "vyos-1.4.5-kvm-amd64.qcow2"},
        },
    ],
}


def test_v8_netmiko_device_type_copied_to_template():
    appliance = dict(VYOS_V8, netmiko_device_type="vyos_ssh")

    template = ApplianceToTemplate().new_template(appliance, VYOS_V8["versions"][1], "local")
    assert template["netmiko_device_type"] == "vyos_ssh"


def test_v8_netmiko_device_type_validates():
    model = ApplianceModel.model_validate(dict(VYOS_V8, netmiko_device_type="vyos_ssh"))
    assert model.netmiko_device_type == "vyos_ssh"

    with pytest.raises(pydantic.ValidationError):
        ApplianceModel.model_validate(dict(VYOS_V8, netmiko_device_type="Not Valid!"))


def test_v8_version_referenced_settings_with_inheritance():
    """
    A version referencing a named settings set must select it and inherit
    the default set properties (vyos 1.5.1 -> "1.5 x86_64", ram overridden to 8192).
    """

    version = VYOS_V8["versions"][0]
    template = ApplianceToTemplate().new_template(VYOS_V8, version, "local")

    assert template["template_type"] == "qemu"
    assert template["version"] == "1.5.1"
    # inherited from the default settings
    assert template["adapters"] == 10
    assert template["adapter_type"] == "virtio-net-pci"
    assert template["platform"] == "x86_64"
    # overridden by the selected settings
    assert template["ram"] == 8192
    # appliance level fields
    assert template["name"] == "VyOS Universal Router"
    assert template["category"] == "router"
    assert template["usage"] == "appliance usage"
    assert template["symbol"] == "vyos.svg"
    # version images are injected
    assert template["hda_disk_image"] == "vyos-1.5.1-kvm-amd64.qcow2"


def test_v8_default_settings_selected_when_version_has_no_reference():
    """
    A version without a settings reference falls back to the default settings set.
    """

    version = VYOS_V8["versions"][1]
    template = ApplianceToTemplate().new_template(VYOS_V8, version, "local")

    assert template["version"] == "1.4.5"
    assert template["ram"] == 2048
    assert template["hda_disk_image"] == "vyos-1.4.5-kvm-amd64.qcow2"


def test_v8_version_level_overrides():
    """
    category/usage/symbol defined at the version level override the appliance level.
    """

    version = dict(VYOS_V8["versions"][1], category="firewall", usage="version usage", symbol="firewall.svg")
    template = ApplianceToTemplate().new_template(VYOS_V8, version, "local")

    assert template["category"] == "firewall"
    assert template["usage"] == "version usage"
    assert template["symbol"] == "firewall.svg"


def test_v8_properties_take_precedence_over_version_and_appliance():
    """
    Fields defined in template_properties win over the version and appliance levels.
    """

    settings = dict(
        VYOS_V8["settings"][0],
        template_properties=dict(VYOS_V8["settings"][0]["template_properties"], usage="settings usage"),
    )
    appliance = dict(VYOS_V8, settings=[settings])
    version = dict(VYOS_V8["versions"][1], usage="version usage")

    template = ApplianceToTemplate().new_template(appliance, version, "local")
    assert template["usage"] == "settings usage"


def test_v8_template_properties_name_and_category():
    """
    name/category defined in template_properties are used for the template.
    """

    settings = dict(
        VYOS_V8["settings"][0],
        template_properties=dict(VYOS_V8["settings"][0]["template_properties"], name="VyOS 1.4", category="guest"),
    )
    appliance = dict(VYOS_V8, settings=[settings])

    template = ApplianceToTemplate().new_template(appliance, None, "local")
    assert template["name"] == "VyOS 1.4"
    assert template["category"] == "guest"


def test_v8_multilayer_switch_category_mapping():
    settings = dict(
        VYOS_V8["settings"][0],
        template_properties=dict(VYOS_V8["settings"][0]["template_properties"]),
    )
    settings["template_properties"].pop("name", None)
    appliance = dict(VYOS_V8, category="multilayer_switch", settings=[settings])

    template = ApplianceToTemplate().new_template(appliance, None, "local")
    assert template["category"] == "switch"


def test_v8_default_symbol_fallback():
    """
    Without any symbol, a docker guest gets the docker symbol, other guests the qemu one.
    """

    appliance = {
        "registry_version": 8,
        "name": "Test",
        "category": "guest",
        "settings": [{"name": "only", "template_type": "docker", "template_properties": {"image": "test:latest"}}],
    }
    template = ApplianceToTemplate().new_template(appliance, None, "local")
    assert template["symbol"] == ":/symbols/docker_guest.svg"
    assert template["template_type"] == "docker"
    assert template["image"] == "test:latest"

    appliance["settings"][0]["template_type"] = "qemu"
    appliance["settings"][0]["template_properties"] = {"ram": 512}
    template = ApplianceToTemplate().new_template(appliance, None, "local")
    assert template["symbol"] == ":/symbols/qemu_guest.svg"


def test_v8_no_inheritance_when_disabled():
    settings = dict(
        VYOS_V8["settings"][1],
        inherit_default_properties=False,
        template_properties={"ram": 4096, "adapters": 2},
    )
    appliance = dict(VYOS_V8, settings=[VYOS_V8["settings"][0], settings])
    version = dict(VYOS_V8["versions"][0], settings="1.5 x86_64")

    template = ApplianceToTemplate().new_template(appliance, version, "local")
    assert template["ram"] == 4096
    assert template["adapters"] == 2
    # not inherited
    assert "adapter_type" not in template
    assert "platform" not in template


def test_v8_unknown_settings_reference_raises():
    version = dict(VYOS_V8["versions"][0], settings="does not exist")

    with pytest.raises(ControllerError, match="Could not find settings 'does not exist'"):
        ApplianceToTemplate().new_template(VYOS_V8, version, "local")


def test_v8_multiple_settings_without_default_raises():
    appliance = dict(VYOS_V8)
    appliance["settings"] = [
        dict(VYOS_V8["settings"][0], default=None),
        dict(VYOS_V8["settings"][1]),
    ]

    with pytest.raises(ControllerError, match="none is marked as default"):
        ApplianceToTemplate().new_template(appliance, VYOS_V8["versions"][1], "local")


def test_v8_single_settings_selected_without_default_flag():
    appliance = {
        "registry_version": 8,
        "name": "Test",
        "category": "router",
        "settings": [{"name": "only", "template_type": "qemu", "template_properties": {"ram": 1024}}],
    }
    template = ApplianceToTemplate().new_template(appliance, None, "local")
    assert template["ram"] == 1024
    assert template["symbol"] == ":/symbols/router.svg"


def test_v6_path_unchanged():
    """
    Registry versions 1-6 keep using the top-level emulator blocks (regression check).
    """

    appliance = {
        "registry_version": 6,
        "name": "SRLinux",
        "category": "router",
        "symbol": ":/symbols/router.svg",
        "usage": "v6 usage",
        "docker": {
            "adapters": 35,
            "image": "ghcr.io/nokia/srlinux:latest",
            "console_type": "docker_exec",
            "environment": "GNS3_SKIP_INIT=1",
        },
    }
    template = ApplianceToTemplate().new_template(appliance, None, "local")

    assert template["template_type"] == "docker"
    assert template["image"] == "ghcr.io/nokia/srlinux:latest"
    assert template["console_type"] == "docker_exec"
    assert template["adapters"] == 35
    assert template["usage"] == "v6 usage"


def test_v6_netmiko_device_type_copied_to_template():
    appliance = {
        "registry_version": 6,
        "name": "SRLinux",
        "category": "router",
        "symbol": ":/symbols/router.svg",
        "netmiko_device_type": "nokia_srl",
        "docker": {"adapters": 35, "image": "ghcr.io/nokia/srlinux:latest"},
    }

    template = ApplianceToTemplate().new_template(appliance, None, "local")
    assert template["netmiko_device_type"] == "nokia_srl"


def test_v8_iou_version_images_mapped_to_path():
    """
    An IOU template takes the image as a path: the version image name must be
    mapped to 'path', never to an 'image' key.
    """

    appliance = {
        "registry_version": 8,
        "name": "IOU L3",
        "category": "router",
        "settings": [
            {"name": "only", "template_type": "iou",
             "template_properties": {"ethernet_adapters": 4, "ram": 256}},
        ],
    }
    version = {"name": "15.9", "images": {"image": "i86bi-linux-l3-15.9.bin"}}

    template = ApplianceToTemplate().new_template(appliance, version, "local")

    assert template["template_type"] == "iou"
    assert template["path"] == "i86bi-linux-l3-15.9.bin"
    assert "image" not in template


def test_v8_dynamips_idlepc_from_version():
    appliance = {
        "registry_version": 8,
        "name": "Cisco 7200",
        "category": "router",
        "settings": [
            {"name": "only", "template_type": "dynamips",
             "template_properties": {"ram": 512, "platform": "c7200"}},
        ],
    }
    version = {"name": "12.4", "idlepc": "0x613080c0", "images": {"image": "c7200.bin"}}

    template = ApplianceToTemplate().new_template(appliance, version, "local")

    assert template["idlepc"] == "0x613080c0"
    assert template["image"] == "c7200.bin"


def test_v8_dynamips_settings_idlepc_precedence():
    """
    An idlepc defined in template_properties wins over the version level.
    """

    appliance = {
        "registry_version": 8,
        "name": "Cisco 7200",
        "category": "router",
        "settings": [
            {"name": "only", "template_type": "dynamips",
             "template_properties": {"ram": 512, "idlepc": "0x6142da40"}},
        ],
    }
    version = {"name": "12.4", "idlepc": "0x613080c0", "images": {"image": "c7200.bin"}}

    template = ApplianceToTemplate().new_template(appliance, version, "local")

    assert template["idlepc"] == "0x6142da40"


def test_v8_qemu_kvm_disable_forces_accel_tcg():
    """
    kvm: disable is not a valid template property: it is converted to the
    equivalent qemu options like for registry versions 1-6.
    """

    appliance = {
        "registry_version": 8,
        "name": "QEMU VM",
        "category": "guest",
        "settings": [
            {"name": "only", "template_type": "qemu",
             "template_properties": {"ram": 512, "options": "-m 512", "kvm": "disable"}},
        ],
    }

    template = ApplianceToTemplate().new_template(appliance, None, "local")

    assert template["options"] == "-m 512 -machine accel=tcg"
    assert "kvm" not in template


def test_v8_qemu_kvm_allow_keeps_options():
    appliance = {
        "registry_version": 8,
        "name": "QEMU VM",
        "category": "guest",
        "settings": [
            {"name": "only", "template_type": "qemu",
             "template_properties": {"ram": 512, "options": "-m 512", "kvm": "allow"}},
        ],
    }

    template = ApplianceToTemplate().new_template(appliance, None, "local")

    assert template["options"] == "-m 512"
    assert "kvm" not in template


def test_v8_no_cross_type_inheritance():
    """
    A version referencing a docker settings set must not inherit properties
    from a default qemu settings set.
    """

    appliance = {
        "registry_version": 8,
        "name": "Mixed",
        "category": "router",
        "settings": [
            {"name": "default qemu", "default": True, "template_type": "qemu",
             "template_properties": {"ram": 2048, "adapters": 10}},
            {"name": "docker alt", "template_type": "docker",
             "template_properties": {"image": "xrd:latest", "adapters": 2}},
        ],
    }
    version = {"name": "1.0", "settings": "docker alt", "images": {"image": "xrd:1.0"}}

    template = ApplianceToTemplate().new_template(appliance, version, "local")

    assert template["template_type"] == "docker"
    assert template["adapters"] == 2
    assert "ram" not in template
    assert template["image"] == "xrd:1.0"


def test_v8_multiple_defaults_inherit_first_same_type():
    """
    With several default settings sets of the same type, the first one is
    inherited from, matching the selection rule.
    """

    appliance = {
        "registry_version": 8,
        "name": "Multi",
        "category": "router",
        "settings": [
            {"name": "default one", "default": True, "template_type": "qemu",
             "template_properties": {"ram": 1024}},
            {"name": "default two", "default": True, "template_type": "qemu",
             "template_properties": {"ram": 2048}},
            {"name": "alt", "template_type": "qemu", "template_properties": {"cpus": 2}},
        ],
    }
    version = {"name": "1.0", "settings": "alt"}

    template = ApplianceToTemplate().new_template(appliance, version, "local")

    assert template["ram"] == 1024
    assert template["cpus"] == 2


def test_v8_symbol_fallback_uses_effective_category():
    """
    The default symbol must reflect the effective category (template_properties,
    then version, then appliance), not the appliance-level one.
    """

    appliance = {
        "registry_version": 8,
        "name": "Test",
        "category": "router",
        "settings": [
            {"name": "only", "template_type": "qemu",
             "template_properties": {"ram": 512, "category": "guest"}},
        ],
    }
    template = ApplianceToTemplate().new_template(appliance, None, "local")
    assert template["category"] == "guest"
    assert template["symbol"] == ":/symbols/qemu_guest.svg"

    appliance = {
        "registry_version": 8,
        "name": "Test",
        "category": "guest",
        "settings": [
            {"name": "only", "template_type": "qemu", "template_properties": {"ram": 512}},
        ],
    }
    version = {"name": "1.0", "category": "router"}
    template = ApplianceToTemplate().new_template(appliance, version, "local")
    assert template["category"] == "router"
    assert template["symbol"] == ":/symbols/router.svg"


def test_v8_reserved_keys_cannot_be_overridden():
    """
    template_properties must not override the structural template fields.
    """

    appliance = {
        "registry_version": 8,
        "name": "Test",
        "category": "router",
        "settings": [
            {"name": "only", "template_type": "docker",
             "template_properties": {
                 "image": "xrd:latest",
                 "template_type": "qemu",
                 "compute_id": "evil-compute",
                 "version": "9.9",
             }},
        ],
    }

    template = ApplianceToTemplate().new_template(appliance, None, "local")

    assert template["template_type"] == "docker"
    assert template["compute_id"] == "local"
    assert "version" not in template


def test_v8_get_template_type():
    """
    get_template_type resolves the emulator type from the settings set
    selected for the version, like the install flow does.
    """

    converter = ApplianceToTemplate()
    appliance = {
        "registry_version": 8,
        "name": "Mixed",
        "category": "router",
        "settings": [
            {"name": "default", "default": True, "template_type": "qemu",
             "template_properties": {"ram": 512}},
            {"name": "alt", "template_type": "docker",
             "template_properties": {"image": "xrd:latest"}},
        ],
    }

    assert converter.get_template_type(appliance, {"name": "1.0", "settings": "alt"}) == "docker"
    assert converter.get_template_type(appliance, None) == "qemu"

    v6 = {"registry_version": 6, "docker": {"image": "test:latest"}}
    assert converter.get_template_type(v6, None) == "docker"


def test_v8_appliance_metadata_copied_to_template():
    """
    Appliance metadata (vendor information, default credentials...) is kept
    on the template instead of being dropped, with version level values
    overriding the appliance level ones.
    """

    appliance = dict(VYOS_V8, default_username="vyos", default_password="vyospass")
    version = dict(VYOS_V8["versions"][1], default_username="vyos145")

    template = ApplianceToTemplate().new_template(appliance, version, "local")

    metadata = template["appliance_metadata"]
    assert metadata["appliance_id"] == VYOS_V8["appliance_id"]
    assert metadata["vendor_name"] == "VyOS Inc."
    assert metadata["status"] == "stable"
    # the version level default_username overrides the appliance level one
    assert metadata["default_username"] == "vyos145"
    assert metadata["default_password"] == "vyospass"


def test_v8_appliance_metadata_version_level_overrides():
    appliance = dict(VYOS_V8, installation_instructions="appliance instructions")
    version = dict(VYOS_V8["versions"][1], installation_instructions="version instructions")

    template = ApplianceToTemplate().new_template(appliance, version, "local")

    assert template["appliance_metadata"]["installation_instructions"] == "version instructions"


def test_v6_appliance_metadata_copied_to_template():
    """
    Registry versions 1-6 appliances keep their metadata too (the fields
    they have: the v8-only ones are simply absent).
    """

    appliance = {
        "registry_version": 6,
        "name": "SRLinux",
        "category": "router",
        "description": "Nokia SR Linux",
        "vendor_name": "Nokia",
        "docker": {"adapters": 35, "image": "ghcr.io/nokia/srlinux:latest"},
    }

    template = ApplianceToTemplate().new_template(appliance, None, "local")

    metadata = template["appliance_metadata"]
    assert metadata["description"] == "Nokia SR Linux"
    assert metadata["vendor_name"] == "Nokia"
    assert "default_username" not in metadata


def test_no_appliance_metadata_when_appliance_has_none():
    appliance = {
        "registry_version": 8,
        "name": "Test",
        "category": "guest",
        "settings": [{"name": "only", "template_type": "qemu", "template_properties": {"ram": 512}}],
    }

    template = ApplianceToTemplate().new_template(appliance, None, "local")

    assert "appliance_metadata" not in template
