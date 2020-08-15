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


import uuid

from tests.utils import asyncio_patch

from gns3server.controller.template import Template


async def test_template_list(controller_api, controller):

    id = str(uuid.uuid4())
    controller.template_manager.load_templates()
    controller.template_manager._templates[id] = Template(id, {
        "template_type": "qemu",
        "category": 0,
        "name": "test",
        "symbol": "guest.svg",
        "default_name_format": "{name}-{0}",
        "compute_id": "local"
    })
    response = await controller_api.get("/templates")
    assert response.status == 200
    assert response.route == "/templates"
    assert len(response.json) > 0


async def test_template_create_without_id(controller_api, controller):

    params = {"base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "template_type": "vpcs"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.route == "/templates"
    assert response.json["template_id"] is not None
    assert len(controller.template_manager.templates) == 1


async def test_template_create_with_id(controller_api, controller):

    params = {"template_id": str(uuid.uuid4()),
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "template_type": "vpcs"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.route == "/templates"
    assert response.json["template_id"] is not None
    assert len(controller.template_manager.templates) == 1


async def test_template_create_wrong_type(controller_api, controller):

    params = {"template_id": str(uuid.uuid4()),
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "template_type": "invalid_template_type"}

    response = await controller_api.post("/templates", params)
    assert response.status == 400
    assert len(controller.template_manager.templates) == 0


async def test_template_get(controller_api):

    template_id = str(uuid.uuid4())
    params = {"template_id": template_id,
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "template_type": "vpcs"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201

    response = await controller_api.get("/templates/{}".format(template_id))
    assert response.status == 200
    assert response.json["template_id"] == template_id


async def test_template_update(controller_api):

    template_id = str(uuid.uuid4())
    params = {"template_id": template_id,
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "template_type": "vpcs"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201

    response = await controller_api.get("/templates/{}".format(template_id))
    assert response.status == 200
    assert response.json["template_id"] == template_id

    params["name"] = "VPCS_TEST_RENAMED"
    response = await controller_api.put("/templates/{}".format(template_id), params)

    assert response.status == 200
    assert response.json["name"] == "VPCS_TEST_RENAMED"


async def test_template_delete(controller_api, controller):

    template_id = str(uuid.uuid4())
    params = {"template_id": template_id,
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "template_type": "vpcs"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201

    response = await controller_api.get("/templates")
    assert len(response.json) == 1
    assert len(controller.template_manager._templates) == 1

    response = await controller_api.delete("/templates/{}".format(template_id))
    assert response.status == 204

    response = await controller_api.get("/templates")
    assert len(response.json) == 0
    assert len(controller.template_manager.templates) == 0


async def test_template_duplicate(controller_api, controller):

    template_id = str(uuid.uuid4())
    params = {"template_id": template_id,
              "base_script_file": "vpcs_base_config.txt",
              "category": "guest",
              "console_auto_start": False,
              "console_type": "telnet",
              "default_name_format": "PC{0}",
              "name": "VPCS_TEST",
              "compute_id": "local",
              "symbol": ":/symbols/vpcs_guest.svg",
              "template_type": "vpcs"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201

    response = await controller_api.post("/templates/{}/duplicate".format(template_id))
    assert response.status == 201
    assert response.json["template_id"] != template_id
    params.pop("template_id")
    for param, value in params.items():
        assert response.json[param] == value

    response = await controller_api.get("/templates")
    assert len(response.json) == 2
    assert len(controller.template_manager.templates) == 2


async def test_c7200_dynamips_template_create(controller_api):

    params = {"name": "Cisco c7200 template",
              "platform": "c7200",
              "compute_id": "local",
              "image": "c7200-adventerprisek9-mz.124-24.T5.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "dynamips",
                         "auto_delete_disks": False,
                         "builtin": False,
                         "category": "router",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "default_name_format": "R{0}",
                         "disk0": 0,
                         "disk1": 0,
                         "exec_area": 64,
                         "idlemax": 500,
                         "idlepc": "",
                         "idlesleep": 30,
                         "image": "c7200-adventerprisek9-mz.124-24.T5.image",
                         "mac_addr": "",
                         "midplane": "vxr",
                         "mmap": True,
                         "name": "Cisco c7200 template",
                         "npe": "npe-400",
                         "nvram": 512,
                         "platform": "c7200",
                         "private_config": "",
                         "ram": 512,
                         "sparsemem": True,
                         "startup_config": "ios_base_startup-config.txt",
                         "symbol": ":/symbols/router.svg",
                         "system_id": "FTX0945W0MY"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_c3745_dynamips_template_create(controller_api):

    params = {"name": "Cisco c3745 template",
              "platform": "c3745",
              "compute_id": "local",
              "image": "c3745-adventerprisek9-mz.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "dynamips",
                         "auto_delete_disks": False,
                         "builtin": False,
                         "category": "router",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "default_name_format": "R{0}",
                         "disk0": 0,
                         "disk1": 0,
                         "exec_area": 64,
                         "idlemax": 500,
                         "idlepc": "",
                         "idlesleep": 30,
                         "image": "c3745-adventerprisek9-mz.124-25d.image",
                         "mac_addr": "",
                         "mmap": True,
                         "name": "Cisco c3745 template",
                         "iomem": 5,
                         "nvram": 256,
                         "platform": "c3745",
                         "private_config": "",
                         "ram": 256,
                         "sparsemem": True,
                         "startup_config": "ios_base_startup-config.txt",
                         "symbol": ":/symbols/router.svg",
                         "system_id": "FTX0945W0MY"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_c3725_dynamips_template_create(controller_api):

    params = {"name": "Cisco c3725 template",
              "platform": "c3725",
              "compute_id": "local",
              "image": "c3725-adventerprisek9-mz.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "dynamips",
                         "auto_delete_disks": False,
                         "builtin": False,
                         "category": "router",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "default_name_format": "R{0}",
                         "disk0": 0,
                         "disk1": 0,
                         "exec_area": 64,
                         "idlemax": 500,
                         "idlepc": "",
                         "idlesleep": 30,
                         "image": "c3725-adventerprisek9-mz.124-25d.image",
                         "mac_addr": "",
                         "mmap": True,
                         "name": "Cisco c3725 template",
                         "iomem": 5,
                         "nvram": 256,
                         "platform": "c3725",
                         "private_config": "",
                         "ram": 128,
                         "sparsemem": True,
                         "startup_config": "ios_base_startup-config.txt",
                         "symbol": ":/symbols/router.svg",
                         "system_id": "FTX0945W0MY"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_c3600_dynamips_template_create(controller_api):

    params = {"name": "Cisco c3600 template",
              "platform": "c3600",
              "chassis": "3660",
              "compute_id": "local",
              "image": "c3660-a3jk9s-mz.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "dynamips",
                         "auto_delete_disks": False,
                         "builtin": False,
                         "category": "router",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "default_name_format": "R{0}",
                         "disk0": 0,
                         "disk1": 0,
                         "exec_area": 64,
                         "idlemax": 500,
                         "idlepc": "",
                         "idlesleep": 30,
                         "image": "c3660-a3jk9s-mz.124-25d.image",
                         "mac_addr": "",
                         "mmap": True,
                         "name": "Cisco c3600 template",
                         "iomem": 5,
                         "nvram": 128,
                         "platform": "c3600",
                         "chassis": "3660",
                         "private_config": "",
                         "ram": 192,
                         "sparsemem": True,
                         "startup_config": "ios_base_startup-config.txt",
                         "symbol": ":/symbols/router.svg",
                         "system_id": "FTX0945W0MY"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_c3600_dynamips_template_create_wrong_chassis(controller_api):

    params = {"name": "Cisco c3600 template",
              "platform": "c3600",
              "chassis": "3650",
              "compute_id": "local",
              "image": "c3660-a3jk9s-mz.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 400


async def test_c2691_dynamips_template_create(controller_api):

    params = {"name": "Cisco c2691 template",
              "platform": "c2691",
              "compute_id": "local",
              "image": "c2691-adventerprisek9-mz.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "dynamips",
                         "auto_delete_disks": False,
                         "builtin": False,
                         "category": "router",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "default_name_format": "R{0}",
                         "disk0": 0,
                         "disk1": 0,
                         "exec_area": 64,
                         "idlemax": 500,
                         "idlepc": "",
                         "idlesleep": 30,
                         "image": "c2691-adventerprisek9-mz.124-25d.image",
                         "mac_addr": "",
                         "mmap": True,
                         "name": "Cisco c2691 template",
                         "iomem": 5,
                         "nvram": 256,
                         "platform": "c2691",
                         "private_config": "",
                         "ram": 192,
                         "sparsemem": True,
                         "startup_config": "ios_base_startup-config.txt",
                         "symbol": ":/symbols/router.svg",
                         "system_id": "FTX0945W0MY"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_c2600_dynamips_template_create(controller_api):

    params = {"name": "Cisco c2600 template",
              "platform": "c2600",
              "chassis": "2651XM",
              "compute_id": "local",
              "image": "c2600-adventerprisek9-mz.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "dynamips",
                         "auto_delete_disks": False,
                         "builtin": False,
                         "category": "router",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "default_name_format": "R{0}",
                         "disk0": 0,
                         "disk1": 0,
                         "exec_area": 64,
                         "idlemax": 500,
                         "idlepc": "",
                         "idlesleep": 30,
                         "image": "c2600-adventerprisek9-mz.124-25d.image",
                         "mac_addr": "",
                         "mmap": True,
                         "name": "Cisco c2600 template",
                         "iomem": 15,
                         "nvram": 128,
                         "platform": "c2600",
                         "chassis": "2651XM",
                         "private_config": "",
                         "ram": 160,
                         "sparsemem": True,
                         "startup_config": "ios_base_startup-config.txt",
                         "symbol": ":/symbols/router.svg",
                         "system_id": "FTX0945W0MY"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_c2600_dynamips_template_create_wrong_chassis(controller_api):

    params = {"name": "Cisco c2600 template",
              "platform": "c2600",
              "chassis": "2660XM",
              "compute_id": "local",
              "image": "c2600-adventerprisek9-mz.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 400


async def test_c1700_dynamips_template_create(controller_api):

    params = {"name": "Cisco c1700 template",
              "platform": "c1700",
              "chassis": "1760",
              "compute_id": "local",
              "image": "c1700-adventerprisek9-mz.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "dynamips",
                         "auto_delete_disks": False,
                         "builtin": False,
                         "category": "router",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "default_name_format": "R{0}",
                         "disk0": 0,
                         "disk1": 0,
                         "exec_area": 64,
                         "idlemax": 500,
                         "idlepc": "",
                         "idlesleep": 30,
                         "image": "c1700-adventerprisek9-mz.124-25d.image",
                         "mac_addr": "",
                         "mmap": True,
                         "name": "Cisco c1700 template",
                         "iomem": 15,
                         "nvram": 128,
                         "platform": "c1700",
                         "chassis": "1760",
                         "private_config": "",
                         "ram": 160,
                         "sparsemem": False,
                         "startup_config": "ios_base_startup-config.txt",
                         "symbol": ":/symbols/router.svg",
                         "system_id": "FTX0945W0MY"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_c1700_dynamips_template_create_wrong_chassis(controller_api):

    params = {"name": "Cisco c1700 template",
              "platform": "c1700",
              "chassis": "1770",
              "compute_id": "local",
              "image": "c1700-adventerprisek9-mz.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 400


async def test_dynamips_template_create_wrong_platform(controller_api):

    params = {"name": "Cisco c3900 template",
              "platform": "c3900",
              "compute_id": "local",
              "image": "c3900-test.124-25d.image",
              "template_type": "dynamips"}

    response = await controller_api.post("/templates", params)
    assert response.status == 400


async def test_iou_template_create(controller_api):

    params = {"name": "IOU template",
              "compute_id": "local",
              "path": "/path/to/i86bi_linux-ipbase-ms-12.4.bin",
              "template_type": "iou"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "iou",
                         "builtin": False,
                         "category": "router",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "default_name_format": "IOU{0}",
                         "ethernet_adapters": 2,
                         "name": "IOU template",
                         "nvram": 128,
                         "path": "/path/to/i86bi_linux-ipbase-ms-12.4.bin",
                         "private_config": "",
                         "ram": 256,
                         "serial_adapters": 2,
                         "startup_config": "iou_l3_base_startup-config.txt",
                         "symbol": ":/symbols/multilayer_switch.svg",
                         "use_default_iou_values": True,
                         "l1_keepalives": False}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_docker_template_create(controller_api):

    params = {"name": "Docker template",
              "compute_id": "local",
              "image": "gns3/endhost:latest",
              "template_type": "docker"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"adapters": 1,
                         "template_type": "docker",
                         "builtin": False,
                         "category": "guest",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_http_path": "/",
                         "console_http_port": 80,
                         "console_resolution": "1024x768",
                         "console_type": "telnet",
                         "default_name_format": "{name}-{0}",
                         "environment": "",
                         "extra_hosts": "",
                         "image": "gns3/endhost:latest",
                         "name": "Docker template",
                         "start_command": "",
                         "symbol": ":/symbols/docker_guest.svg",
                         "custom_adapters": []}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_qemu_template_create(controller_api):

    params = {"name": "Qemu template",
              "compute_id": "local",
              "platform": "i386",
              "hda_disk_image": "IOSvL2-15.2.4.0.55E.qcow2",
              "ram": 512,
              "template_type": "qemu"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"adapter_type": "e1000",
                         "adapters": 1,
                         "template_type": "qemu",
                         "bios_image": "",
                         "boot_priority": "c",
                         "builtin": False,
                         "category": "guest",
                         "cdrom_image": "",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "cpu_throttling": 0,
                         "cpus": 1,
                         "default_name_format": "{name}-{0}",
                         "first_port_name": "",
                         "hda_disk_image": "IOSvL2-15.2.4.0.55E.qcow2",
                         "hda_disk_interface": "none",
                         "hdb_disk_image": "",
                         "hdb_disk_interface": "none",
                         "hdc_disk_image": "",
                         "hdc_disk_interface": "none",
                         "hdd_disk_image": "",
                         "hdd_disk_interface": "none",
                         "initrd": "",
                         "kernel_command_line": "",
                         "kernel_image": "",
                         "legacy_networking": False,
                         "linked_clone": True,
                         "mac_address": "",
                         "name": "Qemu template",
                         "on_close": "power_off",
                         "options": "",
                         "platform": "i386",
                         "port_name_format": "Ethernet{0}",
                         "port_segment_size": 0,
                         "process_priority": "normal",
                         "qemu_path": "",
                         "ram": 512,
                         "symbol": ":/symbols/qemu_guest.svg",
                         "usage": "",
                         "custom_adapters": []}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_vmware_template_create(controller_api):

    params = {"name": "VMware template",
              "compute_id": "local",
              "template_type": "vmware",
              "vmx_path": "/path/to/vm.vmx"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"adapter_type": "e1000",
                         "adapters": 1,
                         "template_type": "vmware",
                         "builtin": False,
                         "category": "guest",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "none",
                         "default_name_format": "{name}-{0}",
                         "first_port_name": "",
                         "headless": False,
                         "linked_clone": False,
                         "name": "VMware template",
                         "on_close": "power_off",
                         "port_name_format": "Ethernet{0}",
                         "port_segment_size": 0,
                         "symbol": ":/symbols/vmware_guest.svg",
                         "use_any_adapter": False,
                         "vmx_path": "/path/to/vm.vmx",
                         "custom_adapters": []}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_virtualbox_template_create(controller_api):

    params = {"name": "VirtualBox template",
              "compute_id": "local",
              "template_type": "virtualbox",
              "vmname": "My VirtualBox VM"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"adapter_type": "Intel PRO/1000 MT Desktop (82540EM)",
                         "adapters": 1,
                         "template_type": "virtualbox",
                         "builtin": False,
                         "category": "guest",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "none",
                         "default_name_format": "{name}-{0}",
                         "first_port_name": "",
                         "headless": False,
                         "linked_clone": False,
                         "name": "VirtualBox template",
                         "on_close": "power_off",
                         "port_name_format": "Ethernet{0}",
                         "port_segment_size": 0,
                         "ram": 256,
                         "symbol": ":/symbols/vbox_guest.svg",
                         "use_any_adapter": False,
                         "vmname": "My VirtualBox VM",
                         "custom_adapters": []}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_vpcs_template_create(controller_api):

    params = {"name": "VPCS template",
              "compute_id": "local",
              "template_type": "vpcs"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "vpcs",
                         "base_script_file": "vpcs_base_config.txt",
                         "builtin": False,
                         "category": "guest",
                         "compute_id": "local",
                         "console_auto_start": False,
                         "console_type": "telnet",
                         "default_name_format": "PC{0}",
                         "name": "VPCS template",
                         "symbol": ":/symbols/vpcs_guest.svg"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_ethernet_switch_template_create(controller_api):

    params = {"name": "Ethernet switch template",
              "compute_id": "local",
              "template_type": "ethernet_switch"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "ethernet_switch",
                         "builtin": False,
                         "category": "switch",
                         "compute_id": "local",
                         "console_type": "none",
                         "default_name_format": "Switch{0}",
                         "name": "Ethernet switch template",
                         "ports_mapping": [{"ethertype": "",
                                            "name": "Ethernet0",
                                            "port_number": 0,
                                            "type": "access",
                                            "vlan": 1
                                            },
                                           {"ethertype": "",
                                            "name": "Ethernet1",
                                            "port_number": 1,
                                            "type": "access",
                                            "vlan": 1
                                            },
                                           {"ethertype": "",
                                            "name": "Ethernet2",
                                            "port_number": 2,
                                            "type": "access",
                                            "vlan": 1
                                            },
                                           {"ethertype": "",
                                            "name": "Ethernet3",
                                            "port_number": 3,
                                            "type": "access",
                                            "vlan": 1
                                            },
                                           {"ethertype": "",
                                            "name": "Ethernet4",
                                            "port_number": 4,
                                            "type": "access",
                                            "vlan": 1
                                            },
                                           {"ethertype": "",
                                            "name": "Ethernet5",
                                            "port_number": 5,
                                            "type": "access",
                                            "vlan": 1
                                            },
                                           {"ethertype": "",
                                            "name": "Ethernet6",
                                            "port_number": 6,
                                            "type": "access",
                                            "vlan": 1
                                            },
                                           {"ethertype": "",
                                            "name": "Ethernet7",
                                            "port_number": 7,
                                            "type": "access",
                                            "vlan": 1
                                            }],
                         "symbol": ":/symbols/ethernet_switch.svg"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_cloud_template_create(controller_api):

    params = {"name": "Cloud template",
              "compute_id": "local",
              "template_type": "cloud"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"template_type": "cloud",
                         "builtin": False,
                         "category": "guest",
                         "compute_id": "local",
                         "default_name_format": "Cloud{0}",
                         "name": "Cloud template",
                         "symbol": ":/symbols/cloud.svg"}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_ethernet_hub_template_create(controller_api):

    params = {"name": "Ethernet hub template",
              "compute_id": "local",
              "template_type": "ethernet_hub"}

    response = await controller_api.post("/templates", params)
    assert response.status == 201
    assert response.json["template_id"] is not None

    expected_response = {"ports_mapping": [{"port_number": 0,
                                            "name": "Ethernet0"
                                            },
                                           {"port_number": 1,
                                             "name": "Ethernet1"
                                            },
                                           {"port_number": 2,
                                            "name": "Ethernet2"
                                            },
                                           {"port_number": 3,
                                            "name": "Ethernet3"
                                            },
                                           {"port_number": 4,
                                            "name": "Ethernet4"
                                            },
                                           {"port_number": 5,
                                            "name": "Ethernet5"
                                            },
                                           {"port_number": 6,
                                            "name": "Ethernet6"
                                            },
                                           {"port_number": 7,
                                            "name": "Ethernet7"
                                            }],
                         "compute_id": "local",
                         "name": "Ethernet hub template",
                         "symbol": ":/symbols/hub.svg",
                         "default_name_format": "Hub{0}",
                         "template_type": "ethernet_hub",
                         "category": "switch",
                         "builtin": False}

    for item, value in expected_response.items():
        assert response.json.get(item) == value


async def test_create_node_from_template(controller_api, controller, project):

    id = str(uuid.uuid4())
    controller.template_manager._templates = {id: Template(id, {
        "template_type": "qemu",
        "category": 0,
        "name": "test",
        "symbol": "guest.svg",
        "default_name_format": "{name}-{0}",
        "compute_id": "example.com"
    })}
    with asyncio_patch("gns3server.controller.project.Project.add_node_from_template", return_value={"name": "test", "node_type": "qemu", "compute_id": "example.com"}) as mock:
        response = await controller_api.post("/projects/{}/templates/{}".format(project.id, id), {
            "x": 42,
            "y": 12
        })
    mock.assert_called_with(id, x=42, y=12, compute_id=None)
    assert response.route == "/projects/{project_id}/templates/{template_id}"
    assert response.status == 201
