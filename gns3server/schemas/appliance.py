# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
from .dynamips_vm import DYNAMIPS_ADAPTERS, DYNAMIPS_WICS
from .qemu import QEMU_PLATFORMS
from .port import PORT_OBJECT_SCHEMA
from .custom_adapters import CUSTOM_ADAPTERS_ARRAY_SCHEMA


BASE_APPLIANCE_PROPERTIES = {
    "appliance_id": {
        "description": "Appliance UUID from which the node has been created. Read only",
        "type": ["null", "string"],
        "minLength": 36,
        "maxLength": 36,
        "pattern": "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
    },
    "name": {
        "description": "Appliance name",
        "type": "string",
        "minLength": 1,
    },
    "compute_id": {
        "description": "Compute identifier",
        "type": "string"
    },
    "default_name_format": {
        "description": "Default name format",
        "type": "string",
        "minLength": 1
    },
    "symbol": {
        "description": "Symbol of the appliance",
        "type": "string",
        "minLength": 1
    },
    "category": {
        "description": "Appliance category",
        "anyOf": [
            {"type": "integer"},  # old category support
            {"enum": ["router", "switch", "guest", "firewall"]}
        ]
    },
    "builtin": {
        "description": "Appliance is builtin",
        "type": "boolean"
    },
}

DYNAMIPS_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["dynamips"]
    },
    "image": {
        "description": "Path to the IOS image",
        "type": "string",
        "minLength": 1
    },
    "mmap": {
        "description": "MMAP feature",
        "type": "boolean",
        "default": True
    },
    "exec_area": {
        "description": "Exec area value",
        "type": "integer",
        "default": 64
    },
    "mac_addr": {
        "description": "Base MAC address",
        "type": "string",
        "anyOf": [
            {"pattern": "^([0-9a-fA-F]{4}\\.){2}[0-9a-fA-F]{4}$"},
            {"pattern": "^$"}
        ],
        "default": ""
    },
    "system_id": {
        "description": "System ID",
        "type": "string",
        "minLength": 1,
        "default": "FTX0945W0MY"
    },
    "startup_config": {
        "description": "IOS startup configuration file",
        "type": "string",
        "default": "ios_base_startup-config.txt"
    },
    "private_config": {
        "description": "IOS private configuration file",
        "type": "string",
        "default": ""
    },
    "idlepc": {
        "description": "Idle-PC value",
        "type": "string",
        "pattern": "^(0x[0-9a-fA-F]+)?$",
        "default": ""
    },
    "idlemax": {
        "description": "Idlemax value",
        "type": "integer",
        "default": 500
    },
    "idlesleep": {
        "description": "Idlesleep value",
        "type": "integer",
        "default": 30
    },
    "disk0": {
        "description": "Disk0 size in MB",
        "type": "integer",
        "default": 0
    },
    "disk1": {
        "description": "Disk1 size in MB",
        "type": "integer",
        "default": 0
    },
    "auto_delete_disks": {
        "description": "Automatically delete nvram and disk files",
        "type": "boolean",
        "default": False
    },
    "wic0": DYNAMIPS_WICS,
    "wic1": DYNAMIPS_WICS,
    "wic2": DYNAMIPS_WICS,
    "slot0": DYNAMIPS_ADAPTERS,
    "slot1": DYNAMIPS_ADAPTERS,
    "slot2": DYNAMIPS_ADAPTERS,
    "slot3": DYNAMIPS_ADAPTERS,
    "slot4": DYNAMIPS_ADAPTERS,
    "slot5": DYNAMIPS_ADAPTERS,
    "slot6": DYNAMIPS_ADAPTERS,
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    }
}

DYNAMIPS_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
DYNAMIPS_APPLIANCE_PROPERTIES["category"]["default"] = "router"
DYNAMIPS_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "R{0}"
DYNAMIPS_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/router.svg"

C7200_DYNAMIPS_APPLIANCE_PROPERTIES = {
    "platform": {
        "description": "Platform type",
        "enum": ["c7200"]
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 512
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 512
    },
    "npe": {
        "description": "NPE model",
        "enum": ["npe-100", "npe-150", "npe-175", "npe-200", "npe-225", "npe-300", "npe-400", "npe-g2"],
        "default": "npe-400"
    },
    "midplane": {
        "description": "Midplane model",
        "enum": ["std", "vxr"],
        "default": "vxr"
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C7200_DYNAMIPS_APPLIANCE_PROPERTIES.update(DYNAMIPS_APPLIANCE_PROPERTIES)

C3745_DYNAMIPS_APPLIANCE_PROPERTIES = {
    "platform": {
        "description": "Platform type",
        "enum": ["c3745"]
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 256
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 256
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 5
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C3745_DYNAMIPS_APPLIANCE_PROPERTIES.update(DYNAMIPS_APPLIANCE_PROPERTIES)

C3725_DYNAMIPS_APPLIANCE_PROPERTIES = {
    "platform": {
        "description": "Platform type",
        "enum": ["c3725"]
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 128
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 256
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 5
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C3725_DYNAMIPS_APPLIANCE_PROPERTIES.update(DYNAMIPS_APPLIANCE_PROPERTIES)

C3600_DYNAMIPS_APPLIANCE_PROPERTIES = {
    "platform": {
        "description": "Platform type",
        "enum": ["c3600"]
    },
    "chassis": {
        "description": "Chassis type",
        "enum": ["3620", "3640", "3660"],
        "default": "3660"
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 192
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 128
    },

    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 5
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C3600_DYNAMIPS_APPLIANCE_PROPERTIES.update(DYNAMIPS_APPLIANCE_PROPERTIES)

C2691_DYNAMIPS_APPLIANCE_PROPERTIES = {
    "platform": {
        "description": "Platform type",
        "enum": ["c2691"]
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 192
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 256
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 5
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C2691_DYNAMIPS_APPLIANCE_PROPERTIES.update(DYNAMIPS_APPLIANCE_PROPERTIES)

C2600_DYNAMIPS_APPLIANCE_PROPERTIES = {
    "platform": {
        "description": "Platform type",
        "enum": ["c2600"]
    },
    "chassis": {
        "description": "Chassis type",
        "enum": ["2610", "2620", "2610XM", "2620XM", "2650XM", "2621", "2611XM", "2621XM", "2651XM"],
        "default": "2651XM"
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 160
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 128
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 15
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": True
    }
}

C2600_DYNAMIPS_APPLIANCE_PROPERTIES.update(DYNAMIPS_APPLIANCE_PROPERTIES)

C1700_DYNAMIPS_APPLIANCE_PROPERTIES = {
    "platform": {
        "description": "Platform type",
        "enum": ["c1700"]
    },
    "chassis": {
        "description": "Chassis type",
        "enum": ["1720", "1721", "1750", "1751", "1760"],
        "default": "1760"
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 160
    },
    "nvram": {
        "description": "Amount of NVRAM in KB",
        "type": "integer",
        "default": 128
    },
    "iomem": {
        "description": "I/O memory percentage",
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "default": 15
    },
    "sparsemem": {
        "description": "Sparse memory feature",
        "type": "boolean",
        "default": False
    }
}

C1700_DYNAMIPS_APPLIANCE_PROPERTIES.update(DYNAMIPS_APPLIANCE_PROPERTIES)

IOU_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["iou"]
    },
    "path": {
        "description": "Path of IOU executable",
        "type": "string",
        "minLength": 1
    },
    "ethernet_adapters": {
        "description": "Number of ethernet adapters",
        "type": "integer",
        "default": 2
    },
    "serial_adapters": {
        "description": "Number of serial adapters",
        "type": "integer",
        "default": 2
    },
    "ram": {
        "description": "RAM in MB",
        "type": "integer",
        "default": 256
    },
    "nvram": {
        "description": "NVRAM in KB",
        "type": "integer",
        "default": 128
    },
    "use_default_iou_values": {
        "description": "Use default IOU values",
        "type": "boolean",
        "default": True
    },
    "startup_config": {
        "description": "Startup-config of IOU",
        "type": "string",
        "default": "iou_l3_base_startup-config.txt"
    },
    "private_config": {
        "description": "Private-config of IOU",
        "type": "string",
        "default": ""
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    },
}

IOU_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
IOU_APPLIANCE_PROPERTIES["category"]["default"] = "router"
IOU_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "IOU{0}"
IOU_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/multilayer_switch.svg"

DOCKER_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["docker"]
    },
    "image": {
        "description": "Docker image name",
        "type": "string",
        "minLength": 1
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 99,
        "default": 1
    },
    "start_command": {
        "description": "Docker CMD entry",
        "type": "string",
        "default": ""
    },
    "environment": {
        "description": "Docker environment variables",
        "type": "string",
        "default": ""
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "vnc", "http", "https", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False,
    },
    "console_http_port": {
        "description": "Internal port in the container for the HTTP server",
        "type": "integer",
        "minimum": 1,
        "maximum": 65535,
        "default": 80
    },
    "console_http_path": {
        "description": "Path of the web interface",
        "type": "string",
        "minLength": 1,
        "default": "/"
    },
    "console_resolution": {
        "description": "Console resolution for VNC",
        "type": "string",
        "pattern": "^[0-9]+x[0-9]+$",
        "default": "1024x768"
    },
    "extra_hosts": {
        "description": "Docker extra hosts (added to /etc/hosts)",
        "type": "string",
        "default": "",
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

DOCKER_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
DOCKER_APPLIANCE_PROPERTIES["category"]["default"] = "guest"
DOCKER_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "{name}-{0}"
DOCKER_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/docker_guest.svg"

QEMU_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["qemu"]
    },
    "usage": {
        "description": "How to use the Qemu VM",
        "type": "string",
        "default": ""
    },
    "qemu_path": {
        "description": "Path to QEMU",
        "type": "string",
        "default": ""
    },
    "platform": {
        "description": "Platform to emulate",
        "enum": QEMU_PLATFORMS,
        "default": "i386"
    },
    "linked_clone": {
        "description": "Whether the VM is a linked clone or not",
        "type": "boolean",
        "default": True
    },
    "ram": {
        "description": "Amount of RAM in MB",
        "type": "integer",
        "default": 256
    },
    "cpus": {
        "description": "Number of vCPUs",
        "type": "integer",
        "minimum": 1,
        "maximum": 255,
        "default": 1
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 275,
        "default": 1
    },
    "adapter_type": {
        "description": "QEMU adapter type",
        "type": "string",
        "enum": ["e1000", "i82550", "i82551", "i82557a", "i82557b", "i82557c", "i82558a","i82558b", "i82559a",
                 "i82559b", "i82559c", "i82559er", "i82562", "i82801", "ne2k_pci", "pcnet", "rtl8139", "virtio",
                 "virtio-net-pci", "vmxnet3"],
        "default": "e1000"
    },
    "mac_address": {
        "description": "QEMU MAC address",
        "type": "string",
        "anyOf": [
            {"pattern": "^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})$"},
            {"pattern": "^$"}
        ],
        "default": "",
    },
    "first_port_name": {
        "description": "Optional name of the first networking port example: eth0",
        "type": "string",
        "default": ""
    },
    "port_name_format": {
        "description": "Optional formatting of the networking port example: eth{0}",
        "type": "string",
        "default": "Ethernet{0}"
    },
    "port_segment_size": {
        "description": "Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2",
        "type": "integer",
        "default": 0
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "vnc", "spice", "spice+agent", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    },
    "boot_priority": {
        "description": "QEMU boot priority",
        "enum": ["c", "d", "n", "cn", "cd", "dn", "dc", "nc", "nd"],
        "default": "c"
    },
    "hda_disk_image": {
        "description": "QEMU hda disk image path",
        "type": "string",
        "default": ""
    },
    "hda_disk_interface": {
        "description": "QEMU hda interface",
        "enum": ["ide", "sata", "scsi", "sd", "mtd", "floppy", "pflash", "virtio", "none"],
        "default": "ide"
    },
    "hdb_disk_image": {
        "description": "QEMU hdb disk image path",
        "type": "string",
        "default": ""
    },
    "hdb_disk_interface": {
        "description": "QEMU hdb interface",
        "enum": ["ide", "sata", "scsi", "sd", "mtd", "floppy", "pflash", "virtio", "none"],
        "default": "ide"
    },
    "hdc_disk_image": {
        "description": "QEMU hdc disk image path",
        "type": "string",
        "default": ""
    },
    "hdc_disk_interface": {
        "description": "QEMU hdc interface",
        "enum": ["ide", "sata", "scsi", "sd", "mtd", "floppy", "pflash", "virtio", "none"],
        "default": "ide"
    },
    "hdd_disk_image": {
        "description": "QEMU hdd disk image path",
        "type": "string",
        "default": ""
    },
    "hdd_disk_interface": {
        "description": "QEMU hdd interface",
        "enum": ["ide", "sata", "scsi", "sd", "mtd", "floppy", "pflash", "virtio", "none"],
        "default": "ide"
    },
    "cdrom_image": {
        "description": "QEMU cdrom image path",
        "type": "string",
        "default": ""
    },
    "initrd": {
        "description": "QEMU initrd path",
        "type": "string",
        "default": ""
    },
    "kernel_image": {
        "description": "QEMU kernel image path",
        "type": "string",
        "default": ""
    },
    "bios_image": {
        "description": "QEMU bios image path",
        "type": "string",
        "default": ""
    },
    "kernel_command_line": {
        "description": "QEMU kernel command line",
        "type": "string",
        "default": ""
    },
    "legacy_networking": {
        "description": "Use QEMU legagy networking commands (-net syntax)",
        "type": "boolean",
        "default": False
    },
    "on_close": {
        "description": "Action to execute on the VM is closed",
        "enum": ["power_off", "shutdown_signal", "save_vm_state"],
        "default": "power_off"
    },
    "cpu_throttling": {
        "description": "Percentage of CPU allowed for QEMU",
        "minimum": 0,
        "maximum": 800,
        "type": "integer",
        "default": 0
    },
    "process_priority": {
        "description": "Process priority for QEMU",
        "enum": ["realtime", "very high", "high", "normal", "low", "very low"],
        "default": "normal"
    },
    "options": {
        "description": "Additional QEMU options",
        "type": "string",
        "default": ""
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

QEMU_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
QEMU_APPLIANCE_PROPERTIES["category"]["default"] = "guest"
QEMU_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "{name}-{0}"
QEMU_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/qemu_guest.svg"

VMWARE_VM_SETTINGS = {
    "vmx_path": "",


    "console_type": "none",
    "console_auto_start": False,
}

VMWARE_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["vmware"]
    },
    "vmx_path": {
        "description": "Path to the vmx file",
        "type": "string",
        "minLength": 1,
    },
    "linked_clone": {
        "description": "Whether the VM is a linked clone or not",
        "type": "boolean",
        "default": False
    },
    "first_port_name": {
        "description": "Optional name of the first networking port example: eth0",
        "type": "string",
        "default": ""
    },
    "port_name_format": {
        "description": "Optional formatting of the networking port example: eth{0}",
        "type": "string",
        "default": "Ethernet{0}"
    },
    "port_segment_size": {
        "description": "Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2",
        "type": "integer",
        "default": 0
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 10,  # maximum adapters support by VMware VMs,
        "default": 1
    },
    "adapter_type": {
        "description": "VMware adapter type",
        "enum": ["default", "e1000", "e1000e", "flexible", "vlance", "vmxnet", "vmxnet2", "vmxnet3"],
        "default": "e1000"
    },
    "use_any_adapter": {
        "description": "Allow GNS3 to use any VMware adapter",
        "type": "boolean",
        "default": False
    },
    "headless": {
        "description": "Headless mode",
        "type": "boolean",
        "default": False
    },
    "on_close": {
        "description": "Action to execute on the VM is closed",
        "enum": ["power_off", "shutdown_signal", "save_vm_state"],
        "default": "power_off"
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "none"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

VMWARE_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
VMWARE_APPLIANCE_PROPERTIES["category"]["default"] = "guest"
VMWARE_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "{name}-{0}"
VMWARE_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/vmware_guest.svg"

VIRTUALBOX_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["virtualbox"]
    },
    "vmname": {
        "description": "VirtualBox VM name (in VirtualBox itself)",
        "type": "string",
        "minLength": 1,
    },
    "ram": {
        "description": "Amount of RAM",
        "minimum": 0,
        "maximum": 65535,
        "type": "integer",
        "default": 256
    },
    "linked_clone": {
        "description": "Whether the VM is a linked clone or not",
        "type": "boolean",
        "default": False
    },
    "adapters": {
        "description": "Number of adapters",
        "type": "integer",
        "minimum": 0,
        "maximum": 36,  # maximum given by the ICH9 chipset in VirtualBox
        "default": 1
    },
    "use_any_adapter": {
        "description": "Allow GNS3 to use any VirtualBox adapter",
        "type": "boolean",
        "default": False
    },
    "adapter_type": {
        "description": "VirtualBox adapter type",
        "enum": ["PCnet-PCI II (Am79C970A)",
                 "PCNet-FAST III (Am79C973)",
                 "Intel PRO/1000 MT Desktop (82540EM)",
                 "Intel PRO/1000 T Server (82543GC)",
                 "Intel PRO/1000 MT Server (82545EM)",
                 "Paravirtualized Network (virtio-net)"],
        "default": "Intel PRO/1000 MT Desktop (82540EM)"
    },
    "first_port_name": {
        "description": "Optional name of the first networking port example: eth0",
        "type": "string",
        "default": ""
    },
    "port_name_format": {
        "description": "Optional formatting of the networking port example: eth{0}",
        "type": "string",
        "default": "Ethernet{0}"
    },
    "port_segment_size": {
        "description": "Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2",
        "type": "integer",
        "default": 0
    },
    "headless": {
        "description": "Headless mode",
        "type": "boolean",
        "default": False
    },
    "on_close": {
        "description": "Action to execute on the VM is closed",
        "enum": ["power_off", "shutdown_signal", "save_vm_state"],
        "default": "power_off"
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "none"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    },
    "custom_adapters": CUSTOM_ADAPTERS_ARRAY_SCHEMA
}

VIRTUALBOX_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
VIRTUALBOX_APPLIANCE_PROPERTIES["category"]["default"] = "guest"
VIRTUALBOX_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "{name}-{0}"
VIRTUALBOX_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/vbox_guest.svg"

TRACENG_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["traceng"]
    },
    "ip_address": {
        "description": "Source IP address for tracing",
        "type": ["string"],
        "minLength": 1
    },
    "default_destination": {
        "description": "Default destination IP address or hostname for tracing",
        "type": ["string"],
        "minLength": 1
    },
    "console_type": {
        "description": "Console type",
        "enum": ["none"],
        "default": "none"
    },
}

TRACENG_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
TRACENG_APPLIANCE_PROPERTIES["category"]["default"] = "guest"
TRACENG_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "TraceNG{0}"
TRACENG_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/traceng.svg"

VPCS_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["vpcs"]
    },
    "base_script_file": {
        "description": "Script file",
        "type": "string",
        "minLength": 1,
        "default": "vpcs_base_config.txt"
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "telnet"
    },
    "console_auto_start": {
        "description": "Automatically start the console when the node has started",
        "type": "boolean",
        "default": False
    },
}

VPCS_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
VPCS_APPLIANCE_PROPERTIES["category"]["default"] = "guest"
VPCS_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "PC{0}"
VPCS_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/vpcs_guest.svg"

ETHERNET_SWITCH_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["ethernet_switch"]
    },
    "ports_mapping": {
        "type": "array",
        "default": [{"ethertype": "",
                     "name": "Ethernet0",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 0
                     },
                    {"ethertype": "",
                     "name": "Ethernet1",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 1
                     },
                    {"ethertype": "",
                     "name": "Ethernet2",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 2
                     },
                    {"ethertype": "",
                     "name": "Ethernet3",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 3
                     },
                    {"ethertype": "",
                     "name": "Ethernet4",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 4
                     },
                    {"ethertype": "",
                     "name": "Ethernet5",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 5
                     },
                    {"ethertype": "",
                     "name": "Ethernet6",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 6
                     },
                    {"ethertype": "",
                     "name": "Ethernet7",
                     "vlan": 1,
                     "type": "access",
                     "port_number": 7
                     }
                    ],
        "items": [
            {"type": "object",
             "oneOf": [
                 {
                     "description": "Ethernet port",
                     "properties": {
                         "name": {
                             "description": "Port name",
                             "type": "string",
                             "minLength": 1
                         },
                         "port_number": {
                             "description": "Port number",
                             "type": "integer",
                             "minimum": 0
                         },
                         "type": {
                             "description": "Port type",
                             "enum": ["access", "dot1q", "qinq"],
                         },
                         "vlan": {"description": "VLAN number",
                                  "type": "integer",
                                  "minimum": 1
                                  },
                         "ethertype": {
                             "description": "QinQ Ethertype",
                             "enum": ["", "0x8100", "0x88A8", "0x9100", "0x9200"],
                         },
                     },
                     "required": ["name", "port_number", "type"],
                     "additionalProperties": False
                 },
             ]},
        ]
    },
    "console_type": {
        "description": "Console type",
        "enum": ["telnet", "none"],
        "default": "telnet"
    },
}

ETHERNET_SWITCH_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
ETHERNET_SWITCH_APPLIANCE_PROPERTIES["category"]["default"] = "switch"
ETHERNET_SWITCH_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "Switch{0}"
ETHERNET_SWITCH_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/ethernet_switch.svg"

ETHERNET_HUB_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["ethernet_hub"]
    },
    "ports_mapping": {
        "type": "array",
        "default": [{"port_number": 0,
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
                     }
        ],
        "items": [
            {"type": "object",
             "oneOf": [{"description": "Ethernet port",
                        "properties": {"name": {"description": "Port name",
                                                "type": "string",
                                                "minLength": 1},
                                       "port_number": {
                                           "description": "Port number",
                                           "type": "integer",
                                           "minimum": 0}
                                       },
                        "required": ["name", "port_number"],
                        "additionalProperties": False}
                       ],
             }
        ]
    }
}

ETHERNET_HUB_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
ETHERNET_HUB_APPLIANCE_PROPERTIES["category"]["default"] = "switch"
ETHERNET_HUB_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "Hub{0}"
ETHERNET_HUB_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/hub.svg"

CLOUD_APPLIANCE_PROPERTIES = {
    "appliance_type": {
        "enum": ["cloud"]
    },
    "ports_mapping": {
        "type": "array",
        "items": [
            PORT_OBJECT_SCHEMA
        ]
    },
    "remote_console_host": {
        "description": "Remote console host or IP",
        "type": ["string"],
        "minLength": 1
    },
    "remote_console_port": {
        "description": "Console TCP port",
        "minimum": 1,
        "maximum": 65535,
        "type": "integer"
    },
    "remote_console_type": {
        "description": "Console type",
        "enum": ["telnet", "vnc", "spice", "http", "https", "none"]
    },
    "remote_console_http_path": {
        "description": "Path of the remote web interface",
        "type": "string",
        "minLength": 1
    },
}

CLOUD_APPLIANCE_PROPERTIES.update(copy.deepcopy(BASE_APPLIANCE_PROPERTIES))
CLOUD_APPLIANCE_PROPERTIES["category"]["default"] = "guest"
CLOUD_APPLIANCE_PROPERTIES["default_name_format"]["default"] = "Cloud{0}"
CLOUD_APPLIANCE_PROPERTIES["symbol"]["default"] = ":/symbols/cloud.svg"

APPLIANCE_OBJECT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "A template object",
    "type": "object",
    "definitions": {
        "c7200": {
            "description": "c7200 appliance",
            "properties": C7200_DYNAMIPS_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["platform", "image"]
        },
        "c3745": {
            "description": "c3745 appliance",
            "properties": C3745_DYNAMIPS_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["platform", "image"]
        },
        "c3725": {
            "description": "c3725 appliance",
            "properties": C3725_DYNAMIPS_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["platform", "image"]
        },
        "c3600": {
            "description": "c3600 appliance",
            "properties": C3600_DYNAMIPS_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["platform", "image", "chassis"]
        },
        "c2691": {
            "description": "c2691 appliance",
            "properties": C2691_DYNAMIPS_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["platform", "image"]
        },
        "c2600": {
            "description": "c2600 appliance",
            "properties": C2600_DYNAMIPS_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["platform", "image", "chassis"]
        },
        "c1700": {
            "description": "c1700 appliance",
            "properties": C1700_DYNAMIPS_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["platform", "image", "chassis"]
        },
        "IOU": {
            "description": "IOU appliance",
            "properties": IOU_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["path"]
        },
        "Docker": {
            "description": "Docker appliance",
            "properties": DOCKER_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["image"]
        },
        "Qemu": {
            "description": "Qemu appliance",
            "properties": QEMU_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "VMware": {
            "description": "VMware appliance",
            "properties": VMWARE_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["vmx_path"]
        },
        "VirtualBox": {
            "description": "VirtualBox appliance",
            "properties": VIRTUALBOX_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
            "required": ["vmname"]
        },
        "TraceNG": {
            "description": "TraceNG appliance",
            "properties": TRACENG_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "VPCS": {
            "description": "VPCS appliance",
            "properties": VPCS_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "EthernetSwitch": {
            "description": "Ethernet switch appliance",
            "properties": ETHERNET_SWITCH_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "EthernetHub": {
            "description": "Ethernet hub appliance",
            "properties": ETHERNET_HUB_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
        "Cloud": {
            "description": "Cloud appliance",
            "properties": CLOUD_APPLIANCE_PROPERTIES,
            "additionalProperties": False,
        },
    },
    "oneOf": [
        {"$ref": "#/definitions/c7200"},
        {"$ref": "#/definitions/c3745"},
        {"$ref": "#/definitions/c3725"},
        {"$ref": "#/definitions/c3600"},
        {"$ref": "#/definitions/c2691"},
        {"$ref": "#/definitions/c2600"},
        {"$ref": "#/definitions/c1700"},
        {"$ref": "#/definitions/IOU"},
        {"$ref": "#/definitions/Docker"},
        {"$ref": "#/definitions/Qemu"},
        {"$ref": "#/definitions/VMware"},
        {"$ref": "#/definitions/VirtualBox"},
        {"$ref": "#/definitions/TraceNG"},
        {"$ref": "#/definitions/VPCS"},
        {"$ref": "#/definitions/EthernetSwitch"},
        {"$ref": "#/definitions/EthernetHub"},
        {"$ref": "#/definitions/Cloud"},
    ],
    "required": ["name", "appliance_type", "appliance_id", "category", "compute_id", "default_name_format", "symbol"]
}

APPLIANCE_CREATE_SCHEMA = copy.deepcopy(APPLIANCE_OBJECT_SCHEMA)

# create schema
# these properties are not required to create an appliance
APPLIANCE_CREATE_SCHEMA["required"].remove("appliance_id")
APPLIANCE_CREATE_SCHEMA["required"].remove("category")
APPLIANCE_CREATE_SCHEMA["required"].remove("default_name_format")
APPLIANCE_CREATE_SCHEMA["required"].remove("symbol")

# update schema
APPLIANCE_UPDATE_SCHEMA = copy.deepcopy(APPLIANCE_OBJECT_SCHEMA)
del APPLIANCE_UPDATE_SCHEMA["required"]

APPLIANCE_USAGE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "description": "Request validation to use an Appliance instance",
    "type": "object",
    "properties": {
        "x": {
            "description": "X position",
            "type": "integer"
        },
        "y": {
            "description": "Y position",
            "type": "integer"
        },
        "compute_id": {
            "description": "If the appliance don't have a default compute use this compute",
            "type": ["null", "string"]
        }
    },
    "additionalProperties": False,
    "required": ["x", "y"]
}
