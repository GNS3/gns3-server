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
Ethernet-switch link), plus the cascade veth naming for switch-to-switch
links.
"""

from gns3server.utils.kernel_anchor import anchor_suffix, kernel_anchor_name, kernel_anchor_type, kernel_cascade_names

NODE_ID = "00010203-0405-0607-0809-0a0b0c0d0e0f"
LINK_ID = "1a2b3c4d-5e6f-4a5b-8c9d-0e1f2a3b4c5d"


def test_every_node_type_has_its_own_prefix():
    assert kernel_anchor_name("docker", NODE_ID, 0, 0) == "gv00010203e0p0"
    assert kernel_anchor_name("qemu", NODE_ID, 1, 2) == "gq00010203e1p2"
    assert kernel_anchor_name("iou", NODE_ID, 0, 3) == "gi00010203e0p3"
    assert kernel_anchor_name("dynamips", NODE_ID, 6, 48) == "gd00010203e6p48"
    assert kernel_anchor_name("iol_docker", NODE_ID, 0, 0) == "gx00010203e0p0"


def test_anchor_type_keys_iol_runner_containers_apart():
    """
    IOL runner containers are Docker nodes whose anchors are persistent TAPs,
    not veth host ends — their own key keeps the gv namespace free of TAPs.
    The marker check must ignore a mere mention of the knob and survive a
    multi-line environment.
    """

    assert kernel_anchor_type("docker", "GNS3_IOL_RUNNER=1") == "iol_docker"
    assert kernel_anchor_type("docker", "GNS3_IOL_STARTUP_CONFIG=cfg.txt\nGNS3_IOL_RUNNER=1") == "iol_docker"
    assert kernel_anchor_type("docker") == "docker"
    assert kernel_anchor_type("docker", "GNS3_UNIX_SOCKET_NIO=1") == "docker"
    assert kernel_anchor_type("qemu") == "qemu"


def test_unknown_node_types_have_no_anchor():
    assert kernel_anchor_name("ethernet_switch", NODE_ID, 0, 0) is None
    assert kernel_anchor_name("vpcs", NODE_ID, 0, 0) is None


def test_names_fit_ifnamsiz():
    # worst case: WIC port numbers reach 48 with the longest prefix
    assert len(kernel_anchor_name("dynamips", NODE_ID, 6, 48)) <= 15


def test_suffix_is_stable_across_the_node_type():
    assert anchor_suffix(NODE_ID, 1, 2) == "00010203e1p2"
    assert kernel_anchor_name("docker", NODE_ID, 1, 2) == "gv" + anchor_suffix(NODE_ID, 1, 2)


def test_cascade_names_are_a_pair_of_distinct_sides():
    end0, end1 = kernel_cascade_names(LINK_ID)
    assert end0 == "gs1a2b3c4d5e0"
    assert end1 == "gs1a2b3c4d5e1"
    assert end0 != end1


def test_cascade_names_fit_ifnamsiz():
    for end in kernel_cascade_names(LINK_ID):
        assert len(end) <= 15


def test_cascade_names_stay_out_of_the_node_anchor_namespace():
    # "gs" cannot collide with any node anchor prefix (gv/gq/gi/gd/gx), so a
    # cascade end is never mistaken for another node's anchor
    for end in kernel_cascade_names(LINK_ID):
        assert not any(end.startswith(prefix) for prefix in ("gv", "gq", "gi", "gd", "gx"))
