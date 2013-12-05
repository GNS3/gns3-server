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

"""
Utilitary functions for STOMP implementation
"""

import sys

PY2 = sys.version_info[0] == 2

if not PY2:
    def encode(char_data):
        if type(char_data) is str:
            return char_data.encode()
        elif type(char_data) is bytes:
            return char_data
        else:
            raise TypeError('message should be a string or bytes')
else:
    def encode(char_data):
        if type(char_data) is unicode:
            return char_data.encode('utf-8')
        else:
            return char_data


def hasbyte(byte, byte_data):
    return bytes([byte]) in byte_data
