# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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

from .adapter import Adapter


class C1700_MB_WIC1(Adapter):

    """
    Fake module to provide a placeholder for slot 1 interfaces when WICs
    are inserted into WIC slot 1.
    """

    def __init__(self):

        super().__init__(interfaces=0, wics=2)

    def __str__(self):

        return "C1700-MB-WIC1"

    def removable(self):

        return False
