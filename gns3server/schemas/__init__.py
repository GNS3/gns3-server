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

# General schemas
from .config import ServerConfig
from .common import ErrorMessage
from .version import Version

# Controller schemas
from .controller.links import LinkCreate, LinkUpdate, Link
from .controller.computes import ComputeCreate, ComputeUpdate, AutoIdlePC, Compute
from .controller.templates import TemplateCreate, TemplateUpdate, TemplateUsage, Template
from .controller.images import Image, ImageType
from .controller.appliances import Appliance
from .controller.drawings import Drawing
from .controller.gns3vm import GNS3VM
from .controller.nodes import NodeCreate, NodeUpdate, NodeDuplicate, NodeCapture, Node
from .controller.projects import ProjectCreate, ProjectUpdate, ProjectDuplicate, Project, ProjectFile
from .controller.users import UserCreate, UserUpdate, LoggedInUserUpdate, User, Credentials, UserGroupCreate, UserGroupUpdate, UserGroup
from .controller.rbac import RoleCreate, RoleUpdate, Role, PermissionCreate, PermissionUpdate, Permission
from .controller.tokens import Token
from .controller.snapshots import SnapshotCreate, Snapshot
from .controller.iou_license import IOULicense
from .controller.capabilities import Capabilities

# Controller template schemas
from .controller.templates.vpcs_templates import VPCSTemplate
from .controller.templates.cloud_templates import CloudTemplate
from .controller.templates.iou_templates import IOUTemplate
from .controller.templates.docker_templates import DockerTemplate
from .controller.templates.ethernet_hub_templates import EthernetHubTemplate
from .controller.templates.ethernet_switch_templates import EthernetSwitchTemplate
from .controller.templates.virtualbox_templates import VirtualBoxTemplate
from .controller.templates.vmware_templates import VMwareTemplate
from .controller.templates.qemu_templates import QemuTemplate
from .controller.templates.dynamips_templates import (
    DynamipsTemplate,
    C1700DynamipsTemplate,
    C2600DynamipsTemplate,
    C2691DynamipsTemplate,
    C3600DynamipsTemplate,
    C3725DynamipsTemplate,
    C3745DynamipsTemplate,
    C7200DynamipsTemplate,
)

# Compute schemas
from .compute.nios import UDPNIO, TAPNIO, EthernetNIO
from .compute.atm_switch_nodes import ATMSwitchCreate, ATMSwitchUpdate, ATMSwitch
from .compute.cloud_nodes import CloudCreate, CloudUpdate, Cloud
from .compute.docker_nodes import DockerCreate, DockerUpdate, Docker
from .compute.dynamips_nodes import DynamipsCreate, DynamipsUpdate, Dynamips
from .compute.ethernet_hub_nodes import EthernetHubCreate, EthernetHubUpdate, EthernetHub
from .compute.ethernet_switch_nodes import EthernetSwitchCreate, EthernetSwitchUpdate, EthernetSwitch
from .compute.frame_relay_switch_nodes import FrameRelaySwitchCreate, FrameRelaySwitchUpdate, FrameRelaySwitch
from .compute.qemu_nodes import QemuCreate, QemuUpdate, QemuImageCreate, QemuImageUpdate, QemuDiskResize, Qemu
from .compute.iou_nodes import IOUCreate, IOUUpdate, IOUStart, IOU
from .compute.nat_nodes import NATCreate, NATUpdate, NAT
from .compute.vpcs_nodes import VPCSCreate, VPCSUpdate, VPCS
from .compute.vmware_nodes import VMwareCreate, VMwareUpdate, VMware
from .compute.virtualbox_nodes import VirtualBoxCreate, VirtualBoxUpdate, VirtualBox
