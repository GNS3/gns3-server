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
from fastapi.routing import APIRoute, APIWebSocketRoute, _IncludedRouter
from starlette.routing import BaseRoute, Mount
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from typing import Iterator, Sequence, Tuple



pytestmark = pytest.mark.asyncio

ALLOWED_CONTROLLER_ENDPOINTS = [
    ("/", "GET"),
    ("/debug", "GET"),
    ("/static/web-ui/{file_path:path}", "GET"),
    ("/docs", "GET"),
    ("/docs/oauth2-redirect", "GET"),
    ("/redoc", "GET"),
    ("/v3/version", "GET"),
    ("/v3/version", "POST"),
    ("/v3/access/users/login", "POST"),
    ("/v3/access/users/authenticate", "POST"),
    ("/v3/access/users/refresh", "POST"),
    ("/v3/symbols", "GET"),
    ("/v3/symbols/{symbol_id:path}/raw", "GET"),
    ("/v3/symbols/{symbol_id:path}/dimensions", "GET"),
    ("/v3/symbols/default_symbols", "GET"),
    ("/v3/mcp/", "GET"),
]


def _join_paths(prefix: str, path: str) -> str:
    if not prefix:
        return path

    normalized_prefix = prefix
    while normalized_prefix.endswith("/"):
        normalized_prefix = normalized_prefix[:-1]

    normalized_path = path
    while normalized_path.startswith("/"):
        normalized_path = normalized_path[1:]

    return f"{normalized_prefix}/{normalized_path}"


def _iter_routes(
        routes: Sequence[BaseRoute],
        prefix: str = "",
        include_mounted_routes: bool = False
) -> Iterator[Tuple[str, BaseRoute]]:
    for route in routes:
        if isinstance(route, _IncludedRouter):
            include_prefix = route.include_context.prefix or ""
            yield from _iter_routes(route.original_router.routes, _join_paths(prefix, include_prefix), include_mounted_routes)
            continue

        if isinstance(route, (APIRoute, APIWebSocketRoute)):
            yield _join_paths(prefix, route.path), route
            continue

        if isinstance(route, Mount) and include_mounted_routes:
            mounted_routes = getattr(route, "routes", None)
            if isinstance(mounted_routes, Sequence):
                yield from _iter_routes(mounted_routes, _join_paths(prefix, route.path), include_mounted_routes)


class TestRoutes:

    # Controller endpoints have a OAuth2 bearer token authentication
    async def test_controller_endpoints_require_authentication(
            self,
            app: FastAPI,
            unauthorized_client: AsyncClient
    ) -> None:

        for path, route in _iter_routes(app.routes):
            if isinstance(route, APIRoute):
                for method in list(route.methods):
                    if (path, method) not in ALLOWED_CONTROLLER_ENDPOINTS:
                        request_path = path.rstrip("/")
                        response = await getattr(unauthorized_client, method.lower())(request_path)
                        assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"{method} {request_path} -> {response.status_code}"
            elif isinstance(route, APIWebSocketRoute) and not path.startswith("/v3/compute"):
                params = {"token": "wrong_token"}
                async with AsyncClient(base_url="http://test-api", transport=ASGIWebSocketTransport(app=app)) as client:
                    async with aconnect_ws(path, client, params=params) as ws:
                        json_notification = await ws.receive_json()
                        assert json_notification['event'] == {
                            'message': 'Could not authenticate while connecting to controller WebSocket: '
                                       'Invalid token (DecodeError) (received token sha256 prefix: 4d4f92fb)'
                        }


    # Compute endpoints have a basic HTTP authentication
    async def test_compute_endpoints_require_authentication(
            self,
            app: FastAPI,
            unauthorized_client: AsyncClient
    ) -> None:

        for path, route in _iter_routes(app.routes, include_mounted_routes=True):
            if not path.startswith("/v3/compute"):
                continue

            if isinstance(route, APIRoute):
                for method in list(route.methods):
                    request_path = path.rstrip("/")
                    response = await getattr(unauthorized_client, method.lower())(request_path)
                    #if response.status_code == status.HTTP_307_TEMPORARY_REDIRECT:
                    #    response = await getattr(unauthorized_client, method.lower())(response.headers["location"])
                    assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"{method} {request_path} -> {response.status_code}"
            elif isinstance(route, APIWebSocketRoute):
                async with AsyncClient(base_url="http://test-api", transport=ASGIWebSocketTransport(app=app)) as client:
                    async with aconnect_ws(path, client, auth=("wrong_user", "password123")) as ws:
                        json_notification = await ws.receive_json()
                        assert json_notification['event'] == {
                            'message': 'Could not authenticate while connecting to compute WebSocket: Could not validate credentials'
                        }
