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
from gns3server.schemas.compute.iou_nodes import ConsoleType

from pydantic import Field
from typing import Optional


class IOUTemplate(TemplateBase):

    category: Optional[Category] = "router"
    default_name_format: Optional[str] = "IOU{0}"
    symbol: Optional[str] = "multilayer_switch"
    path: str = Field(..., description="Path of IOU executable")
    ethernet_adapters: Optional[int] = Field(2, description="Number of ethernet adapters")
    serial_adapters: Optional[int] = Field(2, description="Number of serial adapters")
    ram: Optional[int] = Field(256, description="Amount of RAM in MB")
    nvram: Optional[int] = Field(128, description="Amount of NVRAM in KB")
    use_default_iou_values: Optional[bool] = Field(True, description="Use default IOU values")
    startup_config: Optional[str] = Field("iou_l3_base_startup-config.txt", description="Startup-config of IOU")
    private_config: Optional[str] = Field("", description="Private-config of IOU")
    l1_keepalives: Optional[bool] = Field(False, description="Always keep up Ethernet interface (does not always work)")
    console_type: Optional[ConsoleType] = Field("telnet", description="Console type")
    console_auto_start: Optional[bool] = Field(
        False, description="Automatically start the console when the node has started"
    )


class IOUTemplateUpdate(IOUTemplate):

    path: Optional[str] = Field(None, description="Path of IOU executable")
