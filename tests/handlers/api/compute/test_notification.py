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

import json

from gns3server.compute.notification_manager import NotificationManager


async def test_notification_ws(compute_api, http_client):

    ws = await http_client.ws_connect(compute_api.get_url("/notifications/ws"))
    answer = await ws.receive()
    answer = json.loads(answer.data)

    assert answer["action"] == "ping"

    NotificationManager.instance().emit("test", {})

    answer = await ws.receive()
    answer = json.loads(answer.data)
    assert answer["action"] == "test"

    if not ws.closed:
        await ws.close()
