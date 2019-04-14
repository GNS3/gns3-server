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
import aiohttp
from aiohttp.web import WebSocketResponse
from gns3server.web.route import Route
from gns3server.compute.notification_manager import NotificationManager

import logging
log = logging.getLogger(__name__)


async def process_websocket(ws):
    """
    Process ping / pong and close message
    """
    try:
        await ws.receive()
    except aiohttp.WSServerHandshakeError:
        pass


class NotificationHandler:

    @Route.get(
        r"/notifications/ws",
        description="Send notifications using Websockets")
    async def notifications(request, response):
        notifications = NotificationManager.instance()
        ws = WebSocketResponse()
        await ws.prepare(request)

        request.app['websockets'].add(ws)
        asyncio.ensure_future(process_websocket(ws))
        log.info("New client has connected to compute WebSocket")
        try:
            with notifications.queue() as queue:
                while True:
                    notification = await queue.get_json(1)
                    if ws.closed:
                        break
                    await ws.send_str(notification)
        finally:
            log.info("Client has disconnected from compute WebSocket")
            if not ws.closed:
                await ws.close()
            request.app['websockets'].discard(ws)

        return ws
