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
from gns3server.schemas.compute.cloud_nodes import (
    EthernetPort,
    TAPPort,
    UDPPort,
    CloudConsoleType
)

from pydantic import Field
from typing import Optional, Union, List


class CloudTemplate(TemplateBase):

    category: Optional[Category] = "guest"
    default_name_format: Optional[str] = "Cloud{0}"
    symbol: Optional[str] = "cloud"
    ports_mapping: List[Union[EthernetPort, TAPPort, UDPPort]] = Field(default_factory=list)
    remote_console_host: Optional[str] = Field("127.0.0.1", description="Remote console host or IP")
    remote_console_port: Optional[int] = Field(23, gt=0, le=65535, description="Remote console TCP port")
    remote_console_type: Optional[CloudConsoleType] = Field("none", description="Remote console type")
    remote_console_http_path: Optional[str] = Field("/", description="Path of the remote web interface")


class CloudTemplateUpdate(CloudTemplate):

    pass
