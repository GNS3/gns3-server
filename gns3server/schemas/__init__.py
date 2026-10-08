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
from .common import ErrorMessage
from .config import ServerConfig
from .controller.appliances import Appliance, ApplianceVersion, ApplianceVersionV8
from .controller.computes import (
    AutoIdlePC,
    Compute,
    ComputeCreate,
    ComputeDockerImage,
    ComputeUpdate,
    ComputeVirtualBoxVM,
    ComputeVMwareVM,
)
from .controller.drawings import Drawing
from .controller.gns3vm import GNS3VM
from .controller.images import Image, ImageSyncJob, ImageSyncRequest, ImageType, ImageUpload

# Controller schemas
from .controller.links import (
    EthernetPortInfo,
    Link,
    LinkBatchResult,
    LinkCapture,
    LinkCreate,
    LinkFilterDefinition,
    LinkFilterParameter,
    LinkFilters,
    LinkFilterType,
    LinkUpdate,
    MarkerCreate,
    MarkerDefinitionCreate,
    MarkerUpdate,
    UDPPortInfo,
)
from .controller.nodes import Node, NodeBatchResult, NodeCapture, NodeCreate, NodeDuplicate, NodeUpdate
from .controller.projects import (
    NodeFile,
    Project,
    ProjectCompression,
    ProjectCreate,
    ProjectDuplicate,
    ProjectFile,
    ProjectUpdate,
)
from .controller.templates import Template, TemplateCreate, TemplateUpdate, TemplateUsage
from .controller.users import (
    Credentials,
    LoggedInUserUpdate,
    User,
    UserCreate,
    UserGroup,
    UserGroupCreate,
    UserGroupUpdate,
    UserUpdate,
)
from .version import Version

# Conditionally import AI-related schemas
try:
    from .controller.chat import (
        ChatRequest,
        ChatResponse,
        ChatSession,
        ConversationHistory,
        OpenAIMessage,
        OpenAIToolCall,
        RenameSession,
    )
    from .controller.llm_model_configs import (
        LLMModelConfigCreate,
        LLMModelConfigData,
        LLMModelConfigInheritedResponse,
        LLMModelConfigListResponse,
        LLMModelConfigResponse,
        LLMModelConfigUpdate,
        LLMModelConfigWithSource,
    )
except ImportError:
    # AI schemas are not available (should not happen as they don't depend on external libs)
    pass

from .compute.atm_switch_nodes import ATMSwitch, ATMSwitchCreate, ATMSwitchUpdate
from .compute.cloud_nodes import Cloud, CloudCreate, CloudUpdate
from .compute.docker_nodes import Docker, DockerCreate, DockerUpdate
from .compute.dynamips_nodes import Dynamips, DynamipsCreate, DynamipsUpdate
from .compute.ethernet_hub_nodes import EthernetHub, EthernetHubCreate, EthernetHubUpdate
from .compute.ethernet_switch_nodes import EthernetSwitch, EthernetSwitchCreate, EthernetSwitchUpdate
from .compute.frame_relay_switch_nodes import FrameRelaySwitch, FrameRelaySwitchCreate, FrameRelaySwitchUpdate
from .compute.iou_nodes import IOU, IOUCreate, IOUStart, IOUUpdate
from .compute.nat_nodes import NAT, NATCreate, NATUpdate

# Compute schemas
from .compute.nios import TAPNIO, UDPNIO, BatchNIOCreate, BatchNIOEntry, EthernetNIO, MarkerRebuild, MarkerToggle
from .compute.qemu_nodes import Qemu, QemuCreate, QemuUpdate
from .compute.virtualbox_nodes import VirtualBox, VirtualBoxCreate, VirtualBoxUpdate
from .compute.vmware_nodes import VMware, VMwareCreate, VMwareUpdate
from .compute.vpcs_nodes import VPCS, VPCSCreate, VPCSUpdate
from .controller.capabilities import Capabilities
from .controller.iou_license import IOULicense
from .controller.netmiko import NetmikoDeviceType, NetmikoDeviceTypeList
from .controller.notifications import Notification, NotificationAction
from .controller.pools import Resource, ResourceCreate, ResourcePool, ResourcePoolCreate, ResourcePoolUpdate
from .controller.rbac import ACE, ACECreate, ACEUpdate, Privilege, Role, RoleCreate, RoleUpdate
from .controller.settings import SettingsResponse, SettingsUpdate, SettingsUpdateResponse
from .controller.snapshots import Snapshot, SnapshotCreate
from .controller.templates.cloud_templates import CloudTemplate, CloudTemplateUpdate
from .controller.templates.docker_templates import DockerTemplate, DockerTemplateUpdate
from .controller.templates.dynamips_templates import (
    C1700DynamipsTemplate,
    C1700DynamipsTemplateUpdate,
    C2600DynamipsTemplate,
    C2600DynamipsTemplateUpdate,
    C2691DynamipsTemplate,
    C2691DynamipsTemplateUpdate,
    C3600DynamipsTemplate,
    C3600DynamipsTemplateUpdate,
    C3725DynamipsTemplate,
    C3725DynamipsTemplateUpdate,
    C3745DynamipsTemplate,
    C3745DynamipsTemplateUpdate,
    C7200DynamipsTemplate,
    C7200DynamipsTemplateUpdate,
    DynamipsTemplate,
)
from .controller.templates.ethernet_hub_templates import EthernetHubTemplate, EthernetHubTemplateUpdate
from .controller.templates.ethernet_switch_templates import EthernetSwitchTemplate, EthernetSwitchTemplateUpdate
from .controller.templates.iou_templates import IOUTemplate, IOUTemplateUpdate
from .controller.templates.qemu_templates import QemuTemplate, QemuTemplateUpdate
from .controller.templates.virtualbox_templates import VirtualBoxTemplate, VirtualBoxTemplateUpdate
from .controller.templates.vmware_templates import VMwareTemplate, VMwareTemplateUpdate

# Controller template schemas
from .controller.templates.vpcs_templates import VPCSTemplate, VPCSTemplateUpdate
from .controller.tokens import ApiKeyCreate, RefreshTokenRequest, Token

# Schemas for both controller and compute
from .qemu_disk_image import QemuDiskImageCreate, QemuDiskImageFormat, QemuDiskImageUpdate

__all__ = [
    "ACE",
    "GNS3VM",
    "IOU",
    "NAT",
    "TAPNIO",
    "UDPNIO",
    "VPCS",
    "ACECreate",
    "ACEUpdate",
    "ATMSwitch",
    "ATMSwitchCreate",
    "ATMSwitchUpdate",
    "ApiKeyCreate",
    "Appliance",
    "ApplianceVersion",
    "ApplianceVersionV8",
    "AutoIdlePC",
    "BatchNIOCreate",
    "BatchNIOEntry",
    "C1700DynamipsTemplate",
    "C1700DynamipsTemplateUpdate",
    "C2600DynamipsTemplate",
    "C2600DynamipsTemplateUpdate",
    "C2691DynamipsTemplate",
    "C2691DynamipsTemplateUpdate",
    "C3600DynamipsTemplate",
    "C3600DynamipsTemplateUpdate",
    "C3725DynamipsTemplate",
    "C3725DynamipsTemplateUpdate",
    "C3745DynamipsTemplate",
    "C3745DynamipsTemplateUpdate",
    "C7200DynamipsTemplate",
    "C7200DynamipsTemplateUpdate",
    "Capabilities",
    "ChatRequest",
    "ChatResponse",
    "ChatSession",
    "Cloud",
    "CloudCreate",
    "CloudTemplate",
    "CloudTemplateUpdate",
    "CloudUpdate",
    "Compute",
    "ComputeCreate",
    "ComputeDockerImage",
    "ComputeUpdate",
    "ComputeVMwareVM",
    "ComputeVirtualBoxVM",
    "ConversationHistory",
    "Credentials",
    "Docker",
    "DockerCreate",
    "DockerTemplate",
    "DockerTemplateUpdate",
    "DockerUpdate",
    "Drawing",
    "Dynamips",
    "DynamipsCreate",
    "DynamipsTemplate",
    "DynamipsUpdate",
    "ErrorMessage",
    "EthernetHub",
    "EthernetHubCreate",
    "EthernetHubTemplate",
    "EthernetHubTemplateUpdate",
    "EthernetHubUpdate",
    "EthernetNIO",
    "EthernetPortInfo",
    "EthernetSwitch",
    "EthernetSwitchCreate",
    "EthernetSwitchTemplate",
    "EthernetSwitchTemplateUpdate",
    "EthernetSwitchUpdate",
    "FrameRelaySwitch",
    "FrameRelaySwitchCreate",
    "FrameRelaySwitchUpdate",
    "IOUCreate",
    "IOULicense",
    "IOUStart",
    "IOUTemplate",
    "IOUTemplateUpdate",
    "IOUUpdate",
    "Image",
    "ImageSyncJob",
    "ImageSyncRequest",
    "ImageType",
    "ImageUpload",
    "LLMModelConfigCreate",
    "LLMModelConfigData",
    "LLMModelConfigInheritedResponse",
    "LLMModelConfigListResponse",
    "LLMModelConfigResponse",
    "LLMModelConfigUpdate",
    "LLMModelConfigWithSource",
    "Link",
    "LinkBatchResult",
    "LinkCapture",
    "LinkCreate",
    "LinkFilterDefinition",
    "LinkFilterParameter",
    "LinkFilterType",
    "LinkFilters",
    "LinkUpdate",
    "LoggedInUserUpdate",
    "MarkerCreate",
    "MarkerDefinitionCreate",
    "MarkerRebuild",
    "MarkerToggle",
    "MarkerUpdate",
    "NATCreate",
    "NATUpdate",
    "NetmikoDeviceType",
    "NetmikoDeviceTypeList",
    "Node",
    "NodeBatchResult",
    "NodeCapture",
    "NodeCreate",
    "NodeDuplicate",
    "NodeFile",
    "NodeUpdate",
    "Notification",
    "NotificationAction",
    "OpenAIMessage",
    "OpenAIToolCall",
    "Privilege",
    "Project",
    "ProjectCompression",
    "ProjectCreate",
    "ProjectDuplicate",
    "ProjectFile",
    "ProjectUpdate",
    "Qemu",
    "QemuCreate",
    "QemuDiskImageCreate",
    "QemuDiskImageFormat",
    "QemuDiskImageUpdate",
    "QemuTemplate",
    "QemuTemplateUpdate",
    "QemuUpdate",
    "RefreshTokenRequest",
    "RenameSession",
    "Resource",
    "ResourceCreate",
    "ResourcePool",
    "ResourcePoolCreate",
    "ResourcePoolUpdate",
    "Role",
    "RoleCreate",
    "RoleUpdate",
    "ServerConfig",
    "SettingsResponse",
    "SettingsUpdate",
    "SettingsUpdateResponse",
    "Snapshot",
    "SnapshotCreate",
    "Template",
    "TemplateCreate",
    "TemplateUpdate",
    "TemplateUsage",
    "Token",
    "UDPPortInfo",
    "User",
    "UserCreate",
    "UserGroup",
    "UserGroupCreate",
    "UserGroupUpdate",
    "UserUpdate",
    "VMware",
    "VMwareCreate",
    "VMwareTemplate",
    "VMwareTemplateUpdate",
    "VMwareUpdate",
    "VPCSCreate",
    "VPCSTemplate",
    "VPCSTemplateUpdate",
    "VPCSUpdate",
    "Version",
    "VirtualBox",
    "VirtualBoxCreate",
    "VirtualBoxTemplate",
    "VirtualBoxTemplateUpdate",
    "VirtualBoxUpdate",
]
