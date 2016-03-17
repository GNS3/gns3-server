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

import json

from gns3server.hypervisor.notification_manager import NotificationManager


def test_notification_ws(http_hypervisor, async_run):
    ws = http_hypervisor.websocket("/notifications/ws")
    answer = async_run(ws.receive())
    answer = json.loads(answer.data)
    assert answer["action"] == "ping"

    NotificationManager.instance().emit("test", {})

    answer = async_run(ws.receive())
    answer = json.loads(answer.data)
    assert answer["action"] == "test"

    async_run(http_hypervisor.close())
