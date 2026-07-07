#!/usr/bin/env python
#
# Copyright (C) 2024 GNS3 Technologies Inc.
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
SOCKS5 proxy server with GNS3 username/password authentication.

Implements RFC 1928 (SOCKS5) and RFC 1929 (username/password auth).
Authentication is delegated to GNS3's user repository, reusing the same
credentials as the web interface.
"""

import asyncio
import errno
import ipaddress
import logging
import struct

from sqlalchemy.ext.asyncio import AsyncSession

from gns3server.db.repositories.users import UsersRepository

log = logging.getLogger(__name__)

# SOCKS5 protocol constants
SOCKS5_VERSION = 0x05
SOCKS5_AUTH_USERNAME_PASSWORD = 0x02
SOCKS5_AUTH_NO_ACCEPTABLE = 0xFF

SOCKS5_CMD_CONNECT = 0x01

SOCKS5_ATYP_IPV4 = 0x01
SOCKS5_ATYP_DOMAIN = 0x03
SOCKS5_ATYP_IPV6 = 0x04

SOCKS5_REP_SUCCESS = 0x00
SOCKS5_REP_GENERAL_FAILURE = 0x01
SOCKS5_REP_CONNECTION_NOT_ALLOWED = 0x02
SOCKS5_REP_NETWORK_UNREACHABLE = 0x03
SOCKS5_REP_HOST_UNREACHABLE = 0x04
SOCKS5_REP_CONNECTION_REFUSED = 0x05
SOCKS5_REP_TTL_EXPIRED = 0x06
SOCKS5_REP_COMMAND_NOT_SUPPORTED = 0x07
SOCKS5_REP_ADDRESS_TYPE_NOT_SUPPORTED = 0x08

# SOCKS5 response reason phrases (for logging)
_REASON_PHRASES = {
    SOCKS5_REP_SUCCESS: "succeeded",
    SOCKS5_REP_GENERAL_FAILURE: "general failure",
    SOCKS5_REP_CONNECTION_NOT_ALLOWED: "connection not allowed",
    SOCKS5_REP_NETWORK_UNREACHABLE: "network unreachable",
    SOCKS5_REP_HOST_UNREACHABLE: "host unreachable",
    SOCKS5_REP_CONNECTION_REFUSED: "connection refused",
    SOCKS5_REP_TTL_EXPIRED: "TTL expired",
    SOCKS5_REP_COMMAND_NOT_SUPPORTED: "command not supported",
    SOCKS5_REP_ADDRESS_TYPE_NOT_SUPPORTED: "address type not supported",
}


async def start_socks5_server(host, port, app):
    """
    Start the SOCKS5 proxy server.

    :param host: Listen address
    :param port: Listen port
    :param app: FastAPI application (provides access to db engine via app.state)
    :returns: asyncio.Server instance
    """

    server = await asyncio.start_server(
        lambda r, w: _handle_client(r, w, app),
        host=host,
        port=port,
    )
    log.info(f"SOCKS5 proxy server listening on {host}:{port}")
    return server


async def _handle_client(reader, writer, app):
    """
    Handle a single SOCKS5 client connection through the full lifecycle:

      1. Greeting  — negotiate authentication method
      2. Auth      — RFC 1929 username/password authentication
      3. CONNECT   — parse target address
      4. Forward   — open TCP connection and pipe data bidirectionally
    """

    remote_addr = writer.get_extra_info("peername", ("unknown", 0))
    log.debug(f"SOCKS5 client connected from {remote_addr}")

    try:
        # --- 1. Greeting ---
        await _do_greeting(reader, writer)

        # --- 2. Authentication ---
        username = await _do_auth(reader, writer, app)
        if username is None:
            return

        # --- 3. CONNECT request ---
        target_host, target_port = await _parse_connect_request(reader, writer)
        if target_host is None:
            return

        log.info(f"SOCKS5 CONNECT {target_host}:{target_port} by user '{username}'")

        # --- 4. Connect to target ---
        try:
            remote_reader, remote_writer = await asyncio.open_connection(
                target_host, target_port
            )
        except (OSError, ConnectionError) as e:
            rep = _map_connect_error(e)
            log.warning(
                f"SOCKS5 connect to {target_host}:{target_port} failed: "
                f"{_REASON_PHRASES.get(rep, 'unknown error')} ({e})"
            )
            await _send_connect_response(writer, rep, target_host, target_port)
            return

        # Signal success to client
        await _send_connect_response(writer, SOCKS5_REP_SUCCESS, target_host, target_port)

        # --- 5. Bidirectional forwarding ---
        await _pipe(reader, writer, remote_reader, remote_writer)

    except asyncio.IncompleteReadError:
        log.debug(f"SOCKS5 client {remote_addr} disconnected prematurely")
    except (ConnectionError, OSError) as e:
        log.debug(f"SOCKS5 client {remote_addr} connection error: {e}")
    except Exception as e:
        log.error(f"Unexpected SOCKS5 error for {remote_addr}: {e}", exc_info=True)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# SOCKS5 greeting
# ---------------------------------------------------------------------------

async def _do_greeting(reader, writer):
    """
    Perform SOCKS5 greeting negotiation.

    Client sends:  [0x05, nauth, methods...]
    Server replies: [0x05, method]

    We only accept username/password authentication (method 0x02).
    """

    data = await reader.readexactly(2)
    version, nauth = struct.unpack("!BB", data)

    if version != SOCKS5_VERSION:
        writer.write(struct.pack("!BB", SOCKS5_VERSION, SOCKS5_AUTH_NO_ACCEPTABLE))
        await writer.drain()
        writer.close()
        raise ValueError(f"Invalid SOCKS5 version {version} from client")

    methods = await reader.readexactly(nauth)

    if SOCKS5_AUTH_USERNAME_PASSWORD not in methods:
        writer.write(struct.pack("!BB", SOCKS5_VERSION, SOCKS5_AUTH_NO_ACCEPTABLE))
        await writer.drain()
        writer.close()
        raise ValueError("Client does not offer username/password auth method")

    writer.write(struct.pack("!BB", SOCKS5_VERSION, SOCKS5_AUTH_USERNAME_PASSWORD))
    await writer.drain()


# ---------------------------------------------------------------------------
# RFC 1929 username / password authentication
# ---------------------------------------------------------------------------

async def _do_auth(reader, writer, app):
    """
    Authenticate the client using GNS3 user credentials.

    RFC 1929 sub-negotiation:
      Client: [0x01, ulen, username, plen, password]
      Server: [0x01, status]   (0 = success, any other = failure)

    :returns: Username string on success, None on failure
    """

    data = await reader.readexactly(2)
    version, ulen = struct.unpack("!BB", data)

    if version != 0x01:
        writer.write(struct.pack("!BB", 0x01, 0x01))
        await writer.drain()
        writer.close()
        raise ValueError(f"Invalid auth sub-negotiation version {version}")

    username_bytes = await reader.readexactly(ulen)
    username = username_bytes.decode("utf-8", errors="replace")

    plen = ord(await reader.readexactly(1))
    password_bytes = await reader.readexactly(plen)
    password = password_bytes.decode("utf-8", errors="replace")

    async with AsyncSession(app.state._db_engine, expire_on_commit=False) as db_session:
        users_repo = UsersRepository(db_session)
        user = await users_repo.authenticate_user(username, password)

    if user is None:
        log.warning(f"SOCKS5 authentication failed for user '{username}'")
        writer.write(struct.pack("!BB", 0x01, 0x01))
        await writer.drain()
        writer.close()
        return None

    log.info(f"SOCKS5 user '{username}' authenticated")
    writer.write(struct.pack("!BB", 0x01, 0x00))
    await writer.drain()
    return username


# ---------------------------------------------------------------------------
# SOCKS5 CONNECT request parsing
# ---------------------------------------------------------------------------

async def _parse_connect_request(reader, writer):
    """
    Parse a SOCKS5 CONNECT request.

    Client sends:
      [0x05, cmd, 0x00, atyp, addr, port]

    On error, an appropriate SOCKS5 error response is sent and
    (None, None) is returned.

    :returns: (target_host, target_port) tuple
    """

    data = await reader.readexactly(4)
    version, cmd, rsv, atyp = struct.unpack("!BBBB", data)

    if version != SOCKS5_VERSION:
        await _send_connect_response(writer, SOCKS5_REP_GENERAL_FAILURE)
        return None, None

    if cmd != SOCKS5_CMD_CONNECT:
        log.warning(f"SOCKS5 unsupported command {cmd}")
        await _send_connect_response(writer, SOCKS5_REP_COMMAND_NOT_SUPPORTED)
        return None, None

    if atyp == SOCKS5_ATYP_IPV4:
        addr_bytes = await reader.readexactly(4)
        target_host = str(ipaddress.IPv4Address(addr_bytes))
    elif atyp == SOCKS5_ATYP_DOMAIN:
        dlen = ord(await reader.readexactly(1))
        addr_bytes = await reader.readexactly(dlen)
        target_host = addr_bytes.decode("utf-8", errors="replace")
    elif atyp == SOCKS5_ATYP_IPV6:
        addr_bytes = await reader.readexactly(16)
        target_host = str(ipaddress.IPv6Address(addr_bytes))
    else:
        log.warning(f"SOCKS5 unsupported address type {atyp}")
        await _send_connect_response(writer, SOCKS5_REP_ADDRESS_TYPE_NOT_SUPPORTED)
        return None, None

    target_port = struct.unpack("!H", await reader.readexactly(2))[0]

    return target_host, target_port


async def _send_connect_response(writer, rep, target_host="0.0.0.0", target_port=0):
    """
    Send a SOCKS5 CONNECT response.

    Response format: [0x05, rep, 0x00, atyp, addr, port]
    """

    # Build the address field
    try:
        ip = ipaddress.ip_address(target_host)
        if isinstance(ip, ipaddress.IPv6Address):
            atyp = SOCKS5_ATYP_IPV6
            addr_bytes = ip.packed
        else:
            atyp = SOCKS5_ATYP_IPV4
            addr_bytes = ip.packed
    except ValueError:
        atyp = SOCKS5_ATYP_DOMAIN
        target_encoded = target_host.encode()
        addr_bytes = bytes([len(target_encoded)]) + target_encoded

    writer.write(
        struct.pack("!BBBB", SOCKS5_VERSION, rep, 0x00, atyp)
        + addr_bytes
        + struct.pack("!H", target_port)
    )
    await writer.drain()


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

def _map_connect_error(error):
    """
    Map a connection OSError to a SOCKS5 reply code.
    """

    err = getattr(error, "errno", None)
    if err in (errno.ENETUNREACH, errno.EHOSTUNREACH):
        return SOCKS5_REP_HOST_UNREACHABLE
    elif err in (errno.ECONNREFUSED,):
        return SOCKS5_REP_CONNECTION_REFUSED
    elif err in (errno.ETIMEDOUT,):
        return SOCKS5_REP_TTL_EXPIRED
    else:
        return SOCKS5_REP_GENERAL_FAILURE


# ---------------------------------------------------------------------------
# Bidirectional TCP forwarding
# ---------------------------------------------------------------------------

async def _pipe(client_reader, client_writer, remote_reader, remote_writer):
    """
    Bidirectional TCP forwarding between the SOCKS5 client and the target.

    Two concurrent tasks copy data in each direction.  When one side
    closes (or errors), the other is cancelled and both sockets are
    closed.
    """

    async def _forward(src_reader, dst_writer, label):
        try:
            while True:
                data = await src_reader.read(65536)
                if not data:
                    log.debug(f"SOCKS5 {label}: connection closed by peer")
                    break
                dst_writer.write(data)
                await dst_writer.drain()
        except (ConnectionError, OSError) as e:
            log.debug(f"SOCKS5 {label}: {e}")
        finally:
            try:
                dst_writer.close()
            except Exception:
                pass

    tasks = [
        asyncio.create_task(_forward(client_reader, remote_writer, "c→t")),
        asyncio.create_task(_forward(remote_reader, client_writer, "t→c")),
    ]

    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for task in pending:
        task.cancel()

    # Make sure both writers are closed
    try:
        remote_writer.close()
    except Exception:
        pass
    try:
        client_writer.close()
    except Exception:
        pass
