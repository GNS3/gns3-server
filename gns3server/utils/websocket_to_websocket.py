#
# Copyright (C) 2026 GNS3 Technologies Inc.
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

"""
WebSocket-to-WebSocket proxy utility functions.

Similar pattern to VNC console implementation in base_node.py:
- Bidirectional forwarding
- Binary data only (for protocols like xpra, VNC, RDP)
- Graceful error handling
"""

import asyncio
import logging
import sys
from typing import Optional

import aiohttp
from fastapi import WebSocket, status
from fastapi.websockets import WebSocketDisconnect

log = logging.getLogger(__name__)


async def websocket_proxy(
    client_ws: WebSocket,
    target_url: str,
    buffer_size: int = 65536,
    timeout: Optional[float] = None
) -> None:
    """
    Proxy binary WebSocket data between client and target WebSocket server.

    Designed for binary protocols like xpra, VNC, RDP.
    Text data is not supported.

    Args:
        client_ws: Client WebSocket connection (FastAPI)
        target_url: Target WebSocket URL to proxy to
        buffer_size: Buffer size for binary data (default: 65536)
        timeout: Connection timeout in seconds (default: None)

    Raises:
        aiohttp.ClientError: If connection to target fails
    """
    client_info = f"{client_ws.client.host}:{client_ws.client.port}"

    async def forward_client_to_target(target_ws):
        """Client → Target: Forward binary WebSocket data."""
        try:
            while True:
                data = await client_ws.receive_bytes()
                if data:
                    await target_ws.send_bytes(data)
        except WebSocketDisconnect:
            log.info(f"Client {client_info} disconnected from WebSocket proxy")
        except Exception as e:
            log.warning(f"Error forwarding client to target: {e}")

    async def forward_target_to_client(target_ws):
        """Target → Client: Forward binary WebSocket data."""
        try:
            async for msg in target_ws:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    await client_ws.send_bytes(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.warning(f"Target WebSocket error: {msg.data}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    log.info(f"Target WebSocket closed")
                    break
        except Exception as e:
            log.warning(f"Error forwarding target to client: {e}")

    try:
        # Connect to target WebSocket
        log.info(f"Connecting to target WebSocket: {target_url}")

        timeout_config = {}
        if timeout:
            timeout_config = {"timeout": aiohttp.ClientTimeout(total=timeout)}

        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(target_url, **timeout_config) as target_ws:
                log.info(f"WebSocket proxy established: {client_info} → {target_url}")

                # Run both forwarding tasks in parallel
                # Similar pattern to base_node.py VNC implementation
                if sys.version_info >= (3, 11, 0):
                    aws = [
                        asyncio.create_task(forward_client_to_target(target_ws)),
                        asyncio.create_task(forward_target_to_client(target_ws))
                    ]
                else:
                    aws = [
                        forward_client_to_target(target_ws),
                        forward_target_to_client(target_ws)
                    ]

                done, pending = await asyncio.wait(
                    aws,
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Check for exceptions
                for task in done:
                    if task.exception():
                        log.warning(
                            f"WebSocket proxy task exception: {task.exception()}"
                        )

                # Cancel pending tasks
                for task in pending:
                    task.cancel()

    except aiohttp.ClientError as e:
        log.error(f"WebSocket proxy connection error: {e}")
        await client_ws.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason=f"Proxy connection failed: {e}"
        )
    except Exception as e:
        log.error(f"WebSocket proxy unexpected error: {e}")
        await client_ws.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason=str(e)
        )
