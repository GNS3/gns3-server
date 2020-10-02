# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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


import pytest
import uuid


from gns3server.compute.vpcs import VPCS
from gns3server.compute.vpcs.vpcs_error import VPCSError
from gns3server.compute.project_manager import ProjectManager


@pytest.mark.asyncio
async def test_get_mac_id(compute_project, port_manager):

    # Cleanup the VPCS object
    VPCS._instance = None
    vpcs = VPCS.instance()
    vpcs.port_manager = port_manager
    vm1_id = str(uuid.uuid4())
    vm2_id = str(uuid.uuid4())
    vm3_id = str(uuid.uuid4())
    await vpcs.create_node("PC 1", compute_project.id, vm1_id)
    await vpcs.create_node("PC 2", compute_project.id, vm2_id)
    assert vpcs.get_mac_id(vm1_id) == 0
    assert vpcs.get_mac_id(vm1_id) == 0
    assert vpcs.get_mac_id(vm2_id) == 1
    await vpcs.delete_node(vm1_id)
    await vpcs.create_node("PC 3", compute_project.id, vm3_id)
    assert vpcs.get_mac_id(vm3_id) == 0


@pytest.mark.asyncio
async def test_get_mac_id_multiple_project(port_manager):

    # Cleanup the VPCS object
    VPCS._instance = None
    vpcs = VPCS.instance()
    vpcs.port_manager = port_manager
    vm1_id = str(uuid.uuid4())
    vm2_id = str(uuid.uuid4())
    vm3_id = str(uuid.uuid4())
    project1 = ProjectManager.instance().create_project(project_id=str(uuid.uuid4()))
    project2 = ProjectManager.instance().create_project(project_id=str(uuid.uuid4()))
    await vpcs.create_node("PC 1", project1.id, vm1_id)
    await vpcs.create_node("PC 2", project1.id, vm2_id)
    await vpcs.create_node("PC 2", project2.id, vm3_id)
    assert vpcs.get_mac_id(vm1_id) == 0
    assert vpcs.get_mac_id(vm2_id) == 1
    assert vpcs.get_mac_id(vm3_id) == 0


@pytest.mark.asyncio
async def test_get_mac_id_no_id_available(compute_project, port_manager):

    # Cleanup the VPCS object
    VPCS._instance = None
    vpcs = VPCS.instance()
    vpcs.port_manager = port_manager
    with pytest.raises(VPCSError):
        for i in range(0, 256):
            node_id = str(uuid.uuid4())
            await vpcs.create_node("PC {}".format(i), compute_project.id, node_id)
            assert vpcs.get_mac_id(node_id) == i
