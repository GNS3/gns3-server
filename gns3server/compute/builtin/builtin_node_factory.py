# -*- coding: utf-8 -*-
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


from ..error import NodeError
from .nodes.cloud import Cloud
from .nodes.nat import Nat
from .nodes.ethernet_hub import EthernetHub
from .nodes.ethernet_switch import EthernetSwitch

import logging
log = logging.getLogger(__name__)

BUILTIN_NODES = {'cloud': Cloud,
                 'nat': Nat,
                 'ethernet_hub': EthernetHub,
                 'ethernet_switch': EthernetSwitch}


class BuiltinNodeFactory:

    """
    Factory to create an builtin object based on the node type.
    """

    def __new__(cls, name, node_id, project, manager, node_type, **kwargs):

        if node_type not in BUILTIN_NODES:
            raise NodeError("Unknown node type: {}".format(node_type))

        return BUILTIN_NODES[node_type](name, node_id, project, manager, **kwargs)
