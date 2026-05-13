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
from uuid import uuid4

import pytest
from unittest import mock
from unittest.mock import patch, MagicMock
from gns3server.controller.snapshot import Snapshot

from tests.utils import AsyncioMagicMock


def test_snapshot_name(project):
    """
    Test create a snapshot object with a name
    """

    snapshot = Snapshot(project, name="test1")
    assert snapshot.name == "test1"
    assert snapshot._created_at > 0
    assert snapshot.path == os.path.join(project.path, "snapshots", "test1.gns3snapshot")


def test_snapshot_filename(project):
    """
    Test create a snapshot object with a filename
    """

    # legacy snapshot
    snapshot = Snapshot(project, filename="test1_260716_100439.gns3project")
    assert snapshot.name == "test1"
    assert snapshot._created_at == 1469527479
    assert snapshot.path == os.path.join(project.path, "snapshots", "test1_260716_100439.gns3project")

    # new style snapshot
    snapshot_id = str(uuid4())
    snapshot = Snapshot(project, snapshot_id=snapshot_id, name="test2", created_at=1469527479)
    assert snapshot.id == snapshot_id
    assert snapshot.name == "test2"
    assert snapshot.path == os.path.join(project.path, "snapshots", "test2.gns3snapshot")
    assert snapshot._created_at == 1469527479


def test_json(project):

    # legacy snapshot
    snapshot = Snapshot(project, filename="snapshot_test_260716_100439.gns3project")
    assert snapshot.asdict() == {
        "snapshot_id": snapshot._id,
        "name": "snapshot_test",
        "project_id": project.id,
        "description": "Snapshot 'snapshot_test' taken on 2016-07-26 at 10:04:39",
        "filename": "snapshot_test_260716_100439.gns3project",
        "created_at": 1469527479
    }

    # new style snapshot
    snapshot = Snapshot(project, name="snapshot_test2")
    assert snapshot.asdict() == {
        "snapshot_id": snapshot._id,
        "name": "snapshot_test2",
        "project_id": project.id,
        "filename": "snapshot_test2.gns3snapshot",
        "description": mock.ANY,
        "created_at": mock.ANY
    }

def test_invalid_snapshot_filename(project):

    with pytest.raises(ValueError):
        Snapshot(project, filename="snapshot_test_invalid_file.gns3project")


@pytest.mark.asyncio
async def test_restore(project, controller, config):

    compute = AsyncioMagicMock()
    compute.id = "local"
    controller._computes["local"] = compute
    response = AsyncioMagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    node1_id = str(uuid4())
    await project.add_node(compute, "test1", node1_id, node_type="vpcs", properties={"startup_config": "test.cfg"})
    snapshot = await project.snapshot(name="test")

    # We add a node after the snapshots
    await project.add_node(compute, "test2", None, node_type="vpcs", properties={"startup_config": "test.cfg"})

    # project-files should be reset when reimporting
    test_file = os.path.join(project.path, "project-files", "test.txt")
    os.makedirs(os.path.join(project.path, "project-files"))
    open(test_file, "a+").close()

    assert os.path.exists(test_file)
    assert len(project.nodes) == 2

    controller._notification = MagicMock()
    await snapshot.restore()

    # make sure the original node IDs are restored
    assert list(project.nodes.keys())[0] == node1_id

    assert "snapshot.restored" in [c[0][0] for c in controller.notification.project_emit.call_args_list]
    # project.closed notification should not be sent when restoring snapshots
    assert "project.closed" not in [c[0][0] for c in controller.notification.project_emit.call_args_list]

    project = controller.get_project(project.id)
    assert not os.path.exists(test_file)
    assert len(project.nodes) == 1
