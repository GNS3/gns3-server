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
import aiohttp.errors

from aiohttp.web import WebSocketResponse
from gns3server.web.route import Route
from gns3server.compute.notification_manager import NotificationManager


@asyncio.coroutine
def process_websocket(ws):
    """
    Process ping / pong and close message
    """
    try:
        yield from ws.receive()
    except aiohttp.errors.WSServerHandshakeError:
        pass


class NotificationHandler:

    @Route.get(
        r"/notifications/ws",
        description="Send notifications using Websockets")
    def notifications(request, response):
        notifications = NotificationManager.instance()
        ws = WebSocketResponse()
        yield from ws.prepare(request)

        asyncio.async(process_websocket(ws))

        with notifications.queue() as queue:
            while True:
                try:
                    notification = yield from queue.get_json(5)
                except asyncio.futures.CancelledError:
                    break
                if ws.closed:
                    break
                ws.send_str(notification)
        return ws
