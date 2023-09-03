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

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from uuid import UUID

from ..common import NodeStatus, CustomAdapter


class VirtualBoxConsoleType(str, Enum):
    """
    Supported console types.
    """

    telnet = "telnet"
    none = "none"


class VirtualBoxOnCloseAction(str, Enum):
    """
    Supported actions when closing VirtualBox VM.
    """

    power_off = "power_off"
    shutdown_signal = "shutdown_signal"
    save_vm_state = "save_vm_state"


class VirtualBoxAdapterType(str, Enum):

    pcnet_pci_ii = ("PCnet-PCI II (Am79C970A)",)
    pcnet_fast_iii = ("PCNet-FAST III (Am79C973)",)
    intel_pro_1000_mt_desktop = ("Intel PRO/1000 MT Desktop (82540EM)",)
    intel_pro_1000_t_server = ("Intel PRO/1000 T Server (82543GC)",)
    intel_pro_1000_mt_server = ("Intel PRO/1000 MT Server (82545EM)",)
    paravirtualized_network = "Paravirtualized Network (virtio-net)"


class VirtualBoxBase(BaseModel):
    """
    Common VirtualBox node properties.
    """

    name: str
    vmname: str = Field(..., description="VirtualBox VM name (in VirtualBox itself)")
    node_id: Optional[UUID] = None
    linked_clone: Optional[bool] = Field(None, description="Whether the VM is a linked clone or not")
    usage: Optional[str] = Field(None, description="How to use the node")
    # 36 adapters is the maximum given by the ICH9 chipset in VirtualBox
    adapters: Optional[int] = Field(None, ge=0, le=36, description="Number of adapters")
    adapter_type: Optional[VirtualBoxAdapterType] = Field(None, description="VirtualBox adapter type")
    use_any_adapter: Optional[bool] = Field(None, description="Allow GNS3 to use any VirtualBox adapter")
    console: Optional[int] = Field(None, gt=0, le=65535, description="Console TCP port")
    console_type: Optional[VirtualBoxConsoleType] = Field(None, description="Console type")
    ram: Optional[int] = Field(None, ge=0, le=65535, description="Amount of RAM in MB")
    headless: Optional[bool] = Field(None, description="Headless mode")
    on_close: Optional[VirtualBoxOnCloseAction] = Field(None, description="Action to execute on the VM is closed")
    custom_adapters: Optional[List[CustomAdapter]] = Field(None, description="Custom adapters")


class VirtualBoxCreate(VirtualBoxBase):
    """
    Properties to create a VirtualBox node.
    """

    pass


class VirtualBoxUpdate(VirtualBoxBase):
    """
    Properties to update a VirtualBox node.
    """

    name: Optional[str] = None
    vmname: Optional[str] = None


class VirtualBox(VirtualBoxBase):

    project_id: UUID = Field(..., description="Project ID")
    node_directory: Optional[str] = Field(None, description="Path to the node working directory (read only)")
    status: NodeStatus = Field(..., description="Container status (read only)")
