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


from . import Category, TemplateBase
from gns3server.schemas.compute.qemu_nodes import (
    QemuConsoleType,
    QemuPlatform,
    QemuAdapterType,
    QemuOnCloseAction,
    QemuBootPriority,
    QemuDiskInterfaceType,
    QemuProcessPriority,
    CustomAdapter,
)

from pydantic import Field
from typing import Optional, List


class QemuTemplate(TemplateBase):

    category: Optional[Category] = "guest"
    default_name_format: Optional[str] = "{name}-{0}"
    symbol: Optional[str] = "qemu_guest"
    qemu_path: Optional[str] = Field("", description="Qemu executable path")
    platform: Optional[QemuPlatform] = Field("x86_64", description="Platform to emulate")
    linked_clone: Optional[bool] = Field(True, description="Whether the VM is a linked clone or not")
    ram: Optional[int] = Field(256, description="Amount of RAM in MB")
    cpus: Optional[int] = Field(1, ge=1, le=255, description="Number of vCPUs")
    maxcpus: Optional[int] = Field(1, ge=1, le=255, description="Maximum number of hotpluggable vCPUs")
    adapters: Optional[int] = Field(1, ge=0, le=275, description="Number of adapters")
    adapter_type: Optional[QemuAdapterType] = Field("e1000", description="QEMU adapter type")
    mac_address: Optional[str] = Field(
        "", description="QEMU MAC address", pattern="^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})$|^$"
    )
    first_port_name: Optional[str] = Field("", description="Optional name of the first networking port example: eth0")
    port_name_format: Optional[str] = Field(
        "Ethernet{0}", description="Optional formatting of the networking port example: eth{0}"
    )
    port_segment_size: Optional[int] = Field(
        0,
        description="Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2",
    )
    console_type: Optional[QemuConsoleType] = Field("telnet", description="Console type")
    console_auto_start: Optional[bool] = Field(
        False, description="Automatically start the console when the node has started"
    )
    aux_type: Optional[QemuConsoleType] = Field("none", description="Auxiliary console type")
    boot_priority: Optional[QemuBootPriority] = Field("c", description="QEMU boot priority")
    hda_disk_image: Optional[str] = Field("", description="QEMU hda disk image path")
    hda_disk_interface: Optional[QemuDiskInterfaceType] = Field("none", description="QEMU hda interface")
    hdb_disk_image: Optional[str] = Field("", description="QEMU hdb disk image path")
    hdb_disk_interface: Optional[QemuDiskInterfaceType] = Field("none", description="QEMU hdb interface")
    hdc_disk_image: Optional[str] = Field("", description="QEMU hdc disk image path")
    hdc_disk_interface: Optional[QemuDiskInterfaceType] = Field("none", description="QEMU hdc interface")
    hdd_disk_image: Optional[str] = Field("", description="QEMU hdd disk image path")
    hdd_disk_interface: Optional[QemuDiskInterfaceType] = Field("none", description="QEMU hdd interface")
    cdrom_image: Optional[str] = Field("", description="QEMU cdrom image path")
    initrd: Optional[str] = Field("", description="QEMU initrd path")
    kernel_image: Optional[str] = Field("", description="QEMU kernel image path")
    bios_image: Optional[str] = Field("", description="QEMU bios image path")
    kernel_command_line: Optional[str] = Field("", description="QEMU kernel command line")
    replicate_network_connection_state: Optional[bool] = Field(
        True, description="Replicate the network connection state for links in Qemu"
    )
    create_config_disk: Optional[bool] = Field(
        False, description="Automatically create a config disk on HDD disk interface (secondary slave)"
    )
    tpm: Optional[bool] = Field(False, description="Enable Trusted Platform Module (TPM)")
    uefi: Optional[bool] = Field(False, description="Enable UEFI boot mode")
    on_close: Optional[QemuOnCloseAction] = Field("power_off", description="Action to execute on the VM is closed")
    cpu_throttling: Optional[int] = Field(0, ge=0, le=800, description="Percentage of CPU allowed for QEMU")
    process_priority: Optional[QemuProcessPriority] = Field("normal", description="Process priority for QEMU")
    options: Optional[str] = Field("", description="Additional QEMU options")
    custom_adapters: Optional[List[CustomAdapter]] = Field(default_factory=list, description="Custom adapters")


class QemuTemplateUpdate(QemuTemplate):

    pass
