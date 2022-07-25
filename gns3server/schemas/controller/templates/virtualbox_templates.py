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
from gns3server.schemas.compute.virtualbox_nodes import (
    VirtualBoxConsoleType,
    VirtualBoxAdapterType,
    VirtualBoxOnCloseAction,
    CustomAdapter
)

from pydantic import Field
from typing import Optional, List


class VirtualBoxTemplate(TemplateBase):

    category: Optional[Category] = "guest"
    default_name_format: Optional[str] = "{name}-{0}"
    symbol: Optional[str] = "vbox_guest"
    vmname: str = Field(..., description="VirtualBox VM name (in VirtualBox itself)")
    ram: Optional[int] = Field(256, gt=0, description="Amount of RAM in MB")
    linked_clone: Optional[bool] = Field(False, description="Whether the VM is a linked clone or not")
    adapters: Optional[int] = Field(
        1, ge=0, le=36, description="Number of adapters"
    )  # 36 is the maximum given by the ICH9 chipset in VirtualBox
    use_any_adapter: Optional[bool] = Field(False, description="Allow GNS3 to use any VirtualBox adapter")
    adapter_type: Optional[VirtualBoxAdapterType] = Field(
        "Intel PRO/1000 MT Desktop (82540EM)", description="VirtualBox adapter type"
    )
    first_port_name: Optional[str] = Field("", description="Optional name of the first networking port example: eth0")
    port_name_format: Optional[str] = Field(
        "Ethernet{0}", description="Optional formatting of the networking port example: eth{0}"
    )
    port_segment_size: Optional[int] = Field(
        0,
        description="Optional port segment size. A port segment is a block of port. For example Ethernet0/0 Ethernet0/1 is the module 0 with a port segment size of 2",
    )
    headless: Optional[bool] = Field(False, description="Headless mode")
    on_close: Optional[VirtualBoxOnCloseAction] = Field(
        "power_off", description="Action to execute on the VM is closed"
    )
    console_type: Optional[VirtualBoxConsoleType] = Field("none", description="Console type")
    console_auto_start: Optional[bool] = Field(
        False, description="Automatically start the console when the node has started"
    )
    custom_adapters: Optional[List[CustomAdapter]] = Field(default_factory=list, description="Custom adapters")


class VirtualBoxTemplateUpdate(VirtualBoxTemplate):

    vmname: Optional[str] = Field(None, description="VirtualBox VM name (in VirtualBox itself)")
