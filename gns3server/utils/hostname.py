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


def to_ios_hostname(name):
    """
    Convert name to an IOS hostname
    """

    # Replace invalid characters with hyphens
    name = re.sub(r'[^a-zA-Z0-9-]', '-', name)

    # Ensure the hostname starts with a letter
    if not re.search(r'^[a-zA-Z]', name):
        name = 'a' + name

    # Ensure the hostname ends with a letter or digit
    if not re.search(r'[a-zA-Z0-9]$', name):
        name = name.rstrip('-') + '0'

    # Truncate the hostname to 63 characters
    name = name[:63]

    return name


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


def to_rfc1123_hostname(name: str) -> str:
    """
    Convert name to RFC 1123 hostname
    """

    # Replace invalid characters with hyphens
    name = re.sub(r'[^a-zA-Z0-9-.]', '-', name)

    # Remove trailing dot if it exists
    name = name.rstrip('.')

    # Ensure each label is not longer than 63 characters
    labels = name.split('.')
    labels = [label[:63] for label in labels]

    # Remove leading and trailing hyphens from each label if they exist
    labels = [label.strip('-') for label in labels]

    # Check if the TLD is all-numeric and if so, replace it with "invalid"
    if re.match(r"[0-9]+$", labels[-1]):
        labels[-1] = 'invalid'

    # Join the labels back together
    name = '.'.join(labels)

    # Ensure the total length is not longer than 253 characters
    name = name[:253]

    return name
