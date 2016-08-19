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

import os
import pytest
from unittest.mock import patch, MagicMock

from gns3server.controller.project import Project
from gns3server.controller.snapshot import Snapshot

from tests.utils import AsyncioMagicMock


@pytest.fixture
def project(controller):
    project = Project(controller=controller, name="Test")
    controller._projects[project.id] = project
    return project


def test_snapshot_name(project):
    """
    Test create a snapshot object with a name
    """
    snapshot = Snapshot(project, name="test1")
    assert snapshot.name == "test1"
    assert snapshot._created_at > 0
    assert snapshot.path.startswith(os.path.join(project.path, "snapshots", "test1_"))
    assert snapshot.path.endswith(".gns3project")

    # Check if UTC conversion doesn't corrupt the path
    snap2 = Snapshot(project, filename=os.path.basename(snapshot.path))
    assert snap2.path == snapshot.path


def test_snapshot_filename(project):
    """
    Test create a snapshot object with a filename
    """
    snapshot = Snapshot(project, filename="test1_260716_100439.gns3project")
    assert snapshot.name == "test1"
    assert snapshot._created_at == 1469527479.0
    assert snapshot.path == os.path.join(project.path, "snapshots", "test1_260716_100439.gns3project")


def test_json(project):
    snapshot = Snapshot(project, filename="test1_260716_100439.gns3project")
    assert snapshot.__json__() == {
        "snapshot_id": snapshot._id,
        "name": "test1",
        "project_id": project.id,
        "created_at": 1469527479
    }


def test_restore(project, controller, async_run):
    compute = AsyncioMagicMock()
    compute.id = "local"
    controller._computes["local"] = compute
    response = AsyncioMagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    async_run(project.add_node(compute, "test1", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))

    snapshot = async_run(project.snapshot(name="test"))

    # We add a node after the snapshots
    async_run(project.add_node(compute, "test2", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))

    # project-files should be reset when reimporting
    test_file = os.path.join(project.path, "project-files", "test.txt")
    os.makedirs(os.path.join(project.path, "project-files"))
    open(test_file, "a+").close()

    assert os.path.exists(test_file)
    assert len(project.nodes) == 2

    controller._notification = MagicMock()
    with patch("gns3server.config.Config.get_section_config", return_value={"local": True}):
        async_run(snapshot.restore())

    assert "snapshot.restored" in [c[0][0] for c in controller.notification.emit.call_args_list]
    # project.closed notification should not be send when restoring snapshots
    assert "project.closed" not in [c[0][0] for c in controller.notification.emit.call_args_list]

    project = controller.get_project(project.id)
    assert not os.path.exists(test_file)
    assert len(project.nodes) == 1
