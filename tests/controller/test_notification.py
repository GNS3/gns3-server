#!/usr/bin/env python
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
from unittest.mock import MagicMock

from tests.utils import AsyncioMagicMock


@pytest.fixture
async def node(project):

    compute = MagicMock()
    compute.id = "remote1"
    compute.host = "example.org"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)
    return await project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"})


async def test_emit_to_all(controller, project):
    """
    Send an event to all if we don't have a project id in the event
    """

    notif = controller.notification
    with notif.project_queue(project.id) as queue:
        assert len(notif._project_listeners[project.id]) == 1
        await queue.get(0.1) # ping
        notif.project_emit('test', {})
        msg = await queue.get(5)
        assert msg == ('test', {}, {})

    assert len(notif._project_listeners[project.id]) == 0


async def test_emit_to_project(controller, project):
    """
    Send an event to a project listeners
    """

    notif = controller.notification
    with notif.project_queue(project.id) as queue:
        assert len(notif._project_listeners[project.id]) == 1
        await queue.get(0.1)  # ping
        # This event has not listener
        notif.project_emit('ignore', {"project_id": 42})
        notif.project_emit('test', {"project_id": project.id})
        msg = await queue.get(5)
        assert msg == ('test', {"project_id": project.id}, {})

    assert len(notif._project_listeners[project.id]) == 0


async def test_dispatch(controller, project):

    notif = controller.notification
    with notif.project_queue(project.id) as queue:
        assert len(notif._project_listeners[project.id]) == 1
        await queue.get(0.1)  # ping
        await notif.dispatch("test", {}, project_id=project.id, compute_id=1)
        msg = await queue.get(5)
        assert msg == ('test', {}, {})


async def test_dispatch_ping(controller, project):

    notif = controller.notification
    with notif.project_queue(project.id) as queue:
        assert len(notif._project_listeners[project.id]) == 1
        await queue.get(0.1)  # ping
        await notif.dispatch("ping", {}, project_id=project.id, compute_id=12)
        msg = await queue.get(5)
        assert msg == ('ping', {'compute_id': 12}, {})


async def test_dispatch_node_updated(controller, node, project):
    """
    When we receive a node.updated notification from compute
    we need to update the client
    """

    notif = controller.notification
    with notif.project_queue(project.id) as queue:
        assert len(notif._project_listeners[project.id]) == 1
        await queue.get(0.1)  # ping
        await notif.dispatch("node.updated", {
            "node_id": node.id,
            "project_id": project.id,
            "name": "hello",
            "startup_config": "ip 192"
        },
            project_id=project.id,
            compute_id=1)
        assert node.name == "hello"
        action, event, _ = await queue.get(5)
        assert action == "node.updated"
        assert event["name"] == "hello"
        assert event["properties"]["startup_config"] == "ip 192"


def test_various_notification(controller, node):

    notif = controller.notification
    notif.project_emit("log.info", {"message": "Image uploaded"})
    notif.project_emit("log.warning", {"message": "Warning ASA 8 is not officially supported by GNS3"})
    notif.project_emit("log.error", {"message": "Permission denied on /tmp"})
    notif.project_emit("node.updated", node.__json__())
