#!/usr/bin/env python
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


from sqlalchemy import Boolean, Column, String, Integer, Float, ForeignKey, PickleType
from sqlalchemy.orm import relationship

from .base import BaseTable, generate_uuid, GUID
from .images import image_template_map


class Template(BaseTable):

    __tablename__ = "templates"

    template_id = Column(GUID, primary_key=True, default=generate_uuid)
    name = Column(String, index=True)
    version = Column(String)
    category = Column(String)
    default_name_format = Column(String)
    symbol = Column(String)
    builtin = Column(Boolean, default=False)
    usage = Column(String)
    template_type = Column(String)
    compute_id = Column(String)
    images = relationship("Image", secondary=image_template_map, back_populates="templates")

    __mapper_args__ = {
        "polymorphic_identity": "templates",
        "polymorphic_on": template_type,
    }


class CloudTemplate(Template):

    __tablename__ = "cloud_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    ports_mapping = Column(PickleType)
    remote_console_host = Column(String)
    remote_console_port = Column(Integer)
    remote_console_type = Column(String)
    remote_console_http_path = Column(String)

    __mapper_args__ = {"polymorphic_identity": "cloud", "polymorphic_load": "selectin"}


class DockerTemplate(Template):

    __tablename__ = "docker_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    image = Column(String)
    adapters = Column(Integer)
    start_command = Column(String)
    environment = Column(String)
    console_type = Column(String)
    aux_type = Column(String)
    console_auto_start = Column(Boolean)
    console_http_port = Column(Integer)
    console_http_path = Column(String)
    console_resolution = Column(String)
    extra_hosts = Column(String)
    extra_volumes = Column(PickleType)
    memory = Column(Integer)
    cpus = Column(Float)
    custom_adapters = Column(PickleType)

    __mapper_args__ = {"polymorphic_identity": "docker", "polymorphic_load": "selectin"}


class DynamipsTemplate(Template):

    __tablename__ = "dynamips_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    platform = Column(String)
    chassis = Column(String)
    image = Column(String)
    exec_area = Column(Integer)
    mmap = Column(Boolean)
    mac_addr = Column(String)
    system_id = Column(String)
    startup_config = Column(String)
    private_config = Column(String)
    idlepc = Column(String)
    idlemax = Column(Integer)
    idlesleep = Column(Integer)
    disk0 = Column(Integer)
    disk1 = Column(Integer)
    auto_delete_disks = Column(Boolean)
    console_type = Column(String)
    console_auto_start = Column(Boolean)
    aux_type = Column(String)
    ram = Column(Integer)
    nvram = Column(Integer)
    npe = Column(String)
    midplane = Column(String)
    sparsemem = Column(Boolean)
    iomem = Column(Integer)
    slot0 = Column(String)
    slot1 = Column(String)
    slot2 = Column(String)
    slot3 = Column(String)
    slot4 = Column(String)
    slot5 = Column(String)
    slot6 = Column(String)
    wic0 = Column(String)
    wic1 = Column(String)
    wic2 = Column(String)

    __mapper_args__ = {"polymorphic_identity": "dynamips", "polymorphic_load": "selectin"}


class EthernetHubTemplate(Template):

    __tablename__ = "ethernet_hub_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    ports_mapping = Column(PickleType)

    __mapper_args__ = {"polymorphic_identity": "ethernet_hub", "polymorphic_load": "selectin"}


class EthernetSwitchTemplate(Template):

    __tablename__ = "ethernet_switch_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    ports_mapping = Column(PickleType)
    console_type = Column(String)

    __mapper_args__ = {"polymorphic_identity": "ethernet_switch", "polymorphic_load": "selectin"}


class IOUTemplate(Template):

    __tablename__ = "iou_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    path = Column(String)
    ethernet_adapters = Column(Integer)
    serial_adapters = Column(Integer)
    ram = Column(Integer)
    nvram = Column(Integer)
    use_default_iou_values = Column(Boolean)
    startup_config = Column(String)
    private_config = Column(String)
    l1_keepalives = Column(Boolean)
    console_type = Column(String)
    console_auto_start = Column(Boolean)

    __mapper_args__ = {"polymorphic_identity": "iou", "polymorphic_load": "selectin"}


class QemuTemplate(Template):

    __tablename__ = "qemu_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    qemu_path = Column(String)
    platform = Column(String)
    linked_clone = Column(Boolean)
    ram = Column(Integer)
    cpus = Column(Integer)
    maxcpus = Column(Integer)
    adapters = Column(Integer)
    adapter_type = Column(String)
    mac_address = Column(String)
    first_port_name = Column(String)
    port_name_format = Column(String)
    port_segment_size = Column(Integer)
    console_type = Column(String)
    console_auto_start = Column(Boolean)
    aux_type = Column(String)
    boot_priority = Column(String)
    hda_disk_image = Column(String)
    hda_disk_interface = Column(String)
    hdb_disk_image = Column(String)
    hdb_disk_interface = Column(String)
    hdc_disk_image = Column(String)
    hdc_disk_interface = Column(String)
    hdd_disk_image = Column(String)
    hdd_disk_interface = Column(String)
    cdrom_image = Column(String)
    initrd = Column(String)
    kernel_image = Column(String)
    bios_image = Column(String)
    kernel_command_line = Column(String)
    replicate_network_connection_state = Column(Boolean)
    create_config_disk = Column(Boolean)
    tpm = Column(Boolean)
    uefi = Column(Boolean)
    on_close = Column(String)
    cpu_throttling = Column(Integer)
    process_priority = Column(String)
    options = Column(String)
    custom_adapters = Column(PickleType)

    __mapper_args__ = {"polymorphic_identity": "qemu", "polymorphic_load": "selectin"}


class VirtualBoxTemplate(Template):

    __tablename__ = "virtualbox_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    vmname = Column(String)
    ram = Column(Integer)
    linked_clone = Column(Boolean)
    adapters = Column(Integer)
    use_any_adapter = Column(Boolean)
    adapter_type = Column(String)
    first_port_name = Column(String)
    port_name_format = Column(String)
    port_segment_size = Column(Integer)
    headless = Column(Boolean)
    on_close = Column(String)
    console_type = Column(String)
    console_auto_start = Column(Boolean)
    custom_adapters = Column(PickleType)

    __mapper_args__ = {"polymorphic_identity": "virtualbox", "polymorphic_load": "selectin"}


class VMwareTemplate(Template):

    __tablename__ = "vmware_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    vmx_path = Column(String)
    linked_clone = Column(Boolean)
    first_port_name = Column(String)
    port_name_format = Column(String)
    port_segment_size = Column(Integer)
    adapters = Column(Integer)
    adapter_type = Column(String)
    use_any_adapter = Column(Boolean)
    headless = Column(Boolean)
    on_close = Column(String)
    console_type = Column(String)
    console_auto_start = Column(Boolean)
    custom_adapters = Column(PickleType)

    __mapper_args__ = {"polymorphic_identity": "vmware", "polymorphic_load": "selectin"}


class VPCSTemplate(Template):

    __tablename__ = "vpcs_templates"

    template_id = Column(GUID, ForeignKey("templates.template_id", ondelete="CASCADE"), primary_key=True)
    base_script_file = Column(String)
    console_type = Column(String)
    console_auto_start = Column(Boolean, default=False)

    __mapper_args__ = {"polymorphic_identity": "vpcs", "polymorphic_load": "selectin"}
