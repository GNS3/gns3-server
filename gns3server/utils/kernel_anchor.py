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
``gd`` for a Dynamips port TAP. The prefixes keep anchors out of the
``gns3`` bridge/TAP name space and name-collision-free on a host; the 8
hex chars of the node id plus adapter/port keep every name unique and
within IFNAMSIZ (15).

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
    "qemu": "gq",
    "iou": "gi",
    "dynamips": "gd",
}


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
    link).
    """

    prefix = ANCHOR_PREFIX.get(node_type)
    if prefix is None:
        return None
    return prefix + anchor_suffix(node_id, adapter_number, port_number)
