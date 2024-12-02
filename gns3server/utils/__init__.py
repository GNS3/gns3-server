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


import sys
import re
import shlex
import textwrap
import posixpath
import socket
import errno
import hashlib


def force_unix_path(path):
    """
    :param path: Path to convert
    """

    path = path.replace("\\", "/")
    return posixpath.normpath(path)


def macaddress_to_int(mac_address):
    """
    Convert a macaddress with the format 00:0c:29:11:b0:0a to a int

    :param mac_address: The mac address

    :returns: Integer
    """
    return int(mac_address.replace(":", ""), 16)


def int_to_macaddress(integer):
    """
    Convert an integer to a mac address
    """
    return ":".join(textwrap.wrap("%012x" % (integer), width=2))


def parse_version(version):
    """
    Return a comparable tuple from a version string. We try to force tuple to semver with version like 1.2.0

    Replace pkg_resources.parse_version which now display a warning when use for comparing version with tuple

    :returns: Version string as comparable tuple
    """

    release_type_found = False
    version_infos = re.split(r'(\.|[a-z]+)', version)
    version = []
    for info in version_infos:
        if info == '.' or len(info) == 0:
            continue
        try:
            info = int(info)
            # We pad with zero to compare only on string
            # This avoid issue when comparing version with different length
            version.append("%06d" % (info,))
        except ValueError:
            # Force to a version with three number
            if len(version) == 1:
                version.append("00000")
            if len(version) == 2:
                version.append("000000")
            # We want rc to be at lower level than dev version
            if info == 'rc':
                info = 'c'
            version.append(info)
            release_type_found = True
    if release_type_found is False:
        # Force to a version with three number
        if len(version) == 1:
            version.append("00000")
        if len(version) == 2:
            version.append("000000")
        version.append("final")
    return tuple(version)


def shlex_quote(s):
    """
    Compatible shlex_quote to handle case where Windows needs double quotes around file names, not single quotes.
    """

    if sys.platform.startswith("win"):
        return s if re.match(r'^[-_\w./]+$', s) else '"%s"' % s.replace('"', '\\"')
    else:
        return shlex.quote(s)


def is_ipv6_enabled() -> bool:

    if not socket.has_ipv6:
        return False  # the socket library has no support for IPv6
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
            sock.bind(("::1", 0))
        return True
    except OSError as e:
        if e.errno in (errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT):
            # EADDRNOTAVAIL is the errno if IPv6 modules/drivers are loaded but disabled.
            # EAFNOSUPPORT is the errno if IPv6 modules/drivers are not loaded at all.
            return False
        if e.errno == errno.EADDRINUSE:
            return True
        raise

def md5sum(filename):
    """
    Calculate the MD5 checksum of a file.
    """

    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
