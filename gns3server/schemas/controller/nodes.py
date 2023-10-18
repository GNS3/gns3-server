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

from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Union, Any
from enum import Enum
from uuid import UUID, uuid4

from .labels import Label
from ..common import ConsoleType, NodeStatus, CustomAdapter


class NodeType(str, Enum):
    """
    Supported node types.
    """

    cloud = "cloud"
    nat = "nat"
    ethernet_hub = "ethernet_hub"
    ethernet_switch = "ethernet_switch"
    frame_relay_switch = "frame_relay_switch"
    atm_switch = "atm_switch"
    docker = "docker"
    dynamips = "dynamips"
    vpcs = "vpcs"
    virtualbox = "virtualbox"
    vmware = "vmware"
    iou = "iou"
    qemu = "qemu"


class Image(BaseModel):
    """
    Image data.
    """

    filename: str
    path: str
    md5sum: Optional[str] = None
    filesize: Optional[int] = None


class LinkType(str, Enum):
    """
    Supported link types.
    """

    ethernet = "ethernet"
    serial = "serial"


class DataLinkType(str, Enum):
    """
    Supported data link types.
    """

    atm = "DLT_ATM_RFC1483"
    ethernet = "DLT_EN10MB"
    frame_relay = "DLT_FRELAY"
    cisco_hdlc = "DLT_C_HDLC"
    ppp = "DLT_PPP_SERIAL"


class NodeCapture(BaseModel):
    """
    Node capture data.
    """

    capture_file_name: str
    data_link_type: Optional[DataLinkType] = None


class NodePort(BaseModel):
    """
    Node port data.
    """

    name: str = Field(..., description="Port name")
    short_name: str = Field(..., description="Port name")
    adapter_number: int = Field(..., description="Adapter slot")
    adapter_type: Optional[str] = Field(None, description="Adapter type")
    port_number: int = Field(..., description="Port slot")
    link_type: LinkType = Field(..., description="Type of link")
    data_link_types: dict = Field(..., description="Available PCAP types for capture")
    mac_address: Union[str, None] = Field(None, pattern="^([0-9a-fA-F]{2}[:]){5}([0-9a-fA-F]{2})$")


class NodeBase(BaseModel):
    """
    Node data.
    """

    compute_id: Union[UUID, str]
    name: str
    node_type: NodeType

    node_id: Optional[UUID] = None

    console: Optional[int] = Field(None, gt=0, le=65535, description="Console TCP port")

    console_type: Optional[ConsoleType] = None
    console_auto_start: Optional[bool] = Field(
        False, description="Automatically start the console when the node has started"
    )
    aux: Optional[int] = Field(None, gt=0, le=65535, description="Auxiliary console TCP port")
    aux_type: Optional[ConsoleType] = None
    properties: Optional[dict] = Field(default_factory=dict, description="Properties specific to an emulator")

    label: Optional[Label] = None
    symbol: Optional[str] = None

    x: Optional[int] = 0
    y: Optional[int] = 0
    z: Optional[int] = 1
    locked: Optional[bool] = Field(False, description="Whether the element locked or not")
    port_name_format: Optional[str] = Field(
        None, descript_port_name_formation="Formatting for port name {0} will be replace by port number"
    )
    port_segment_size: Optional[int] = Field(None, description="Size of the port segment")
    first_port_name: Optional[str] = Field(None, description="Name of the first port")
    custom_adapters: Optional[List[CustomAdapter]] = None


class NodeCreate(NodeBase):

    node_id: UUID = Field(default_factory=uuid4)


class NodeUpdate(NodeBase):
    """
    Data to update a node.
    """

    compute_id: Optional[Union[UUID, str]] = None
    name: Optional[str] = None
    node_type: Optional[NodeType] = None


class Node(NodeBase):

    template_id: Optional[UUID] = Field(None,
                                        description="Template UUID from which the node has been created. Read only")
    project_id: Optional[UUID] = None
    node_directory: Optional[str] = Field(None, description="Working directory of the node. Read only")
    status: Optional[NodeStatus] = Field(None, description="Node status. Read only")
    command_line: Optional[str] = Field(None, description="Command line use to start the node. Read only")
    width: Optional[int] = Field(None, description="Width of the node. Read only")
    height: Optional[int] = Field(None, description="Height of the node. Read only")
    ports: Optional[List[NodePort]] = Field(None, description="List of node ports. Read only")
    console_host: Optional[str] = Field(
        None,
        description="Console host. Warning if the host is 0.0.0.0 or :: (listen on all interfaces) you need to use the same address you use to connect to the controller",
    )


class NodeDuplicate(BaseModel):
    """
    Data to duplicate a node.
    """

    x: int
    y: int
    z: Optional[int] = 0
