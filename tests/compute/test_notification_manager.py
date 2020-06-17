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

import uuid

from gns3server.compute.notification_manager import NotificationManager


async def test_queue():

    NotificationManager.reset()
    notifications = NotificationManager.instance()
    with notifications.queue() as queue:
        assert len(notifications._listeners) == 1

        res = await queue.get(5)
        assert res[0] == "ping"

        notifications.emit("test", {"a": 1})
        res = await queue.get(5)
        assert res == ('test', {"a": 1}, {})

    assert len(notifications._listeners) == 0


async def test_queue_json():

    NotificationManager.reset()
    notifications = NotificationManager.instance()
    with notifications.queue() as queue:
        assert len(notifications._listeners) == 1

        res = await queue.get(5)
        assert "ping" in res

        notifications.emit("test", {"a": 1})
        res = await queue.get_json(5)
        assert res == '{"action": "test", "event": {"a": 1}}'

    assert len(notifications._listeners) == 0


async def test_queue_json_meta():

    NotificationManager.reset()
    project_id = str(uuid.uuid4())
    notifications = NotificationManager.instance()
    with notifications.queue() as queue:
        assert len(notifications._listeners) == 1

        res = await queue.get(5)
        assert "ping" in res

        notifications.emit("test", {"a": 1}, project_id=project_id)
        res = await queue.get_json(5)
        assert res == '{"action": "test", "event": {"a": 1}, "project_id": "' + project_id + '"}'

    assert len(notifications._listeners) == 0


async def test_queue_ping():
    """
    If we don't send a message during a long time (0.5 seconds)
    a ping is send
    """

    NotificationManager.reset()
    notifications = NotificationManager.instance()
    with notifications.queue() as queue:
        assert len(notifications._listeners) == 1

        res = await queue.get(5)
        assert res[0] == "ping"

        res = await queue.get(0.5)
        assert res[0] == "ping"
        assert res[1]["cpu_usage_percent"] is not None
    assert len(notifications._listeners) == 0
