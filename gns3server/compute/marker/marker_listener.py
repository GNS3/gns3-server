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

import asyncio
import logging

log = logging.getLogger(__name__)


class MarkerListener(asyncio.DatagramProtocol):
    """
    Receives ubridge ``MARK`` signal datagrams and turns each into a
    ``marker.match`` notification.

    Signal format (one datagram per match, ASCII)::

        MARK <sec.usec> node=<id> filter=<name> tag=<tag> len=<n> [dir=<tx|rx>]\\n

    The signal carries metadata only (no packet bytes). ``dir`` is optional and
    additive: uBridge stamps it from the ingress NIO of the matched packet to
    indicate travel direction relative to the capture node (the ``node=<id>``
    above) — ``tx`` = the capture node is sending (ingressed on the device-side
    NIO), ``rx`` = it is receiving (ingressed on the link-side NIO). Older
    uBridge builds omit it, so the listener leaves ``dir`` unset and consumers
    fall back to undirected rendering. Unknown keys are always ignored, so the
    field ships safely with no version coupling.

    The compute-side
    :class:`~gns3server.compute.marker.marker_manager.MarkerManager` registry
    resolves ``(node_id, filter_name)`` to ``(project_id, link_id, tag)`` so the
    event can be emitted on the right project-scoped notification stream.
    """

    def __init__(self, manager):
        # MarkerManager owns this listener and the registry.
        self._manager = manager
        self.transport = None
        self._received = 0
        self._errors = 0

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self._received += 1
        try:
            self._handle(data)
        except Exception:
            self._errors += 1
            # Never let a malformed datagram kill the listener.
            log.exception("Failed to process MARK datagram from %s: %r", addr, data)

    def _handle(self, data):
        line = data.decode("utf-8", errors="replace").strip()
        if not line.startswith("MARK"):
            return

        parts = line.split()
        # parts[0] == "MARK"; parts[1] == "<sec.usec>"
        if len(parts) < 2:
            return

        try:
            ts = float(parts[1])
        except ValueError:
            log.warning("Ignoring MARK signal with bad timestamp: %r", line)
            return

        kv = {}
        for token in parts[2:]:
            if "=" in token:
                key, value = token.split("=", 1)
                kv[key] = value

        node_id = kv.get("node")
        filter_name = kv.get("filter")
        if not node_id or not filter_name:
            return

        # "-" means the field was unset on the ubridge side (see contract §3.3).
        link = kv.get("link")
        tag = kv.get("tag")
        length = kv.get("len")
        # Travel direction relative to the capture node (the node=<id> above):
        # "tx" = capture node is sending (matched packet ingressed on the
        # device-side NIO), "rx" = it is receiving (link-side NIO). Older
        # uBridge builds omit dir; None here lets consumers render undirected.
        direction = kv.get("dir")

        project_id, link_id, registered_tag = self._manager.lookup(node_id, filter_name)
        if project_id is None:
            log.warning(
                "MARK signal for unregistered node=%s filter=%s, dropping", node_id, filter_name
            )
            return

        # `link=` is the authoritative per-link id (opaque, set by gns3server at
        # filter install time). It disambiguates signals that share a node+filter
        # across several links; fall back to the registry's link only for legacy
        # signals that carry no `link=`.
        signal_link = link if link and link != "-" else None

        event = {
            "project_id": project_id,
            "node_id": node_id,
            "link_id": signal_link or link_id,
            "filter": filter_name,
            # Prefer the value carried in the signal; fall back to the one we registered.
            "tag": tag if tag and tag != "-" else registered_tag,
            "ts": ts,
            "len": int(length) if length and length.isdigit() else 0,
            # Travel direction relative to the capture node (node_id above);
            # None when the signal carries none (older uBridge) — undirected.
            "dir": direction,
        }
        self._manager.emit_match(project_id, event)
