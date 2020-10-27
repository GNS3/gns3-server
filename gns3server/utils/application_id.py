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

import aiohttp

import logging
log = logging.getLogger(__name__)


def get_next_application_id(projects, computes):
    """
    Calculates free application_id from given nodes

    :param projects: all projects managed by controller
    :param computes: all computes used by the project
    :raises HTTPConflict when exceeds number
    :return: integer first free id
    """

    nodes = []

    # look for application id for in all nodes across all opened projects that share the same computes
    for project in projects.values():
        if project.status == "opened":
            nodes.extend(list(project.nodes.values()))

    used = set([n.properties["application_id"] for n in nodes if n.node_type == "iou" and n.compute.id in computes])
    pool = set(range(1, 512))
    try:
        application_id = (pool - used).pop()
        return application_id
    except KeyError:
        raise aiohttp.web.HTTPConflict(text="Cannot create a new IOU node (limit of 512 nodes across all opened projects using the same computes)")
