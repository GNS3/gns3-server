#
# Copyright (C) 2026 GNS3 Technologies Inc.
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

"""
The kernel-datapath anchor naming contract, in one place.

Every node type whose adapters own a host-side interface names that anchor
deterministically: ``g<type>{node_id[:8]}e{adapter}p{port}`` — ``gv`` for a
Docker veth host end, ``gq`` for a QEMU TAP, ``gi`` for an IOU port TAP,
``gd`` for a Dynamips port TAP, ``gx`` for an IOL runner container's port
TAP (a Docker node whose guest leg is unix sockets, so its anchor is a TAP
like IOU's, not a veth). The prefixes keep anchors out of the ``gns3``
bridge/TAP name space and name-collision-free on a host; the 8 hex chars of
the node id plus adapter/port keep every name unique and within IFNAMSIZ
(15).

The compute classes create their anchors with these helpers (single source
of truth), and so does the controller when a switch link has to name the
peer's anchor — the name is a pure function of (node type, node id,
adapter, port), valid whether or not the node is currently running, which
is what makes links to stopped nodes wireable.
"""

import logging

log = logging.getLogger(__name__)

# Node type -> the anchor prefix its interface names carry. ``gc`` (the
# Docker veth guest end) is container-local and deliberately absent.
ANCHOR_PREFIX = {
    "docker": "gv",
    "iol_docker": "gx",
    "qemu": "gq",
    "iou": "gi",
    "dynamips": "gd",
}


def kernel_anchor_type(node_type, environment=None):
    """
    The anchor-type key a node of this type and environment names its
    anchors under. IOL runner containers are Docker nodes (node_type
    "docker") whose anchors are persistent TAPs, not veth host ends — their
    own key keeps the ``gv`` veth namespace free of TAPs (stale-interface
    sweeps and human eyes both key on the prefix). Every other node type is
    its own key unchanged.
    """

    # The marker check mirrors the compute's class selection
    # (compute/docker/__init__.py, _select_node_class) inline: only a
    # stripped, comma-trimmed line *beginning* with the marker selects
    # IOLDockerVM, so e.g. NOTE=GNS3_IOL_RUNNER=1 must not be named as an
    # IOL TAP anchor here. The check stays dependency-free on purpose: this
    # module sits below every node module (compute and controller alike
    # import it during their own import), so it must not import them back.
    if node_type == "docker":
        for line in (environment or "").splitlines():
            line = line.strip().rstrip(",")
            if line.startswith("GNS3_IOL_RUNNER="):
                return "iol_docker"
    return node_type


def anchor_suffix(node_id, adapter_number, port_number=0):
    """
    The shared ``{node_id[:8]}e{adapter}p{port}`` name stem (8 hex chars of
    the node id, no dashes).
    """

    return f"{str(node_id).replace('-', '')[:8]}e{adapter_number}p{port_number}"


def kernel_anchor_name(node_type, node_id, adapter_number, port_number=0):
    """
    The host-side kernel-datapath anchor of one adapter port, or None for a
    node type without one (the anchor-less types never anchor a kernel
    link). Accepts either a raw node type or an anchor-type key from
    :func:`kernel_anchor_type`.
    """

    prefix = ANCHOR_PREFIX.get(node_type)
    if prefix is None:
        return None
    return prefix + anchor_suffix(node_id, adapter_number, port_number)


def kernel_cascade_names(link_id):
    """
    The two veth ends of a switch-to-switch cascade link, as
    ``(owner end, peer end)``. The pair belongs to the *link* (not to either
    switch): both names are a pure function of the link id, so each side
    computes its own end and the controller can hand each switch exactly
    the name to enslave — the same deterministic-name trick per-link
    bridges use. ``gs`` keeps the cascade ends out of the node-anchor and
    ``gns3`` name spaces; 10 hex chars of the link id plus the side index
    stay within IFNAMSIZ (15).
    """

    stem = str(link_id).replace("-", "")[:10]
    return f"gs{stem}0", f"gs{stem}1"
