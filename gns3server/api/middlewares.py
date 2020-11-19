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

import time
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from gns3server.version import __version__


class AddExtraHeadersMiddleware:

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:


        if scope["type"] in ("http", "websocket") and scope["scheme"] in ("http", "ws"):
            url = URL(scope=scope)
            redirect_scheme = {"http": "https", "ws": "wss"}[url.scheme]
            netloc = url.hostname if url.port in (80, 443) else url.netloc
            url = url.replace(scheme=redirect_scheme, netloc=netloc)
            response = RedirectResponse(url, status_code=307)
            await response(scope, receive, send)


@app.middleware("http")
async def add_extra_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-GNS3-Server-Version"] = "{}".format(__version__)
    return response
