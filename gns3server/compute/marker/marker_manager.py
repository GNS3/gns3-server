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
import socket

from gns3server.compute.marker.marker_listener import MarkerListener
from gns3server.compute.notification_manager import NotificationManager

log = logging.getLogger(__name__)


class MarkerManager:
    """
    Singleton owning the compute-side UDP sink for ubridge ``MARK`` signals and
    the registry that maps each ``(node_id, filter_name)`` back to its
    ``(project_id, link_id, tag)``.

    The registry is populated when a marker is created on a link (the compute
    endpoint has project_id + node_id from its route path and link_id/name/tag
    from the request body) and cleared when the marker is deleted or the project
    closed. At signal time it is an O(1) lookup — no node-table scan, and the
    signal payload is untouched.

    One listener per compute process serves every ubridge on that host; source
    ubridges are disambiguated by ``node=<id>`` (UUID, globally unique).
    """

    def __init__(self):

        self._listener = None
        self._transport = None
        self._host = None
        self._port = None
        # Flat lookup: (node_id, filter_name) -> {"project_id", "link_id", "tag"}
        self._entries = {}
        # Reverse index for O(1) per-project teardown: project_id -> set of keys
        self._by_project = {}

    @property
    def host(self):
        """The host the UDP sink is reachable on (for ``marker sink``)."""
        return self._host

    @property
    def port(self):
        """The UDP port the sink is bound on (for ``marker sink``)."""
        return self._port

    @property
    def running(self):
        return self._transport is not None

    async def start(self, host="127.0.0.1", port=0):
        """
        Bind the UDP sink. ``port=0`` lets the OS choose a free port, which is
        then read back and exposed via :attr:`port` for ``marker sink`` commands.
        """

        if self.running:
            return
        loop = asyncio.get_running_loop()
        self._listener = MarkerListener(self)

        def _configure_transport(transport):
            sock = transport.get_extra_info("socket")
            if sock is not None:
                # Raise the UDP receive buffer from the default ~208 KB to 8 MB
                # so that 1000+ uBridge processes can burst marker.match signals
                # without kernel-side datagram loss.
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)

        try:
            self._transport, _ = await loop.create_datagram_endpoint(
                lambda: self._listener, local_addr=(host, port)
            )
            _configure_transport(self._transport)
        except OSError:
            if port != 0:
                log.warning(
                    "Marker listener: port %s unavailable, falling back to OS-assigned port", port
                )
                try:
                    self._transport, _ = await loop.create_datagram_endpoint(
                        lambda: self._listener, local_addr=(host, 0)
                    )
                    _configure_transport(self._transport)
                except OSError as e:
                    log.error(
                        "Marker listener startup failed: %s. Traffic insight signals are unavailable.", e
                    )
                    self._listener = None
                    return
            else:
                log.error(
                    "Marker listener startup failed on OS-assigned port. Traffic insight signals are unavailable."
                )
                self._listener = None
                return
        sock = self._transport.get_extra_info("socket")
        self._host = host
        self._port = sock.getsockname()[1] if sock else port
        log.info("Marker signal sink listening on %s:%s", self._host, self._port)
        self._stats_task = asyncio.create_task(self._log_stats())

    async def _log_stats(self):
        """Log marker.match throughput every 10 s so operators can tell whether
        the single UDP sink keeps up with the aggregated uBridge traffic."""
        while self.running:
            await asyncio.sleep(10)
            listener = self._listener
            if listener is None:
                break
            received, errors = listener._received, listener._errors
            listener._received = 0
            listener._errors = 0
            if received:
                log.info(
                    "marker sink: %d matches (%.0f/s), %d errors in last 10s",
                    received, received / 10.0, errors,
                )

    async def stop(self):
        """Close the UDP sink and drop the whole registry."""

        if hasattr(self, "_stats_task") and self._stats_task:
            self._stats_task.cancel()
            self._stats_task = None
        if self._transport:
            self._transport.close()
            self._transport = None
        self._listener = None
        self._entries.clear()
        self._by_project.clear()
        self._host = None
        self._port = None

    def register(self, project_id, node_id, filter_name, link_id, tag=None):
        """
        Record that ``filter_name`` on ``node_id`` belongs to ``project_id`` /
        ``link_id``. Called from the compute marker-start endpoint.

        Re-registering the same key updates the stored tag (e.g. on re-add).
        """

        key = (node_id, filter_name)
        self._entries[key] = {"project_id": project_id, "link_id": link_id, "tag": tag}
        self._by_project.setdefault(project_id, set()).add(key)

    def unregister(self, node_id, filter_name):
        """Forget a single marker. Returns True if something was removed."""

        key = (node_id, filter_name)
        entry = self._entries.pop(key, None)
        if entry is None:
            return False
        project_entries = self._by_project.get(entry["project_id"])
        if project_entries is not None:
            project_entries.discard(key)
            if not project_entries:
                self._by_project.pop(entry["project_id"], None)
        return True

    def unregister_project(self, project_id):
        """Drop every marker belonging to ``project_id`` (project close)."""

        keys = self._by_project.pop(project_id, None)
        if not keys:
            return
        for key in keys:
            self._entries.pop(key, None)

    def lookup(self, node_id, filter_name):
        """
        O(1) resolution of an incoming signal to its project/link/tag.

        :returns: (project_id, link_id, tag) or (None, None, None) on miss.
        """

        entry = self._entries.get((node_id, filter_name))
        if entry is None:
            return None, None, None
        return entry["project_id"], entry["link_id"], entry["tag"]

    def emit_match(self, project_id, event):
        """
        Forward a parsed match as a project-scoped ``marker.match`` notification.
        Flows compute -> controller dispatch -> project_emit -> web UI WS.
        """

        NotificationManager.instance().emit("marker.match", event, project_id=project_id)

    _instance = None

    @staticmethod
    def instance():
        if MarkerManager._instance is None:
            MarkerManager._instance = MarkerManager()
        return MarkerManager._instance

    @staticmethod
    def reset():
        MarkerManager._instance = None
