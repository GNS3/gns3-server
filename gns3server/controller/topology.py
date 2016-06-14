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

from ..version import __version__


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
            "computes": []
        },
        "type": "topology",
        "revision": 5,
        "version": __version__
    }

    computes = set()
    for node in project.nodes.values():
        computes.add(node.compute)
        data["topology"]["nodes"].append(node.__json__())
    for link in project.links.values():
        data["topology"]["links"].append(link.__json__())
    for compute in computes:
        if hasattr(compute, "__json__"):
            data["topology"]["computes"].append(compute.__json__())
    print(data)
    #TODO: check JSON schema
    return data
