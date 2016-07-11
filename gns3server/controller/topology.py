#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import json
import jsonschema
import aiohttp

from ..version import __version__
from ..schemas.topology import TOPOLOGY_SCHEMA

import logging
log = logging.getLogger(__name__)


GNS3_FILE_FORMAT_REVISION = 5


def _check_topology_schema(topo):
    try:
        jsonschema.validate(topo, TOPOLOGY_SCHEMA)
    except jsonschema.ValidationError as e:
        error = "Invalid data in topology file: {} in schema: {}".format(
            e.message,
            json.dumps(e.schema))
        log.critical(error)
        raise aiohttp.web.HTTPConflict(text=error)


def project_to_topology(project):
    """
    :return: A dictionnary with the topology ready to dump to a .gns3
    """
    data = {
        "project_id": project.id,
        "name": project.name,
        "topology": {
            "nodes": [],
            "links": [],
            "computes": [],
            "drawings": []
        },
        "type": "topology",
        "revision": GNS3_FILE_FORMAT_REVISION,
        "version": __version__
    }

    computes = set()
    for node in project.nodes.values():
        computes.add(node.compute)
        data["topology"]["nodes"].append(node.__json__(topology_dump=True))
    for link in project.links.values():
        data["topology"]["links"].append(link.__json__(topology_dump=True))
    for drawing in project.drawings.values():
        data["topology"]["drawings"].append(drawing.__json__(topology_dump=True))
    for compute in computes:
        if hasattr(compute, "__json__"):
            data["topology"]["computes"].append(compute.__json__(topology_dump=True))
    _check_topology_schema(data)
    return data


def load_topology(path):
    """
    Open a topology file, patch it for last GNS3 release and return it
    """
    try:
        with open(path) as f:
            topo = json.load(f)
    except OSError as e:
        raise aiohttp.web.HTTPConflict(text="Could not load topology {}: {}".format(path, str(e)))
    if topo["revision"] < GNS3_FILE_FORMAT_REVISION:
        raise aiohttp.web.HTTPConflict(text="Old GNS3 project are not yet supported")
    _check_topology_schema(topo)
    return topo
