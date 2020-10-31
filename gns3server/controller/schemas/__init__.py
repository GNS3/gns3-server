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
