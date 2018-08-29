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
from gns3server.utils.asyncio import asyncio_ensure_future


@asyncio.coroutine
def process_websocket(ws):
    """
    Process ping / pong and close message
    """
    try:
        yield from ws.receive()
    except aiohttp.WSServerHandshakeError:
        pass


class NotificationHandler:

    @Route.get(
        r"/notifications",
        description="Receive notifications about the controller",
        status_codes={
            200: "End of stream"
        })
    def notification(request, response):

        controller = Controller.instance()
        response.content_type = "application/json"
        response.set_status(200)
        response.enable_chunked_encoding()

        yield from response.prepare(request)
        with controller.notification.controller_queue() as queue:
            while True:
                try:
                    msg = yield from queue.get_json(5)
                    response.write(("{}\n".format(msg)).encode("utf-8"))
                except asyncio.futures.CancelledError:
                    break
                yield from response.drain()

    @Route.get(
        r"/notifications/ws",
        description="Receive notifications about controller from a Websocket",
        status_codes={
            200: "End of stream"
        })
    def notification_ws(request, response):

        controller = Controller.instance()
        ws = aiohttp.web.WebSocketResponse()
        yield from ws.prepare(request)

        asyncio_ensure_future(process_websocket(ws))
        with controller.notification.controller_queue() as queue:
            while True:
                try:
                    notification = yield from queue.get_json(5)
                except asyncio.futures.CancelledError:
                    break
                if ws.closed:
                    break
                ws.send_str(notification)
        return ws
