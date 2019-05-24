# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 GNS3 Technologies Inc.
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
TraceNG server module.
"""

import asyncio

from ..base_manager import BaseManager
from .traceng_error import TraceNGError
from .traceng_vm import TraceNGVM


class TraceNG(BaseManager):

    _NODE_CLASS = TraceNGVM

    def __init__(self):

        super().__init__()

    async def create_node(self, *args, **kwargs):
        """
        Creates a new TraceNG VM.

        :returns: TraceNGVM instance
        """

        return (await super().create_node(*args, **kwargs))
