# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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


from .dynamips_error import DynamipsError
from .nodes.c1700 import C1700
from .nodes.c2600 import C2600
from .nodes.c2691 import C2691
from .nodes.c3600 import C3600
from .nodes.c3725 import C3725
from .nodes.c3745 import C3745
from .nodes.c7200 import C7200
from .nodes.atm_switch import ATMSwitch
from .nodes.ethernet_switch import EthernetSwitch
from .nodes.ethernet_hub import EthernetHub
from .nodes.frame_relay_switch import FrameRelaySwitch

import logging
log = logging.getLogger(__name__)

PLATFORMS = {'c1700': C1700,
             'c2600': C2600,
             'c2691': C2691,
             'c3725': C3725,
             'c3745': C3745,
             'c3600': C3600,
             'c7200': C7200}


DEVICES = {'atm_switch': ATMSwitch,
           'frame_relay_switch': FrameRelaySwitch,
           'ethernet_switch': EthernetSwitch,
           'ethernet_hub': EthernetHub}


class DynamipsFactory:

    """
    Factory to create an Router object based on the correct platform.
    """

    def __new__(cls, name, node_id, project, manager, node_type="dynamips", dynamips_id=None, platform=None, **kwargs):

        if node_type == "dynamips":
            if platform not in PLATFORMS:
                raise DynamipsError("Unknown router platform: {}".format(platform))

            return PLATFORMS[platform](name, node_id, project, manager, dynamips_id, **kwargs)
        else:
            if node_type not in DEVICES:
                raise DynamipsError("Unknown device type: {}".format(node_type))

            return DEVICES[node_type](name, node_id, project, manager, **kwargs)
