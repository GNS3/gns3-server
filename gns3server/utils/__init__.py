#!/usr/bin/env python
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


import textwrap
import posixpath


def force_unix_path(path):
    """
    :param path: Path to convert
    """

    path = path.replace("\\", "/")
    return posixpath.normpath(path)


def macaddress_to_int(macaddress):
    """
    Convert a macaddress with the format 00:0c:29:11:b0:0a to a int

    :param macaddress: The mac address
    :returns: Integer
    """
    return int(macaddress.replace(":", ""), 16)


def int_to_macaddress(integer):
    """
    Convert an integer to a macaddress
    """
    return ":".join(textwrap.wrap("%012x" % (integer), width=2))
