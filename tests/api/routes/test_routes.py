# -*- coding: utf-8 -*-
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

import pytest
from fastapi import FastAPI, status
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import Mount
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

ALLOWED_CONTROLLER_ENDPOINTS = [
    ("/", "GET"),
    ("/debug", "GET"),
    ("/static/web-ui/{file_path:path}", "GET"),
    ("/v3/version", "GET"),
    ("/v3/version", "POST"),
    ("/v3/users/login", "POST"),
    ("/v3/users/authenticate", "POST"),
    ("/v3/symbols", "GET"),
    ("/v3/symbols/{symbol_id:path}/raw", "GET"),
    ("/v3/symbols/{symbol_id:path}/dimensions", "GET"),
    ("/v3/symbols/default_symbols", "GET")
]

# Controller endpoints have a OAuth2 bearer token authentication
async def test_controller_endpoints_require_authentication(app: FastAPI, unauthorized_client: AsyncClient) -> None:

    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in list(route.methods):
                if (route.path, method) not in ALLOWED_CONTROLLER_ENDPOINTS:
                    response = await getattr(unauthorized_client, method.lower())(route.path)
                    assert response.status_code == status.HTTP_401_UNAUTHORIZED
        elif isinstance(route, APIWebSocketRoute):
            pass  # TODO: test websocket route authentication

# Compute endpoints have a basic HTTP authentication
async def test_compute_endpoints_require_authentication(app: FastAPI, unauthorized_client: AsyncClient) -> None:

    for route in app.routes:
        if isinstance(route, Mount):
            for compute_route in route.routes:
                if isinstance(compute_route, APIRoute):  # APIWebSocketRoute
                    for method in list(compute_route.methods):
                        response = await getattr(unauthorized_client, method.lower())(route.path + compute_route.path)
                        assert response.status_code == status.HTTP_401_UNAUTHORIZED
                elif isinstance(compute_route, APIWebSocketRoute):
                    pass # TODO: test websocket route authentication
