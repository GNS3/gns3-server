#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import sys
import os

from .capabilities_handler import CapabilitiesHandler
from .network_handler import NetworkHandler
from .project_handler import ProjectHandler
from .dynamips_vm_handler import DynamipsVMHandler
from .qemu_handler import QEMUHandler
from .virtualbox_handler import VirtualBoxHandler
from .vpcs_handler import VPCSHandler
from .vmware_handler import VMwareHandler
from .server_handler import ServerHandler
from .notification_handler import NotificationHandler
from .cloud_handler import CloudHandler
from .nat_handler import NatHandler
from .ethernet_hub_handler import EthernetHubHandler
from .ethernet_switch_handler import EthernetSwitchHandler
from .frame_relay_switch_handler import FrameRelaySwitchHandler
from .atm_switch_handler import ATMSwitchHandler

if sys.platform.startswith("linux") or hasattr(sys, "_called_from_test") or os.environ.get("PYTEST_BUILD_DOCUMENTATION") == "1":
    # IOU runs only on Linux but test suite works on UNIX platform
    if not sys.platform.startswith("win"):
        from .iou_handler import IOUHandler
        from .docker_handler import DockerHandler
