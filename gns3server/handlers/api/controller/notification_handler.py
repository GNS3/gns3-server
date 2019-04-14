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
from gns3server.controller import Controller

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
        r"/notifications",
        description="Receive notifications about the controller",
        status_codes={
            200: "End of stream"
        })
    async def notification(request, response):

        controller = Controller.instance()
        response.content_type = "application/json"
        response.set_status(200)
        response.enable_chunked_encoding()

        await response.prepare(request)
        with controller.notification.controller_queue() as queue:
            while True:
                msg = await queue.get_json(5)
                await response.write(("{}\n".format(msg)).encode("utf-8"))

    @Route.get(
        r"/notifications/ws",
        description="Receive notifications about controller from a Websocket",
        status_codes={
            200: "End of stream"
        })
    async def notification_ws(request, response):

        controller = Controller.instance()
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)

        request.app['websockets'].add(ws)
        asyncio.ensure_future(process_websocket(ws))
        log.info("New client has connected to controller WebSocket")
        try:
            with controller.notification.controller_queue() as queue:
                while True:
                    notification = await queue.get_json(5)
                    if ws.closed:
                        break
                    await ws.send_str(notification)
        finally:
            log.info("Client has disconnected from controller WebSocket")
            if not ws.closed:
                await ws.close()
            request.app['websockets'].discard(ws)

        return ws
