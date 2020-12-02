# -*- coding: utf-8 -*-
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


from .iou_license import IOULicense
from .links import Link
from .common import ErrorMessage
from .version import Version
from .computes import ComputeCreate, ComputeUpdate, AutoIdlePC, Compute
from .templates import TemplateCreate, TemplateUpdate, TemplateUsage, Template
from .drawings import Drawing
from .gns3vm import GNS3VM
from .nodes import NodeUpdate, NodeDuplicate, NodeCapture, Node
from .projects import ProjectCreate, ProjectUpdate, ProjectDuplicate, Project, ProjectFile
from .users import UserCreate, UserUpdate, User
from .tokens import Token
from .snapshots import SnapshotCreate, Snapshot
from .capabilities import Capabilities
from .nios import UDPNIO, TAPNIO, EthernetNIO
from .atm_switch_nodes import ATMSwitchCreate, ATMSwitchUpdate, ATMSwitch
from .cloud_nodes import CloudCreate, CloudUpdate, Cloud
from .docker_nodes import DockerCreate, DockerUpdate, Docker
from .dynamips_nodes import DynamipsCreate, DynamipsUpdate, Dynamips
from .ethernet_hub_nodes import EthernetHubCreate, EthernetHubUpdate, EthernetHub
from .ethernet_switch_nodes import EthernetSwitchCreate, EthernetSwitchUpdate, EthernetSwitch
from .frame_relay_switch_nodes import FrameRelaySwitchCreate, FrameRelaySwitchUpdate, FrameRelaySwitch
from .qemu_nodes import QemuCreate, QemuUpdate, QemuImageCreate, QemuImageUpdate, QemuDiskResize, Qemu
from .iou_nodes import IOUCreate, IOUUpdate, IOUStart, IOU
from .nat_nodes import NATCreate, NATUpdate, NAT
from .vpcs_nodes import VPCSCreate, VPCSUpdate, VPCS
from .vmware_nodes import VMwareCreate, VMwareUpdate, VMware
from .virtualbox_nodes import VirtualBoxCreate, VirtualBoxUpdate, VirtualBox

from .vpcs_templates import VPCSTemplate
from .cloud_templates import CloudTemplate
from .iou_templates import IOUTemplate
from .docker_templates import DockerTemplate
from .ethernet_hub_templates import EthernetHubTemplate
from .ethernet_switch_templates import EthernetSwitchTemplate
from .virtualbox_templates import VirtualBoxTemplate
from .vmware_templates import VMwareTemplate
from .qemu_templates import QemuTemplate
from .dynamips_templates import (
    DynamipsTemplate,
    C1700DynamipsTemplate,
    C2600DynamipsTemplate,
    C2691DynamipsTemplate,
    C3600DynamipsTemplate,
    C3725DynamipsTemplate,
    C3745DynamipsTemplate,
    C7200DynamipsTemplate
)
