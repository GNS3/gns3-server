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
#

from gns3server.controller.controller_error import ControllerError

import logging

log = logging.getLogger(__name__)

# IOU draws from the lower half: uBridge's iol_bridge uses application_id + 512
# for its netio peer endpoint. IOL Docker nodes (iol-runner images) draw from
# the upper half: their netiomux peer is the fixed id 1023. Both node types
# derive interface MACs from the id (aabb.cc{app}{iface}), so the two pools
# must stay disjoint — a shared id silently blackholes traffic between the
# nodes as a MAC loop.
IOU_APPLICATION_ID_POOL = range(1, 512)
IOL_DOCKER_APPLICATION_ID_POOL = range(512, 1023)


def is_iol_runner_environment(environment) -> bool:
    """
    Whether a Docker node environment carries the GNS3_IOL_RUNNER marker —
    the same signal the compute uses to select the IOLDockerVM class.
    """

    return "GNS3_IOL_RUNNER=" in (environment or "")


def get_next_application_id(projects, computes, iol_docker=False):
    """
    Calculates free application_id from given nodes

    :param projects: all projects managed by controller
    :param computes: all computes used by the project
    :param iol_docker: allocate for an IOL Docker (iol-runner) node instead of IOU
    :raises HTTPConflict when exceeds number
    :return: integer first free id
    """

    nodes = []

    # look for application id for in all nodes across all opened projects that share the same computes
    for project in projects.values():
        if project.status == "opened":
            nodes.extend(list(project.nodes.values()))

    if iol_docker:
        used = {
            n.properties["application_id"]
            for n in nodes
            if n.node_type == "docker"
            and n.compute.id in computes
            and "application_id" in n.properties
            and is_iol_runner_environment(n.properties.get("environment"))
        }
        pool = set(IOL_DOCKER_APPLICATION_ID_POOL)
        limit = "511 IOL Docker nodes"
    else:
        used = {n.properties["application_id"] for n in nodes if n.node_type == "iou" and n.compute.id in computes}
        pool = set(IOU_APPLICATION_ID_POOL)
        limit = "512 nodes"
    try:
        application_id = (pool - used).pop()
        return application_id
    except KeyError:
        raise ControllerError(
            f"Cannot create a new {'IOL Docker' if iol_docker else 'IOU'} node "
            f"(limit of {limit} across all opened projects using the same computes)"
        )
