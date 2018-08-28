# -*- coding: utf-8 -*-
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

from ..iou_error import IOUError

import logging
log = logging.getLogger(__name__)


def get_next_application_id(nodes):
    """
    Calculates free application_id from given nodes

    :param nodes:
    :raises IOUError when exceeds number
    :return: integer first free id
    """
    used = set([n.application_id for n in nodes])
    pool = set(range(1, 512))
    try:
        return (pool - used).pop()
    except KeyError:
        raise IOUError("Cannot create a new IOU VM (limit of 512 VMs on one host reached)")
