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
#

"""
Cross-compute VXLAN link identity: the derived VNI and device name.
"""

import uuid

from gns3server.utils.vxlan import VXLAN_NAME_PREFIX, VXLAN_VNI_MAX, VXLAN_VNI_MIN, derive_vni, vxlan_device_name


def test_derive_vni_is_deterministic_and_bounded():
    link_id = str(uuid.uuid4())
    vni = derive_vni(link_id)
    assert derive_vni(link_id) == vni
    assert VXLAN_VNI_MIN <= vni <= VXLAN_VNI_MAX


def test_derive_vni_salt_moves_the_value():
    link_id = str(uuid.uuid4())
    values = {derive_vni(link_id, salt) for salt in range(16)}
    # Every salt lands in range; a bumped salt is a fresh point of the space
    # (a collision here would defeat the retry, and 16 draws out of ~16.8M
    # values collapsing is a hash failure, not bad luck).
    assert all(VXLAN_VNI_MIN <= v <= VXLAN_VNI_MAX for v in values)
    assert len(values) == 16


def test_derive_vni_avoids_low_well_known_vnis():
    # Flannel starts at 1, Docker overlay networks at 256: derived links
    # must never land in the low range whatever the link id.
    for _ in range(200):
        assert derive_vni(str(uuid.uuid4()), uuid.uuid4().int) >= VXLAN_VNI_MIN


def test_vxlan_device_name_deterministic_and_within_ifnamsiz():
    link_id = str(uuid.uuid4())
    node_id = str(uuid.uuid4())
    name = vxlan_device_name(link_id, node_id)
    assert name == vxlan_device_name(link_id, node_id)
    assert name.startswith(VXLAN_NAME_PREFIX)
    # IFNAMSIZ (16) includes the NUL terminator: the kernel accepts 15 chars.
    assert len(name) <= 15


def test_vxlan_device_name_unique_per_endpoint_and_link():
    link1 = str(uuid.uuid4())
    link2 = str(uuid.uuid4())
    node1 = str(uuid.uuid4())
    node2 = str(uuid.uuid4())
    names = {
        vxlan_device_name(link1, node1),
        vxlan_device_name(link1, node2),
        vxlan_device_name(link2, node1),
    }
    assert len(names) == 3
