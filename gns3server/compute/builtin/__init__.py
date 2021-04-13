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

"""
Builtin nodes server module.
"""


from ..base_manager import BaseManager
from .builtin_node_factory import BuiltinNodeFactory, BUILTIN_NODES

import logging

log = logging.getLogger(__name__)


class Builtin(BaseManager):

    _NODE_CLASS = BuiltinNodeFactory

    def __init__(self):

        super().__init__()

    @classmethod
    def node_types(cls):
        """
        :returns: List of node type supported by this class and computer
        """
        types = ["cloud", "ethernet_hub", "ethernet_switch"]
        if BUILTIN_NODES["nat"].is_supported():
            types.append("nat")
        return types
