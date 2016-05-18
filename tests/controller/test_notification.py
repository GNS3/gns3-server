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

from gns3server.controller.notification import Notification
from gns3server.controller.project import Project


def test_emit_to_all(async_run, controller):
    """
    Send an event to all if we don't have a project id in the event
    """
    project = Project()
    notif = controller.notification
    with notif.queue(project) as queue:
        assert len(notif._listeners[project.id]) == 1
        async_run(queue.get(0.1))  #  ping
        notif.emit('test', {})
        msg = async_run(queue.get(5))
        assert msg == ('test', {}, {})

    assert len(notif._listeners[project.id]) == 0


def test_emit_to_project(async_run, controller):
    """
    Send an event to a project listeners
    """
    project = Project()
    notif = controller.notification
    with notif.queue(project) as queue:
        assert len(notif._listeners[project.id]) == 1
        async_run(queue.get(0.1))  #  ping
        # This event has not listener
        notif.emit('ignore', {}, project_id=42)
        notif.emit('test', {}, project_id=project.id)
        msg = async_run(queue.get(5))
        assert msg == ('test', {}, {})

    assert len(notif._listeners[project.id]) == 0
