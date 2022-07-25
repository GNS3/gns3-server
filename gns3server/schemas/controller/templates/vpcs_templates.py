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
from gns3server.schemas.compute.vpcs_nodes import ConsoleType

from pydantic import Field
from typing import Optional


class VPCSTemplate(TemplateBase):

    category: Optional[Category] = "guest"
    default_name_format: Optional[str] = "PC{0}"
    symbol: Optional[str] = "vpcs_guest"
    base_script_file: Optional[str] = Field("vpcs_base_config.txt", description="Script file")
    console_type: Optional[ConsoleType] = Field("telnet", description="Console type")
    console_auto_start: Optional[bool] = Field(
        False, description="Automatically start the console when the node has started"
    )


class VPCSTemplateUpdate(VPCSTemplate):

    pass
