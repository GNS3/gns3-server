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

import pytest
from unittest.mock import MagicMock

from gns3server.controller.notification import Notification
from gns3server.controller import Controller
from tests.utils import AsyncioMagicMock


@pytest.fixture
def project(async_run):
    return async_run(Controller.instance().add_project(name="Test"))


@pytest.fixture
def node(project, async_run):
    compute = MagicMock()
    compute.id = "remote1"
    compute.host = "example.org"
    response = MagicMock()
    response.json = {"console": 2048}
    compute.post = AsyncioMagicMock(return_value=response)

    return async_run(project.add_node(compute, "test", None, node_type="vpcs", properties={"startup_config": "test.cfg"}))


def test_emit_to_all(async_run, controller, project):
    """
    Send an event to all if we don't have a project id in the event
    """
    notif = controller.notification
    with notif.queue(project) as queue:
        assert len(notif._listeners[project.id]) == 1
        async_run(queue.get(0.1))  # ping
        notif.emit('test', {})
        msg = async_run(queue.get(5))
        assert msg == ('test', {}, {})

    assert len(notif._listeners[project.id]) == 0


def test_emit_to_project(async_run, controller, project):
    """
    Send an event to a project listeners
    """
    notif = controller.notification
    with notif.queue(project) as queue:
        assert len(notif._listeners[project.id]) == 1
        async_run(queue.get(0.1))  # ping
        # This event has not listener
        notif.emit('ignore', {"project_id": 42})
        notif.emit('test', {"project_id": project.id})
        msg = async_run(queue.get(5))
        assert msg == ('test', {"project_id": project.id}, {})

    assert len(notif._listeners[project.id]) == 0


def test_dispatch(async_run, controller, project):
    notif = controller.notification
    with notif.queue(project) as queue:
        assert len(notif._listeners[project.id]) == 1
        async_run(queue.get(0.1))  # ping
        async_run(notif.dispatch("test", {}, compute_id=1))
        msg = async_run(queue.get(5))
        assert msg == ('test', {}, {})


def test_dispatch_ping(async_run, controller, project):
    notif = controller.notification
    with notif.queue(project) as queue:
        assert len(notif._listeners[project.id]) == 1
        async_run(queue.get(0.1))  # ping
        async_run(notif.dispatch("ping", {}, compute_id=12))
        msg = async_run(queue.get(5))
        assert msg == ('ping', {'compute_id': 12}, {})


def test_dispatch_node_updated(async_run, controller, node, project):
    """
    When we receive a node.updated notification from compute
    we need to update the client
    """

    notif = controller.notification
    with notif.queue(project) as queue:
        assert len(notif._listeners[project.id]) == 1
        async_run(queue.get(0.1))  # ping
        async_run(notif.dispatch("node.updated", {
            "node_id": node.id,
            "project_id": project.id,
            "name": "hello",
            "startup_config": "ip 192"
        },
            compute_id=1))
        assert node.name == "hello"
        action, event, _ = async_run(queue.get(5))
        assert action == "node.updated"
        assert event["name"] == "hello"
        assert event["properties"]["startup_config"] == "ip 192"


def test_various_notification(controller, node):
    notif = controller.notification
    notif.emit("log.info", {"message": "Image uploaded"})
    notif.emit("log.warning", {"message": "Warning ASA 8 is not officialy supported by GNS3"})
    notif.emit("log.error", {"message": "Permission denied on /tmp"})
    notif.emit("node.updated", node.__json__())
