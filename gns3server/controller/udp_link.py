#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

from .controller_error import ControllerError, ControllerNotFoundError
from .link import Link, _UNSET
from .node_types import BUILTIN_NODE_TYPES
from gns3server.utils.packet_filter_validation import validate_bpf_syntax, FilterValidationError

# Node types that can host a marker (have a uBridge bridge to attach the
# `mark` filter to).  Mirrors _get_filter_node in link.py, minus "nat"
# (which has no uBridge) and "ethernet_hub" (still Dynamips-hosted, no
# uBridge of its own).  "ethernet_switch" hosts markers on the per-port
# uBridge relays of its brctl kernel-bridge backend.
_MARKER_CAPABLE_TYPES = frozenset({
    "vpcs", "qemu", "docker", "iou", "dynamips", "cloud", "ethernet_switch",
})


log = logging.getLogger(__name__)


class UDPLink(Link):
    def __init__(self, project, link_id=None):
        super().__init__(project, link_id=link_id)
        self._created = False
        self._link_data = []

    @property
    def debug_link_data(self):
        """
        Use for the debug exports
        """
        return self._link_data
    
    def _get_node_filters(self, node1, node2):
        """
        Determine which node gets the active filters applied.

        :returns: Tuple of (node1_filters, node2_filters)
        """
        filter_node = self._get_filter_node()
        return (
            self.get_active_filters() if filter_node == node1 else {},
            self.get_active_filters() if filter_node == node2 else {},
        )

    def _markers_for_node(self, node):
        """
        Marker specs (name -> {bpf, tag, link_id, direction, data_link_type,
        enabled}) for the markers whose capture side is ``node``. Routed by
        capture_node_id so a marker only rides the NIO of the node whose uBridge
        will host it. A disabled marker is included (installed then turned
        ``off`` at uBridge, not dropped) so the UI can toggle it instantly
        without an NIO rebuild.
        """
        return {
            name: {"bpf": m["bpf"], "tag": m.get("tag"), "link_id": self._id,
                   "direction": m.get("direction"),
                   "data_link_type": m.get("data_link_type", "DLT_EN10MB"),
                   "enabled": m.get("enabled", True)}
            for name, m in self._markers.items()
            if m.get("capture_node_id") == node.id
        }

    def _get_node_markers(self, node1, node2):
        """
        Determine which node gets which markers applied.

        :returns: Tuple of (node1_markers, node2_markers)
        """
        return self._markers_for_node(node1), self._markers_for_node(node2)

    async def _prepare(self):
        """
        Local-only link setup: resolve peer addresses, reserve UDP ports and
        build the two NIO tunnel specs (``self._link_data``). No NIO is sent to
        the computes — the caller decides how to dispatch them (one-by-one via
        :meth:`create`, or batched via the project-open bulk path).

        :returns: list of two ``(node, adapter_number, port_number, nio_data)``
            tuples, ready to be POSTed to each node's compute.
        """

        # Start from a clean slate: reset() re-creates the link on the same
        # object (delete() + create()), and _commit_nios()/update() always
        # address indices 0/1 — appending onto the previous run's entries
        # would re-commit the stale (already released) port pair and orphan
        # the freshly allocated ports.
        self._link_data = []

        node1 = self._nodes[0]["node"]
        adapter_number1 = self._nodes[0]["adapter_number"]
        port_number1 = self._nodes[0]["port_number"]
        node2 = self._nodes[1]["node"]
        adapter_number2 = self._nodes[1]["adapter_number"]
        port_number2 = self._nodes[1]["port_number"]

        # Get an IP allowing communication between both host
        try:
            (node1_host, node2_host) = await node1.compute.get_ip_on_same_subnet(node2.compute)
        except ValueError as e:
            raise ControllerError(f"Cannot get an IP address on same subnet: {e}")

        # Reserve a UDP port on both sides in parallel. Pre-allocated ports
        # (used during batch project loading) are popped from memory; otherwise
        # each side falls back to a single HTTP round-trip to its compute.
        async def _allocate_port(compute):
            port = self._project.pop_preallocated_udp_port(compute.id)
            if port is not None:
                return port
            response = await compute.post(f"/projects/{self._project.id}/ports/udp")
            return response.json["udp_port"]

        self._node1_port, self._node2_port = await asyncio.gather(
            _allocate_port(node1.compute), _allocate_port(node2.compute)
        )

        node1_filters, node2_filters = self._get_node_filters(node1, node2)
        node1_markers, node2_markers = self._get_node_markers(node1, node2)

        # Build the tunnel specs for both sides. Index 0 is always node1 so
        # that update()/delete() keep addressing self._link_data[0]/[1].
        self._link_data.append(
            {
                "lport": self._node1_port,
                "rhost": node2_host,
                "rport": self._node2_port,
                "type": "nio_udp",
                "filters": node1_filters,
                "markers": node1_markers,
                "suspend": self._suspended,
            }
        )
        self._link_data.append(
            {
                "lport": self._node2_port,
                "rhost": node1_host,
                "rport": self._node1_port,
                "type": "nio_udp",
                "filters": node2_filters,
                "markers": node2_markers,
                "suspend": self._suspended,
            }
        )

        return [
            (node1, adapter_number1, port_number1, self._link_data[0]),
            (node2, adapter_number2, port_number2, self._link_data[1]),
        ]

    async def _commit_nios(self, entries):
        """
        Send the two NIO tunnel POSTs in parallel and roll back on failure.

        :param entries: the two ``(node, adapter_number, port_number, nio_data)``
            tuples returned by :meth:`_prepare`.
        """

        (node1, adapter_number1, port_number1, nio_data1), \
            (node2, adapter_number2, port_number2, nio_data2) = entries

        # The two ends are independent once the ports and peer addresses are
        # known — each node talks to its own compute/uBridge with no shared
        # lock between them — so the two POSTs overlap. If either fails, roll
        # back whichever side succeeded before re-raising the first error.
        results = await asyncio.gather(
            node1.post(
                f"/adapters/{adapter_number1}/ports/{port_number1}/nio", data=nio_data1, timeout=120
            ),
            node2.post(
                f"/adapters/{adapter_number2}/ports/{port_number2}/nio", data=nio_data2, timeout=120
            ),
            return_exceptions=True,
        )
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            cleanup = []
            if not isinstance(results[0], Exception):
                cleanup.append(
                    node1.delete(f"/adapters/{adapter_number1}/ports/{port_number1}/nio", timeout=120)
                )
            if not isinstance(results[1], Exception):
                cleanup.append(
                    node2.delete(f"/adapters/{adapter_number2}/ports/{port_number2}/nio", timeout=120)
                )
            if cleanup:
                await asyncio.gather(*cleanup, return_exceptions=True)
            raise errors[0]
        self._created = True

    async def create(self):
        """
        Create the link on the nodes (interactive path: prepare + commit).
        """

        entries = await self._prepare()
        await self._commit_nios(entries)
        # New links automatically inherit every active project-level marker
        # definition so the user doesn't have to reconfigure.
        await self._project.apply_defs_to_new_link(self)

    async def update(self):
        """
        Update the link on the nodes
        """

        if len(self._link_data) == 0:
            return
        node1 = self._nodes[0]["node"]
        node2 = self._nodes[1]["node"]

        node1_filters, node2_filters = self._get_node_filters(node1, node2)
        node1_markers, node2_markers = self._get_node_markers(node1, node2)

        adapter_number1 = self._nodes[0]["adapter_number"]
        port_number1 = self._nodes[0]["port_number"]
        self._link_data[0]["filters"] = node1_filters
        self._link_data[0]["markers"] = node1_markers
        self._link_data[0]["suspend"] = self._suspended
        # The Ethernet hub is still Dynamips-hosted (no uBridge of its own and
        # no PUT NIO route) — keep skipping its side. Every other node type,
        # including the brctl Ethernet switch, re-applies via the NIO update.
        if node1.node_type != "ethernet_hub":
            await node1.put(
                f"/adapters/{adapter_number1}/ports/{port_number1}/nio", data=self._link_data[0], timeout=120
            )

        adapter_number2 = self._nodes[1]["adapter_number"]
        port_number2 = self._nodes[1]["port_number"]
        self._link_data[1]["filters"] = node2_filters
        self._link_data[1]["markers"] = node2_markers
        self._link_data[1]["suspend"] = self._suspended
        if node2.node_type != "ethernet_hub":
            await node2.put(
                f"/adapters/{adapter_number2}/ports/{port_number2}/nio", data=self._link_data[1], timeout=221
            )

    async def delete(self):
        """
        Delete the link and free the resources
        """
        if not self._created:
            return
        try:
            node1 = self._nodes[0]["node"]
            adapter_number1 = self._nodes[0]["adapter_number"]
            port_number1 = self._nodes[0]["port_number"]
        except IndexError:
            return
        try:
            await node1.delete(f"/adapters/{adapter_number1}/ports/{port_number1}/nio", timeout=120)
        # If the node is already deleted (user selected multiple element and delete all in the same time)
        except ControllerNotFoundError:
            pass

        try:
            node2 = self._nodes[1]["node"]
            adapter_number2 = self._nodes[1]["adapter_number"]
            port_number2 = self._nodes[1]["port_number"]
        except IndexError:
            return
        try:
            await node2.delete(f"/adapters/{adapter_number2}/ports/{port_number2}/nio", timeout=120)
        # If the node is already deleted (user selected multiple element and delete all in the same time)
        except ControllerNotFoundError:
            pass
        await super().delete()

    async def reset(self):
        """
        Reset the link.
        """

        # recreate the link on the compute
        await self.delete()
        await self.create()

    async def start_capture(self, data_link_type="DLT_EN10MB", capture_file_name=None, wireshark=False, jwt_token=None):
        """
        Start capture on a link
        """
        if not capture_file_name:
            capture_file_name = self.default_capture_file_name()
        self._capture_node = self._choose_capture_side()
        data = {"capture_file_name": capture_file_name, "data_link_type": data_link_type}
        await self._capture_node["node"].post(
            "/adapters/{adapter_number}/ports/{port_number}/capture/start".format(
                adapter_number=self._capture_node["adapter_number"], port_number=self._capture_node["port_number"]
            ),
            data=data,
        )
        await super().start_capture(data_link_type=data_link_type, capture_file_name=capture_file_name, wireshark=wireshark, jwt_token=jwt_token)

    async def stop_capture(self):
        """
        Stop capture on a link
        """
        if self._capture_node:
            await self._capture_node["node"].post(
                "/adapters/{adapter_number}/ports/{port_number}/capture/stop".format(
                    adapter_number=self._capture_node["adapter_number"], port_number=self._capture_node["port_number"]
                )
            )
            self._capture_node = None
        await super().stop_capture()

    def _choose_capture_side(self):
        """
        Run capture on the best candidate.

        The ideal candidate is a node who on controller server and always
        running (capture will not be cut off)

        :returns: Node where the capture should run
        """

        for node in self._nodes:
            if (
                node["node"].compute.id == "local"
                and node["node"].node_type in BUILTIN_NODE_TYPES
                and node["node"].status == "started"
            ):
                return node

        for node in self._nodes:
            if node["node"].node_type in BUILTIN_NODE_TYPES and node["node"].status == "started":
                return node

        for node in self._nodes:
            if node["node"].compute.id == "local" and node["node"].status == "started":
                return node

        for node in self._nodes:
            if node["node"].node_type and node["node"].status == "started":
                return node

        raise ControllerError("Cannot capture because there is no running device on this link")

    def _choose_marker_side(self):
        """
        Pick the node that will host the marker, mirroring ``_get_filter_node``
        in link.py.  Only types with a uBridge bridge (``_MARKER_CAPABLE_TYPES``)
        are eligible.  A running node is preferred, but a stopped one is
        accepted — like packet filters, the marker is stored on the NIO and
        applied when the node starts.
        """

        # Prefer started.
        for node in self._nodes:
            if (
                node["node"].node_type in _MARKER_CAPABLE_TYPES
                and node["node"].status == "started"
            ):
                return node

        # Accept stopped but capable (marker rides NIO, applied at start).
        for node in self._nodes:
            if node["node"].node_type in _MARKER_CAPABLE_TYPES:
                return node

        raise ControllerError(
            "Cannot add marker because no device on this link supports "
            "traffic insight"
        )

    def _node_by_id(self, node_id):
        """
        Resolve a caller-chosen capture node by id, validating it is an
        endpoint of this link and marker-capable. Used when the caller
        (REST/MCP) explicitly pins the observer side instead of letting
        ``_choose_marker_side`` auto-pick.

        :param node_id: node id (UUID or str) the caller requested
        :returns: a ``self._nodes`` entry (node/adapter_number/port_number)
        """

        target = str(node_id)
        for node in self._nodes:
            if str(node["node"].id) != target:
                continue
            if node["node"].node_type not in _MARKER_CAPABLE_TYPES:
                raise ControllerError(
                    f"Node {node_id} ({node['node'].node_type}) cannot host a "
                    f"marker — no uBridge bridge to attach the filter to"
                )
            return node
        raise ControllerNotFoundError(
            f"Node {node_id} is not an endpoint of link {self._id}"
        )

    async def node_updated(self, node):
        """
        Called when a node member of the link is updated
        """
        if self._capture_node and node == self._capture_node["node"] and node.status != "started":
            await self.stop_capture()
        # Marker clean-up is *not* done on node stop — markers are a persistent
        # link-scoped feature that recovers via NIO on restart (see
        # _ubridge_apply_markers in add_ubridge_udp_connection).  The user
        # explicitly deletes a marker via the REST API, and a marker is torn
        # down automatically only when its link is deleted.

    async def start_marker(self, name, bpf, tag=None, direction=None, data_link_type="DLT_EN10MB", capture_node_id=None, color=None, highlight_duration=None, enabled=True, inherited_from=None, dump=True, memory_only=False):
        """
        Attach a traffic-insight marker to this link.

        State-only model (mirrors ``update_filters``): record the marker in
        ``_markers`` (with its capture-side node id for NIO routing), then push
        via ``self.update()`` so it rides the NIO and is applied by
        ``_ubridge_apply_markers``. No dedicated uBridge round-trip — exactly
        how packet filters are applied.

        :param name: stable filter name — echoed in MARK signals + pcap identity
        :param bpf: libpcap BPF expression
        :param tag: optional correlation id
        :param capture_node_id: optional explicit observer node. When set the
            marker is pinned to that endpoint's uBridge (and ``direction`` is
            interpreted from its perspective); validated by ``_node_by_id``.
            Omitted = auto-pick via ``_choose_marker_side``. Ignored for
            inherited markers (project defs are link-agnostic → always auto).
        :param color: optional hex color for the Web UI (e.g. '#ff5722'); stored
            with the link and persisted in the topology, never sent to uBridge
        :param highlight_duration: optional UI-only hint (milliseconds) for how
            long a match keeps the marker highlighted; stored, never sent to uBridge
        :param inherited_from: def name when this marker is a project-level
            inheritance copy; set automatically, never exposed to REST callers
        """

        if name in self._markers:
            raise ControllerError(f"Marker '{name}' already exists on link {self._id}")

        # Validate the BPF only for private per-link markers. An inherited copy
        # (``inherited_from`` set) fans out from a definition whose BPF was
        # already validated once at create/update (and on project load), so
        # re-validating per link would spawn one ``tcpdump -d`` per link for the
        # same expression.
        if not inherited_from:
            result = validate_bpf_syntax(bpf)
            if not result.get("valid"):
                raise ControllerError(f"Invalid BPF expression: {result.get('error', 'unknown error')}")

        if capture_node_id and not inherited_from:
            marker_side = self._node_by_id(capture_node_id)
        else:
            marker_side = self._choose_marker_side()
        marker_entry = {
            "bpf": bpf,
            "tag": tag,
            "enabled": enabled,
            "color": color,
            "highlight_duration": highlight_duration,
            "capture_node_id": marker_side["node"].id,
            "direction": direction,
            "data_link_type": data_link_type,
        }
        if inherited_from:
            marker_entry["inherited_from"] = inherited_from
        self._markers[name] = marker_entry
        if memory_only:
            # Project-open prepare / marker-def fan-out: only refresh the
            # in-memory NIO specs so a later batch dispatch carries the new
            # markers — no per-link update HTTP, notification or dump.
            self._refresh_link_data()
            return
        if self._created:
            await self.update()
        self._project.emit_notification("link.updated", self.asdict())
        # Bulk fan-out passes dump=False: N per-link topology writes on a
        # 500-link project are the dominant cost — the caller dumps once after.
        if dump:
            self._project.dump()

    def _refresh_link_data(self):
        """
        Recompute the filters / markers / suspend fields of ``_link_data`` from
        the current link state without pushing to computes. Used by the
        memory-only marker path so a batch dispatch picks up the new markers.
        """

        if len(self._link_data) < 2:
            return
        node1 = self._nodes[0]["node"]
        node2 = self._nodes[1]["node"]
        node1_filters, node2_filters = self._get_node_filters(node1, node2)
        node1_markers, node2_markers = self._get_node_markers(node1, node2)
        self._link_data[0]["filters"] = node1_filters
        self._link_data[0]["markers"] = node1_markers
        self._link_data[0]["suspend"] = self._suspended
        self._link_data[1]["filters"] = node2_filters
        self._link_data[1]["markers"] = node2_markers
        self._link_data[1]["suspend"] = self._suspended

    async def stop_marker(self, name, inherited=False, dump=True, memory_only=False):
        """
        Remove a traffic-insight marker from this link.

        Drop it from ``_markers`` and push via ``self.update()``: the NIO
        reset+reapply in ``_ubridge_apply_filters``/``_ubridge_apply_markers``
        drops it from uBridge. Mirrors how deleting a packet filter works.

        :param name: filter name to remove
        :param inherited: set by project-level def-delete to bypass the
            inheritance guard (the project layer is the legitimate remover)
        """

        if name not in self._markers:
            raise ControllerNotFoundError(f"Marker '{name}' not found on link {self._id}")

        if self._markers[name].get("inherited_from") and not inherited:
            raise ControllerError(
                f"Marker '{name}' is inherited from the project-level "
                f"definition '{self._markers[name]['inherited_from']}'. "
                "Delete or update it via the marker-definitions API instead."
            )

        capture_node_id = self._markers[name].get("capture_node_id")
        del self._markers[name]
        if memory_only:
            # Project-level def-delete fan-out: marker is gone from _markers;
            # refresh _link_data so the batch dispatch drops it from uBridge
            # via full reapply. No per-link delete round-trip, notification or dump.
            self._refresh_link_data()
            return
        # Remove the marker filter + its pcap on the capture node directly — NOT a
        # full NIO reapply (which would reset_packet_filters and close/reopen every
        # sibling marker's pcap). delete_packet_filter removes just this filter;
        # the marker is already gone from _markers, so any later reapply (filter
        # change, node restart) won't re-add it either.
        if capture_node_id is not None:
            side = next((s for s in self._nodes if str(s["node"].id) == str(capture_node_id)), None)
            if side is not None:
                try:
                    await side["node"].delete(
                        f"/adapters/{side['adapter_number']}/ports/{side['port_number']}/markers/{name}",
                        params={"link_id": self._id},
                    )
                except Exception:
                    pass  # best-effort: old compute without the route leaves the file
        self._project.emit_notification("link.updated", self.asdict())
        if dump:
            self._project.dump()

    async def update_marker(self, name, bpf=None, tag=None, enabled=None, direction=_UNSET, color=None, highlight_duration=None, inherited=False, dump=True, memory_only=False):
        """
        Update an existing marker's fields and push to uBridge fine-grained — no
        full NIO reapply, so sibling markers' pcaps stay open. bpf/tag/direction
        rebuild just this filter (delete + add); enabled is an instant toggle;
        color/highlight_duration are UI-only (stored, never pushed).

        :param name: filter name to update
        :param bpf: new BPF expression (None = keep existing)
        :param tag: new tag id (None = keep existing)
        :param enabled: toggle (None = keep existing)
        :param color: new hex color (None = keep existing)
        :param highlight_duration: new UI highlight duration in ms (None = keep existing)
        :param inherited: set by project-level sync to bypass the inheritance
            guard (the project layer is the legitimate editor)
        """

        marker_info = self._markers.get(name)
        if not marker_info:
            raise ControllerNotFoundError(f"Marker '{name}' not found on link {self._id}")

        if marker_info.get("inherited_from") and not inherited:
            raise ControllerError(
                f"Marker '{name}' is inherited from the project-level "
                f"definition '{marker_info['inherited_from']}'. "
                "Update it via the marker-definitions API instead."
            )

        # Merge every changed field into the marker state first.
        if bpf is not None and bpf != marker_info["bpf"]:
            # An inherited marker is synced from a definition whose BPF was
            # already validated at create/update (or load); re-validating per
            # link is redundant. Private markers validate here as before.
            if not inherited:
                result = validate_bpf_syntax(bpf)
                if not result.get("valid"):
                    raise ControllerError(f"Invalid BPF expression: {result.get('error', 'unknown error')}")
            marker_info["bpf"] = bpf
        if tag is not None:
            marker_info["tag"] = tag
        if enabled is not None:
            marker_info["enabled"] = enabled
        if color is not None:
            marker_info["color"] = color
        if highlight_duration is not None:
            marker_info["highlight_duration"] = highlight_duration
        if direction is not _UNSET:
            marker_info["direction"] = direction  # None = clear back to both directions

        if memory_only:
            # Project-level def sync fan-out: state is already merged into
            # _markers; just refresh _link_data so the batch dispatch carries
            # it. No per-link uBridge rebuild, notification or dump.
            self._refresh_link_data()
            return

        # Push to uBridge fine-grained — NO full NIO reapply (which would
        # reset_packet_filters and close/reopen every sibling marker's pcap):
        #   * bpf/tag/direction changed → rebuild just this filter (delete + add),
        #     reopening only this marker's pcap (expected, new BPF)
        #   * only enabled changed      → instant toggle (enable_packet_filter)
        #   * only UI fields changed    → nothing to push to uBridge
        if self._created:
            ubridge_rebuild = (bpf is not None) or (tag is not None) or (direction is not _UNSET)
            capture_node_id = marker_info.get("capture_node_id")
            side = next((s for s in self._nodes if str(s["node"].id) == str(capture_node_id)), None)
            if side is not None:
                try:
                    if ubridge_rebuild:
                        await side["node"].put(
                            f"/markers/{name}/rebuild",
                            data={
                                "bpf": marker_info["bpf"],
                                "tag": marker_info.get("tag"),
                                "direction": marker_info.get("direction"),
                                "enabled": marker_info.get("enabled", True),
                                "link_id": self._id,
                            },
                        )
                    elif enabled is not None:
                        await side["node"].put(f"/markers/{name}", data={"enabled": enabled})
                except Exception:
                    # Old compute without the route / node down: state is already
                    # correct in _markers; the next NIO reapply converges uBridge.
                    pass
        self._project.emit_notification("link.updated", self.asdict())
        if dump:
            self._project.dump()
