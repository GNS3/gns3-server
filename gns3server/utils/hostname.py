#!/usr/bin/env python
#
# Copyright (C) 2022 GNS3 Technologies Inc.
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

import re


def is_ios_hostname_valid(hostname: str) -> bool:
    """
    Check if an IOS hostname is valid

    IOS hostname must start with a letter, end with a letter or digit, and
    have as interior characters only letters, digits, and hyphens.
    They must be 63 characters or fewer (ARPANET rules).
    """

    if re.search(r"""^(?!-|[0-9])[a-zA-Z0-9-]{1,63}(?<!-)$""", hostname):
        return True
    return False


def is_rfc1123_hostname_valid(hostname: str) -> bool:
    """
    Check if a hostname is valid according to RFC 1123

    Each element of the hostname must be from 1 to 63 characters long
    and the entire hostname, including the dots, can be at most 253
    characters long.  Valid characters for hostnames are ASCII
    letters from a to z, the digits from 0 to 9, and the hyphen (-).
    A hostname may not start with a hyphen.
    """

    if hostname[-1] == ".":
        hostname = hostname[:-1]  # strip exactly one dot from the right, if present

    if len(hostname) > 253:
        return False

    labels = hostname.split(".")

    # the TLD must be not all-numeric
    if re.match(r"[0-9]+$", labels[-1]):
        return False

    allowed = re.compile(r"(?!-)[a-zA-Z0-9-]{1,63}(?<!-)$")
    return all(allowed.match(label) for label in labels)
