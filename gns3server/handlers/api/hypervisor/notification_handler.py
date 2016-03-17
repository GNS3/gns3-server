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

import asyncio

from ....web.route import Route
from ....hypervisor.notification_manager import NotificationManager
from aiohttp.web import WebSocketResponse


class NotificationHandler:

    @classmethod
    @Route.get(
        r"/notifications/ws",
        description="Send notifications about what happend using websockets")
    def notifications(request, response):
        notifications = NotificationManager.instance()
        ws = WebSocketResponse()
        yield from ws.prepare(request)

        with notifications.queue() as queue:
            while True:
                notif = yield from queue.get_json(5)
                ws.send_str(notif)
        return ws

