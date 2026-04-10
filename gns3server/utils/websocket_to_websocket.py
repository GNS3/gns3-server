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
from starlette.websockets import WebSocket as StarletteWebSocket

log = logging.getLogger(__name__)


async def websocket_proxy(
    client_ws: WebSocket,
    target_url: str,
    requested_protocols: list = None,
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
        requested_protocols: List of subprotocols requested by client (default: ["binary"])
        buffer_size: Buffer size for binary data (default: 65536)
        timeout: Connection timeout in seconds (default: None)

    Raises:
        aiohttp.ClientError: If connection to target fails
    """
    client_info = f"{client_ws.client.host}:{client_ws.client.port}"

    async def forward_client_to_target(target_ws):
        """Client → Target: Forward binary WebSocket data."""
        log.info(f"forward_client_to_target: started")
        try:
            while True:
                log.info(f"forward_client_to_target: waiting for client data")
                data = await client_ws.receive_bytes()
                log.info(f"forward_client_to_target: received {len(data)} bytes from client")
                if data:
                    await target_ws.send_bytes(data)
        except WebSocketDisconnect:
            log.info(f"Client {client_info} disconnected from WebSocket proxy")
        except Exception as e:
            log.warning(f"Error forwarding client to target: {e}")

    async def forward_target_to_client(target_ws):
        """Target → Client: Forward binary WebSocket data."""
        log.info(f"forward_target_to_client: started, about to iterate")
        try:
            async for msg in target_ws:
                log.info(f"forward_target_to_client: got message type={msg.type}")
                if msg.type == aiohttp.WSMsgType.BINARY:
                    try:
                        await client_ws.send_bytes(msg.data)
                    except Exception as e:
                        log.warning(f"Failed to send to client (possibly disconnected): {e}")
                        break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.warning(f"Target WebSocket error: {msg.data}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    log.info(f"Target WebSocket closed")
                    # Don't try to forward close to client if already disconnected
                    break
            log.info(f"forward_target_to_client: iteration ended")
        except Exception as e:
            log.warning(f"Error forwarding target to client: {e}")

    try:
        # Connect to target WebSocket FIRST to negotiate subprotocol
        log.info(f"Connecting to target WebSocket: {target_url}")

        # Use requested protocols from client (usually "binary" for xpra)
        subprotocols = requested_protocols or ["binary"]
        log.info(f"Client requested subprotocols: {subprotocols}")

        timeout_config = {}
        if timeout:
            timeout_config = {"timeout": aiohttp.ClientTimeout(total=timeout)}

        async with aiohttp.ClientSession() as session:
            log.info(f"About to ws_connect to {target_url}")
            ws_conn = session.ws_connect(target_url, protocols=subprotocols, **timeout_config)
            log.info(f"ws_connect coroutine created, about to enter")
            async with ws_conn as target_ws:
                negotiated_protocol = target_ws.protocol
                log.info(f"Target WebSocket negotiated protocol: {negotiated_protocol}")
                log.info(f"target_ws.closed = {target_ws.closed}")

                # Note: FastAPI has already accepted the client WebSocket connection
                # The subprotocol should have been set on the websocket object before
                # the route handler was called. We just log it here for debugging.
                log.info(f"Client WebSocket subprotocol: {getattr(client_ws, 'subprotocol', None)}")
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

                log.info(f"About to call asyncio.wait with {len(aws)} tasks")
                try:
                    done, pending = await asyncio.wait(
                        aws,
                        return_when=asyncio.ALL_COMPLETED
                    )
                    log.info(f"asyncio.wait returned. done={len(done)}, pending={len(pending)}")
                except Exception as e:
                    log.error(f"asyncio.wait raised exception: {e}")
                log.info(f"After asyncio.wait check")

                # Check for exceptions
                for task in done:
                    if task.exception():
                        log.warning(
                            f"WebSocket proxy task exception: {task.exception()}"
                        )

                # Cancel pending tasks
                for task in pending:
                    log.info(f"Cancelling pending task")
                    task.cancel()

                log.info(f"Cleanup complete, exiting websocket_proxy")

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


async def websocket_proxy_with_manual_accept(
    client_ws: StarletteWebSocket,
    target_url: str,
    requested_protocols: list = None,
    buffer_size: int = 65536,
    timeout: Optional[float] = None
) -> None:
    """
    Proxy binary WebSocket data between client and target WebSocket server.

    This version manually accepts the client WebSocket connection after negotiating
    the subprotocol with the backend server. This is required for protocols like xpra
    that depend on proper subprotocol negotiation.

    Args:
        client_ws: Client WebSocket connection (Starlette WebSocket)
        target_url: Target WebSocket URL to proxy to
        requested_protocols: List of subprotocols requested by client (default: ["binary"])
        buffer_size: Buffer size for binary data (default: 65536)
        timeout: Connection timeout in seconds (default: None)

    Raises:
        aiohttp.ClientError: If connection to target fails
    """
    client_info = f"{client_ws.client.host}:{client_ws.client.port}" if hasattr(client_ws, 'client') else "unknown"

    async def forward_client_to_target(target_ws):
        """Client → Target: Forward binary WebSocket data."""
        log.info(f"forward_client_to_target: started")
        try:
            while True:
                log.info(f"forward_client_to_target: waiting for client data")
                data = await client_ws.receive_bytes()
                log.info(f"forward_client_to_target: received {len(data)} bytes from client")
                if data:
                    await target_ws.send_bytes(data)
        except Exception as e:
            log.info(f"Client disconnected or error: {e}")
            raise

    async def forward_target_to_client(target_ws):
        """Target → Client: Forward binary WebSocket data."""
        log.info(f"forward_target_to_client: started, about to iterate")
        try:
            async for msg in target_ws:
                log.info(f"forward_target_to_client: got message type={msg.type}")
                if msg.type == aiohttp.WSMsgType.BINARY:
                    try:
                        await client_ws.send_bytes(msg.data)
                    except Exception as e:
                        log.warning(f"Failed to send to client (possibly disconnected): {e}")
                        break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.warning(f"Target WebSocket error: {msg.data}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    log.info(f"Target WebSocket closed")
                    break
            log.info(f"forward_target_to_client: iteration ended")
        except Exception as e:
            log.warning(f"Error forwarding target to client: {e}")

    try:
        # Connect to target WebSocket FIRST to negotiate subprotocol
        log.info(f"Connecting to target WebSocket: {target_url}")

        # Use requested protocols from client (usually "binary" for xpra)
        subprotocols = requested_protocols or ["binary"]
        log.info(f"Client requested subprotocols: {subprotocols}")

        timeout_config = {}
        if timeout:
            timeout_config = {"timeout": aiohttp.ClientTimeout(total=timeout)}

        async with aiohttp.ClientSession() as session:
            log.info(f"About to ws_connect to {target_url}")
            ws_conn = session.ws_connect(target_url, protocols=subprotocols, **timeout_config)
            log.info(f"ws_connect coroutine created, about to enter")
            async with ws_conn as target_ws:
                negotiated_protocol = target_ws.protocol
                log.info(f"Target WebSocket negotiated protocol: {negotiated_protocol}")
                log.info(f"target_ws.closed = {target_ws.closed}")

                # Accept client WebSocket with the negotiated subprotocol
                # This is CRITICAL for xpra to work properly
                log.info(f"Accepting client WebSocket with subprotocol: {negotiated_protocol}")
                await client_ws.accept(subprotocol=negotiated_protocol)
                log.info(f"Client WebSocket accepted")

                log.info(f"WebSocket proxy established: {client_info} → {target_url}")

                # Run both forwarding tasks in parallel
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

                log.info(f"About to call asyncio.wait with {len(aws)} tasks")
                try:
                    done, pending = await asyncio.wait(
                        aws,
                        return_when=asyncio.ALL_COMPLETED
                    )
                    log.info(f"asyncio.wait returned. done={len(done)}, pending={len(pending)}")
                except Exception as e:
                    log.error(f"asyncio.wait raised exception: {e}")
                log.info(f"After asyncio.wait check")

                # Check for exceptions
                for task in done:
                    if task.exception():
                        log.warning(
                            f"WebSocket proxy task exception: {task.exception()}"
                        )

                # Cancel pending tasks
                for task in pending:
                    log.info(f"Cancelling pending task")
                    task.cancel()

                log.info(f"Cleanup complete, exiting websocket_proxy_with_manual_accept")

    except aiohttp.ClientError as e:
        log.error(f"WebSocket proxy connection error: {e}")
        try:
            await client_ws.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
    except Exception as e:
        log.error(f"WebSocket proxy unexpected error: {e}")
        try:
            await client_ws.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
