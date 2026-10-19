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
Identity of a cross-compute VXLAN link: the device name and VNI the
controller derives and ships in both endpoints' NIOs.

A cross-compute kernel link is carried by one VXLAN device per endpoint
(uBridge's ``vxlan`` module, rtnetlink), enslaved into the link's per-link
kernel bridge next to the node's anchor. Each device is local to its own
host, but the VNI is the kernel's demux key for received frames on the
deployment-wide shared dstport socket — both ends must agree on it while
neither can ask the other, so the controller is the single source for both
values.

* the device name is a pure function of the link id plus the endpoint's
  node id: unique per (link, endpoint), within IFNAMSIZ, and outside the
  ``gns3``/anchor name spaces (``gvl`` prefix). Determinism is what makes
  a crashed run's leftover device recognisable — the compute deletes a
  device it finds under the name before re-creating it;
* the VNI is a pure function of the link id and a controller-side salt —
  a random base per link object, bumped when a retry needs a fresh VNI —
  drawn from the upper half of the VNI space so it cannot collide with the
  low well-known VNIs other software uses (Flannel's 1, Docker overlay
  networks from 256, ...).

The kernel refuses a second device registering a VNI already taken on the
same (dstport, socket) pair with EEXIST — a check that doubles as the
collision detector: the controller retries with a bumped salt and falls
back to the UDP relay when the space stays occupied (the relay needs no
VNI at all).
"""

import hashlib

# The VNI range derived links draw from: at or above 0x100000 (1M) to stay
# clear of the low VNIs other VXLAN software commonly registers, at or below
# 0xFFFFFE so every derived value is valid for the module's 1..16777215
# (0xFFFFFF) check with one value of headroom.
VXLAN_VNI_MIN = 0x100000
VXLAN_VNI_MAX = 0xFFFFFE

# IFNAMSIZ (16) - 1 for the terminator: "gvl" (3) + 8 (link) + 4 (node) = 15.
VXLAN_NAME_PREFIX = "gvl"


def derive_vni(link_id, salt=0):
    """
    The VNI both endpoints of *link_id* tunnel through.

    :param link_id: link UUID (or str)
    :param salt: controller-side retry counter — bumped when the kernel
        refuses the previous VNI as already registered on the shared
        dstport socket; 0 for the first attempt
    :returns: VNI in [VXLAN_VNI_MIN, VXLAN_VNI_MAX]
    """

    digest = hashlib.sha256(f"{link_id}:{salt}".encode()).digest()
    span = VXLAN_VNI_MAX - VXLAN_VNI_MIN + 1
    return VXLAN_VNI_MIN + int.from_bytes(digest[:8], "big") % span


def vxlan_device_name(link_id, node_id):
    """
    The VXLAN device name one endpoint of *link_id* creates on its own host,
    deterministic from the link id plus the endpoint's node id (the pair
    normally lives on two hosts, but a forced same-host pair must not name
    both its devices identically).
    """

    link = str(link_id).replace("-", "")[:8]
    node = str(node_id).replace("-", "")[:4]
    return f"{VXLAN_NAME_PREFIX}{link}{node}"
