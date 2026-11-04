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

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gns3server.api.routes.compute import compute_api
from gns3server.api.routes.compute.notifications import project_ws_notifications


@pytest.mark.asyncio
async def test_compute_ws_stops_when_app_is_exiting() -> None:

    # plain assignment: see the note in test_notifications.py — monkeypatch
    # cannot round-trip attributes of Starlette's State on pytest 9.2+
    compute_api.state.exiting = True
    try:
        websocket = MagicMock()
        websocket.app = compute_api
        websocket.client = SimpleNamespace(host="127.0.0.1", port=1000)
        websocket.send_text = AsyncMock()

        await asyncio.wait_for(project_ws_notifications(websocket=websocket), timeout=1)

        websocket.send_text.assert_not_awaited()
    finally:
        compute_api.state.exiting = False
