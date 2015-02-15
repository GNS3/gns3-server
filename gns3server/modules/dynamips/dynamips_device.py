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
from .nodes.atm_switch import ATMSwitch
from .nodes.ethernet_switch import EthernetSwitch
from .nodes.ethernet_hub import EthernetHub
from .nodes.frame_relay_switch import FrameRelaySwitch

import logging
log = logging.getLogger(__name__)

DEVICES = {'atm_switch': ATMSwitch,
           'frame_relay_switch': FrameRelaySwitch,
           'ethernet_switch': EthernetSwitch,
           'ethernet_hub': EthernetHub}


class DynamipsDevice:

    """
    Factory to create an Device object based on the type
    """

    def __new__(cls, name, device_id, project, manager, device_type, **kwargs):

        if device_type not in DEVICES:
            raise DynamipsError("Unknown device type: {}".format(device_type))

        return DEVICES[device_type](name, device_id, project, manager, **kwargs)
