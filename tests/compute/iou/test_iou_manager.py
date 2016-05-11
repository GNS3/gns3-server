# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
from unittest.mock import patch
import uuid
import os
import sys

pytestmark = pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")

if not sys.platform.startswith("win"):
    from gns3server.compute.iou import IOU
    from gns3server.compute.iou.iou_error import IOUError

from gns3server.compute.project_manager import ProjectManager


@pytest.fixture(scope="function")
def iou(port_manager):
    # Cleanup the IOU object
    IOU._instance = None
    iou = IOU.instance()
    iou.port_manager = port_manager
    return iou


def test_get_application_id(loop, project, iou):
    vm1_id = str(uuid.uuid4())
    vm2_id = str(uuid.uuid4())
    vm3_id = str(uuid.uuid4())
    loop.run_until_complete(iou.create_node("PC 1", project.id, vm1_id))
    loop.run_until_complete(iou.create_node("PC 2", project.id, vm2_id))
    assert iou.get_application_id(vm1_id) == 1
    assert iou.get_application_id(vm1_id) == 1
    assert iou.get_application_id(vm2_id) == 2
    loop.run_until_complete(iou.delete_node(vm1_id))
    loop.run_until_complete(iou.create_node("PC 3", project.id, vm3_id))
    assert iou.get_application_id(vm3_id) == 1


def test_get_application_id_multiple_project(loop, iou):
    vm1_id = str(uuid.uuid4())
    vm2_id = str(uuid.uuid4())
    vm3_id = str(uuid.uuid4())
    project1 = ProjectManager.instance().create_project(project_id=str(uuid.uuid4()))
    project2 = ProjectManager.instance().create_project(project_id=str(uuid.uuid4()))
    loop.run_until_complete(iou.create_node("PC 1", project1.id, vm1_id))
    loop.run_until_complete(iou.create_node("PC 2", project1.id, vm2_id))
    loop.run_until_complete(iou.create_node("PC 2", project2.id, vm3_id))
    assert iou.get_application_id(vm1_id) == 1
    assert iou.get_application_id(vm2_id) == 2
    assert iou.get_application_id(vm3_id) == 3


def test_get_application_id_no_id_available(loop, project, iou):
    with pytest.raises(IOUError):
        for i in range(1, 513):
            node_id = str(uuid.uuid4())
            loop.run_until_complete(iou.create_node("PC {}".format(i), project.id, node_id))
            assert iou.get_application_id(node_id) == i


def test_get_images_directory(iou, tmpdir):
    with patch("gns3server.config.Config.get_section_config", return_value={"images_path": str(tmpdir)}):
        assert iou.get_images_directory() == str(tmpdir / "IOU")
