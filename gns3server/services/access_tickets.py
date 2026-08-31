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
Short-lived access tickets.

An access ticket is a short random string ("gns3t_" + 16 urlsafe chars) that
replaces the long JWTs previously embedded in URLs and curl commands returned
to LLM clients, which reliably corrupted the ~200-char JWT when retyping it
into a shell command. The ticket carries no information itself — the server
remembers what it maps to, which is what makes a 96-bit random string a
sufficient credential.

A ticket is bound to exactly one target, in one of two modes:

- node binding (project_id + node_id): redeemable on that node's console
  WebSocket endpoints (console/ws and console/vnc share the binding),
  validated against the route's path parameters.
- path binding (exact resource path): redeemable on one REST resource path
  (e.g. a capture file download or a symbol image), validated against
  request.url.path.

Tickets are multi-use within their TTL, so clients that reconnect keep
working. Redemption re-checks the minting user's token_version, so logging
out invalidates outstanding tickets just like it invalidates JWTs.
"""

import logging
import secrets
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

# Distinguishes tickets from JWTs (which contain dots) and API keys ("gns3_")
TICKET_PREFIX = "gns3t_"
DEFAULT_TICKET_TTL = 600  # seconds


@dataclass
class AccessTicket:
    username: str
    token_version: int
    project_id: Optional[str] = None  # node binding: console WebSocket endpoints
    node_id: Optional[str] = None
    path: Optional[str] = None  # path binding: one exact REST resource path
    expires_at: float = 0.0  # time.monotonic() based


class AccessTicketService:
    """
    In-memory store for access tickets.

    Single-process asyncio app: minting (MCP tool handlers, via worker
    threads) and redemption (auth dependencies, event loop) share one dict.
    dict get/set/del are atomic under the GIL and keys are random, so no
    locking is needed. Tickets vanish on restart — clients just request a
    new one.
    """

    def __init__(self) -> None:
        self._tickets: dict[str, AccessTicket] = {}

    def mint(
        self,
        username: str,
        token_version: int,
        project_id: Optional[str] = None,
        node_id: Optional[str] = None,
        path: Optional[str] = None,
        ttl: int = DEFAULT_TICKET_TTL,
    ) -> str:
        # 12 random bytes → 16 urlsafe chars (~96 bits); comfortably
        # unguessable within the 10-minute window and short enough that
        # LLM clients copy it without corruption.
        ticket = TICKET_PREFIX + secrets.token_urlsafe(12)
        self._sweep_expired()
        self._tickets[ticket] = AccessTicket(
            username=username,
            token_version=token_version,
            project_id=project_id,
            node_id=node_id,
            path=path,
            expires_at=time.monotonic() + ttl,
        )
        return ticket

    def redeem(self, ticket: str, path_params: dict) -> Optional[AccessTicket]:
        """
        Validate a node-bound ticket against a WebSocket route.

        Returns the ticket record if valid, None otherwise. The route's path
        parameters must match the ticket's binding, which confines a ticket
        to the node's console endpoints — routes without a node_id path
        parameter (notifications, web wireshark, …) always fail the binding,
        and so do path-bound (REST) tickets.
        """

        record = self._get_valid(ticket)
        if record is None:
            return None
        if record.node_id is None or record.path is not None:
            return None
        if path_params.get("project_id") != record.project_id or path_params.get("node_id") != record.node_id:
            return None
        return record

    def redeem_for_path(self, ticket: str, path: str) -> Optional[AccessTicket]:
        """
        Validate a path-bound ticket against a REST resource path.

        The path must match exactly — a ticket minted for one capture file
        download cannot be replayed against any other resource.
        """

        record = self._get_valid(ticket)
        if record is None:
            return None
        if record.path is None or record.path != path:
            return None
        return record

    def _get_valid(self, ticket: str) -> Optional[AccessTicket]:
        record = self._tickets.get(ticket)
        if record is None:
            return None
        if time.monotonic() >= record.expires_at:
            self._tickets.pop(ticket, None)
            return None
        return record

    def _sweep_expired(self) -> None:
        now = time.monotonic()
        for ticket in [t for t, record in self._tickets.items() if now >= record.expires_at]:
            del self._tickets[ticket]
