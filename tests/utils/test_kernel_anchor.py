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
The kernel-datapath anchor naming contract (shared by the compute classes
that create anchors and the controller that names a peer's anchor for an
Ethernet-switch link).
"""

from gns3server.utils.kernel_anchor import anchor_suffix, kernel_anchor_name

NODE_ID = "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_every_node_type_has_its_own_prefix():
    assert kernel_anchor_name("docker", NODE_ID, 0, 0) == "gv00010203e0p0"
    assert kernel_anchor_name("qemu", NODE_ID, 1, 2) == "gq00010203e1p2"
    assert kernel_anchor_name("iou", NODE_ID, 0, 3) == "gi00010203e0p3"
    assert kernel_anchor_name("dynamips", NODE_ID, 6, 48) == "gd00010203e6p48"


def test_unknown_node_types_have_no_anchor():
    assert kernel_anchor_name("ethernet_switch", NODE_ID, 0, 0) is None
    assert kernel_anchor_name("vpcs", NODE_ID, 0, 0) is None


def test_names_fit_ifnamsiz():
    # worst case: WIC port numbers reach 48 with the longest prefix
    assert len(kernel_anchor_name("dynamips", NODE_ID, 6, 48)) <= 15


def test_suffix_is_stable_across_the_node_type():
    assert anchor_suffix(NODE_ID, 1, 2) == "00010203e1p2"
    assert kernel_anchor_name("docker", NODE_ID, 1, 2) == "gv" + anchor_suffix(NODE_ID, 1, 2)
