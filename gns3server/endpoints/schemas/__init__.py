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


from .version import Version
from .iou_license import IOULicense
from .links import Link
from .common import ErrorMessage
from .computes import ComputeCreate, ComputeUpdate, Compute, AutoIdlePC
from .nodes import NodeUpdate, NodeDuplicate, NodeCapture, Node
from .projects import ProjectCreate, ProjectUpdate, ProjectDuplicate, Project, ProjectFile
from .snapshots import SnapshotCreate, Snapshot
from .templates import TemplateCreate, TemplateUpdate, TemplateUsage, Template
from .capabilities import Capabilities
from .nios import UDPNIO, TAPNIO, EthernetNIO
from .atm_switch_nodes import ATMSwitchCreate, ATMSwitchUpdate, ATMSwitch
from .cloud_nodes import CloudCreate, CloudUpdate, Cloud
from .docker_nodes import DockerCreate, DockerUpdate, Docker
from .dynamips_nodes import DynamipsCreate, DynamipsUpdate, Dynamips
from .ethernet_hub_nodes import EthernetHubCreate, EthernetHubUpdate, EthernetHub
from .ethernet_switch_nodes import EthernetSwitchCreate, EthernetSwitchUpdate, EthernetSwitch
from .frame_relay_switch_nodes import FrameRelaySwitchCreate, FrameRelaySwitchUpdate, FrameRelaySwitch
from .iou_nodes import IOUCreate, IOUUpdate, IOUStart, IOU
from .nat_nodes import NATCreate, NATUpdate, NAT
from .qemu_nodes import QemuCreate, QemuUpdate, Qemu, QemuDiskResize, QemuImageCreate, QemuImageUpdate
from .virtualbox_nodes import VirtualBoxCreate, VirtualBoxUpdate, VirtualBox
from .vmware_nodes import VMwareCreate, VMwareUpdate, VMware
from .vpcs_nodes import VPCSCreate, VPCSUpdate, VPCS
from .vpcs_templates import VPCSTemplateCreate, VPCSTemplateUpdate, VPCSTemplate
from .cloud_templates import CloudTemplateCreate, CloudTemplateUpdate, CloudTemplate
from .iou_templates import IOUTemplateCreate, IOUTemplateUpdate, IOUTemplate
