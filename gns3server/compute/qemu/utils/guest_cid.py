#
# Copyright (C) 2017 GNS3 Technologies Inc.
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

from ..qemu_error import QemuError

import logging

log = logging.getLogger(__name__)


def get_next_guest_cid(nodes):
    """
    Calculates free guest_id from given nodes

    :param nodes:
    :raises QemuError when exceeds number
    :return: integer first free cid
    """

    used = {n.guest_cid for n in nodes}
    pool = set(range(3, 65535))
    try:
        return (pool - used).pop()
    except KeyError:
        raise QemuError("Cannot create a new Qemu VM (limit of 65535 guest ID on one host reached)")
