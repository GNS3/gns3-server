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
Kernel-datapath machinery shared by every node type whose adapters own a
host-side interface: the tc packet-filter translation (netem, classic-BPF
match-drop, eBPF stateful drops), the uBridge tc-capability probe, the kernel
marker primitives, the link attach/detach flows and the adapter carrier.

An **anchor** is the host-side interface an adapter owns in the root
namespace — the veth host end of a Docker adapter, the persistent TAP of a
QEMU adapter, and whatever a future node type creates. Links attach *to* the
anchor (per-link kernel bridge port, or a uBridge relay endpoint via
AF_PACKET); links never create or destroy it. Every datapath-specific command
in this module takes an anchor name, which is why a TAP and a veth host end
are interchangeable here.

A node type using this mixin provides:

* ``_kernel_host_ifc(adapter_number, port_number)`` — its anchor for a port,
  or None when the adapter has none (a vendor container without a veth);
* ``_kernel_anchors()`` — every anchor it currently owns, used to recognise
  the polymorphic marker anchor;
* ``_tap_name(adapter_number, port_number)`` — the deterministic anchor TAP
  name of a port (the shared utils.kernel_anchor contract), for the node
  types whose anchor is a persistent TAP;
* optionally ``_relay_carrier_bridge(adapter_number, port_number)`` — the
  uBridge bridge carrying the adapter's TAP relay, for node types whose relay
  datapath still rides a uBridge-owned TAP instead of an anchor;
* optionally ``_kernel_error(message)`` — the module's own error type, so
  failures surface as ``DockerError`` / ``QemuError`` rather than ``NodeError``.
"""

import contextlib
import logging
import os

from gns3server.compute.error import NodeError
from gns3server.compute.ubridge.ubridge_error import UbridgeError
from gns3server.utils.tc_capabilities import FILTER_EBPF_MODES, parse_tc_capabilities, usable_ebpf_modes

from .nios.nio_bridge import NIOBridge

log = logging.getLogger(__name__)


class KernelDatapathMixin:
    """
    The datapath-agnostic half of a kernel-datapath node: consumed by
    DockerVM and QEMUVm so each of them stays focused on its own node
    lifecycle.
    """

    # ------------------------------------------------------------------
    # Hooks a node type implements
    # ------------------------------------------------------------------

    def _kernel_host_ifc(self, adapter_number, port_number=0):
        """
        Returns the anchor interface of an adapter port, or None when the
        adapter has no host-side interface (a vendor container wired through
        a unix socket).
        """

        raise NotImplementedError

    def _kernel_anchors(self):
        """
        Returns the set of anchor interface names this node currently owns.
        """

        raise NotImplementedError

    def _relay_carrier_bridge(self, adapter_number, port_number=0):
        """
        Returns the uBridge relay bridge whose TAP carrier replicates this
        adapter's connection state, or None when the adapter's relay does not
        ride a uBridge-owned TAP (every anchor-backed adapter: its carrier is
        the anchor's own admin state).
        """

        return None

    def _tap_name(self, adapter_number, port_number=0):
        """
        Returns the deterministic anchor TAP name of a port (the shared
        utils.kernel_anchor naming contract — the controller names a peer's
        anchor with the same function when an Ethernet switch absorbs it).
        """

        raise NotImplementedError

    def _kernel_error(self, message):
        """
        Returns the node module's error for a kernel-datapath failure
        (DockerError, QemuError, ...).
        """

        return NodeError(message)

    def _kernel_marker_anchor(self, anchor):
        """
        Whether *anchor* names one of this node's anchors. Marker anchors are
        polymorphic: a relay bridge name on the relay datapath, the anchor
        interface on the kernel datapath. Anchor names cannot collide with
        uBridge bridge names.
        """

        return anchor in self._kernel_anchors()

    async def _set_adapter_carrier(self, adapter_number, connected, port_number=0):
        """Replicate an adapter's connection state on its host interface.

        Anchor-backed adapters toggle the anchor's admin state (the peer —
        container end or VM TAP reader — loses carrier when it is down);
        adapters whose relay rides a uBridge TAP toggle that TAP's carrier
        from the uBridge fd holder.
        """

        host_ifc = self._kernel_host_ifc(adapter_number, port_number)
        if host_ifc is not None:
            state = "up" if connected else "down"
            await self._ubridge_send(f'link set "{host_ifc}" {state}')
            return

        bridge_name = self._relay_carrier_bridge(adapter_number, port_number)
        if bridge_name is None:
            return
        state = "on" if connected else "off"
        await self._ubridge_send(f"bridge set_nio_tap_carrier {bridge_name} {state}")

    # ------------------------------------------------------------------
    # Anchor TAP lifecycle
    # ------------------------------------------------------------------

    async def _probe_persistent_taps(self, probe_name):
        """
        Probe the node's uBridge for the persistent-TAP module with a
        scratch TAP that is deleted again. Returns None when the module
        works, or the UbridgeError that refused it — an old build answers
        "Unknown command"/"Unknown module", a build without CAP_NET_ADMIN
        fails outright. The caller composes its own warning and fallback:
        the legacy relay datapath keeps working either way.
        """

        try:
            await self._ubridge_send(f'tap create "{probe_name}"')
        except UbridgeError as e:
            return e
        with contextlib.suppress(UbridgeError):
            await self._ubridge_send(f'tap delete "{probe_name}"')
        return None

    async def _create_anchor_taps(self, ports, set_owner=False, keep_existing=False):
        """
        Create the persistent anchor TAP of every port, named through
        ``_tap_name`` and registered in ``_kernel_taps``.

        *ports* is an iterable of ``(adapter_number, port_number)`` keys — a
        node type enumerates whichever of its ports anchor (QEMU's whole
        adapters, IOU's bay/units, Dynamips' Ethernet slot ports, the IOL
        container's bay/units). A persistent TAP outlives its creator, so a
        leftover of a previous run (crash, kill) is swept first; each TAP is
        created and starts DOWN (carrier off until a link attaches).
        ``set_owner`` hands the device to this user for the node types whose
        unprivileged emulator opens it itself (QEMU, Dynamips);
        ``keep_existing`` leaves ports that already hold an anchor alone —
        for a node whose anchors outlive its stop (Dynamips) or an adapter
        hot-added to a running node, where an anchor must never be recreated
        under a live link.
        """

        for key in ports:
            if keep_existing and key in self._kernel_taps:
                continue
            tap = self._tap_name(*key)
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'tap delete "{tap}"')
            await self._ubridge_send(f'tap create "{tap}"')
            if set_owner:
                try:
                    await self._ubridge_send(f"tap set_owner {tap} {os.getuid()}")
                except UbridgeError as e:
                    # Only root could open the TAP then: the emulator would
                    # fail to attach its netdev, which is worth surfacing
                    # here rather than as a launch failure.
                    log.warning(
                        "Node '%s' [%s]: could not hand TAP %s to uid %s: %s", self._name, self._id, tap, os.getuid(), e
                    )
            await self._ubridge_send(f'link set "{tap}" down')
            self._kernel_taps[key] = tap
            log.debug("Node '%s' [%s]: anchor TAP %s created for port %s", self._name, self._id, tap, key)

    async def _delete_anchor_taps(self):
        """
        Delete every registered anchor TAP and the per-link kernel bridges
        this node still holds, then drop the registry. The caller releases
        whatever holds each TAP's fd first (the QEMU process, the IOL
        bridge, the hypervisor's NIO bindings, the container port bridges):
        a held device answers EBADFD and the best-effort delete below would
        leak it. The sweep is suppressed per TAP — an anchor already gone
        is not an error — and the registry is cleared either way.
        """

        if self.ubridge:
            for tap in self._kernel_taps.values():
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'tap delete "{tap}"')
            await self._remove_kernel_bridges()
        self._kernel_taps.clear()

    # ------------------------------------------------------------------
    # Link attach / detach
    # ------------------------------------------------------------------

    @staticmethod
    def _owns_anchor_impairments(nio):
        """
        Whether this end owns the tc state (netem, cls_bpf, eBPF) of the
        anchor it was handed. A NIOBridge with no bridge of its own
        (``bridge is None``) means the anchor is absorbed by an Ethernet
        switch: the switch owns the anchor's bridge membership and its
        impairment state — the controller routes the link's filters to the
        switch end, so this NIO always carries an empty filter set, whose
        reconcile is a plain ``tc reset``. Applying it here would silently
        wipe the netem/bpf/eBPF the switch just put on the shared anchor.
        """

        return not (isinstance(nio, NIOBridge) and nio.bridge is None)

    # The anchor whose kernel capture currently holds the uBridge process's
    # single AF_PACKET capture slot (None = free; see _reserve_kernel_capture).
    # Class-level default so every node type gets it without touching its
    # __init__; BaseNode._stop_ubridge resets it when uBridge goes away.
    _kernel_capture_ifc = None

    def _reserve_kernel_capture(self, anchor):
        """
        Claim uBridge's single kernel-capture slot for *anchor*.

        uBridge serves one AF_PACKET capture per process (a static slot: a
        second ``capture start_kernel`` answers EALREADY) while the server
        models captures per port — a second kernel port of the same node is
        refused here with a clear error. Without the claim the loser's port
        would stay marked as capturing, and its stop would issue the
        process-wide, argument-less ``capture stop_kernel``, killing the
        winner's capture while its own flag still says capturing.
        """

        if self._kernel_capture_ifc is not None and self._kernel_capture_ifc != anchor:
            raise self._kernel_error(
                f"Cannot start the packet capture: this node's uBridge already captures "
                f"{self._kernel_capture_ifc} (one kernel capture per node); stop that capture first"
            )
        self._kernel_capture_ifc = anchor

    def _release_kernel_capture(self, anchor):
        """
        Release the slot if *anchor* holds it: after a stop, or after a
        failed start whose port must not stay marked as capturing.
        """

        if self._kernel_capture_ifc == anchor:
            self._kernel_capture_ifc = None

    def _kernel_capture_owned_by(self, anchor):
        """
        Whether *anchor* may issue the process-wide ``capture stop_kernel``:
        only the port holding the slot — or a node whose slot is empty (a
        capture predating the tracker), where stopping is the historical
        best-effort behaviour. A second port must never reach it: the
        command takes no interface and would stop the owner's capture.
        """

        return self._kernel_capture_ifc is None or self._kernel_capture_ifc == anchor

    async def _kernel_attach(self, anchor, nio):
        """
        Attach an anchor to the per-link kernel bridge carried by *nio*
        (NIOBridge): create the bridge, bring it and the anchor up, enslave
        the anchor, then install the capture, markers and impairment filters
        the NIO carries. Called on link creation and on node start (a link
        that outlived a node restart is re-attached from its NIO).

        Both link endpoints run this concurrently and either may create the
        bridge first: an existing bridge is success instead of a create race
        failure.

        A NIO whose ``bridge`` is None means the anchor is bridged
        elsewhere — an Ethernet switch absorbed it into the switch's own
        bridge — so the membership work is skipped here and only the link
        state this end owns is applied: capture and markers always, the
        impairment filters only when this end owns the anchor's tc state
        (see _owns_anchor_impairments). Exactly one end of such a link
        owns the anchor's bridge and impairment state; the other end is a
        passive carrier.
        """

        if nio.bridge is not None:
            try:
                await self._ubridge_send(f'brctl create "{nio.bridge}"')
            except UbridgeError:
                # Raises again if the bridge genuinely does not exist.
                await self._ubridge_send(f'brctl show "{nio.bridge}"')
            await self._ubridge_send(f'link set "{nio.bridge}" up')
            await self._ubridge_send(f'brctl addif "{nio.bridge}" "{anchor}"')
        if nio.capturing:
            # Restore a capture that was active before a node restart
            # (mirrors the relay path's start_capture). The slot is claimed
            # like a fresh start: a second kernel port's replay is refused
            # with a clear error instead of an EALREADY deep in the wiring.
            self._reserve_kernel_capture(anchor)
            await self._ubridge_send(f'capture start_kernel {anchor} "{nio.pcap_output_file}"')
        # Markers carried by the NIO attach to the anchor (AF_PACKET taps) —
        # the anchor is the interface, not a relay bridge.
        await self._ubridge_apply_markers(anchor, nio)
        # Impairment filters become one tc netem qdisc on the anchor
        # (restored here on node restart, like the capture above); bpf
        # expressions become cls_bpf match-drop classifiers and
        # frequency_drop/quota/window_drop become the eBPF stateful
        # classifier. A passive end owns none of this: its empty filter
        # set is a tc reset, which would wipe the switch's qdisc off the
        # shared anchor.
        if self._owns_anchor_impairments(nio):
            await self._ubridge_apply_netem(anchor, nio.filters)
            await self._ubridge_apply_bpf_drops(anchor, nio.filters)
            await self._ubridge_apply_ebpf_drops(anchor, nio.filters)

    async def _relay_attach(self, anchor, bridge_name, nio):
        """
        Attach an anchor to a uBridge relay bridge (NIOUDP): the bridge turns
        the anchor into an AF_PACKET endpoint and relays it to the link's UDP
        peer. Called on link creation and on node start, and after a link was
        re-created — the relay analogue of _kernel_attach.
        """

        await self._ubridge_send(f"bridge create {bridge_name}")
        # libpcap cannot open a packet socket on an admin-down interface (its
        # netlink promiscuous-mode transaction returns ENOENT), and an anchor
        # is born down (carrier off until a link attaches) — bring it up for
        # the relay attach. The carrier pass in the caller refines the state
        # afterwards (a suspended NIO sets it back down).
        await self._ubridge_send(f'link set "{anchor}" up')
        await self._ubridge_send(f'bridge add_nio_ethernet {bridge_name} "{anchor}"')
        await self._ubridge_send(f"bridge add_nio_udp {bridge_name} {nio.lport} {nio.rhost} {nio.rport}")
        if nio.capturing:
            await self._ubridge_send(f'bridge start_capture {bridge_name} "{nio.pcap_output_file}"')
        await self._ubridge_send(f"bridge start {bridge_name}")
        await self._ubridge_apply_filters(bridge_name, nio.filters)
        await self._ubridge_apply_markers(bridge_name, nio)

    async def _relay_detach(self, bridge_name):
        """
        Drop a relay bridge: its AF_PACKET endpoint on the anchor goes with
        it, which is what makes switching an adapter from the relay datapath
        to a kernel link safe (otherwise the anchor would both be a bridge
        port and a relay endpoint, duplicating one direction).
        """

        if self.ubridge:
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f"bridge delete {bridge_name}")

    async def _kernel_update(self, anchor, nio):
        """
        Re-apply everything a kernel link carries on an already-attached
        anchor (filters and markers changed): no re-enslaving, no bridge
        create. A passive end (bridge is None — an anchor absorbed by an
        Ethernet switch) leaves the anchor's impairment state to the
        switch that owns it.
        """

        await self._ubridge_apply_markers(anchor, nio)
        # The netem apply resets the interface first (the kernel merges
        # optional netem attrs on replace), so everything anchored on clsact
        # must re-apply after it: bpf drops flush + re-add, eBPF modes re-set.
        if self._owns_anchor_impairments(nio):
            await self._ubridge_apply_netem(anchor, nio.filters)
            await self._ubridge_apply_bpf_drops(anchor, nio.filters)
            await self._ubridge_apply_ebpf_drops(anchor, nio.filters)

    async def _remove_kernel_nio(self, nio, adapter_number, port_number=0):
        """
        Detach an anchor from its per-link kernel bridge. Both endpoints run
        this concurrently: deleting a bridge that still has the peer's port
        enslaved fails with EBUSY, so the last endpoint to remove its port
        wins the deletion and the loser's failure is expected and suppressed.

        A NIO whose ``bridge`` is None owns no bridge here: the anchor is
        bridged by an Ethernet switch, which tears its own membership down
        on its side; this end only releases the link state it applied
        (markers, impairments, carrier).
        """

        host_ifc = self._kernel_host_ifc(adapter_number, port_number)
        if host_ifc is not None:
            await self._remove_kernel_markers(host_ifc)
            # The anchor survives link deletion, so an orphaned netem qdisc
            # would keep impairing whatever attaches to the adapter next
            # (kernel link or relay). Best-effort: ENOENT just means no
            # qdisc was attached.
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'tc reset "{host_ifc}"')
            if self.status == "started":
                await self._set_adapter_carrier(adapter_number, False, port_number)
            if nio.bridge is not None:
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'brctl delif "{nio.bridge}" "{host_ifc}"')
        if nio.bridge is not None:
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'brctl delete "{nio.bridge}"')

    async def _remove_kernel_bridges(self):
        """
        Delete every per-link kernel bridge this node still holds. Deleting a
        node (or closing a project) never runs the link-teardown path, so a
        bridge whose ports just disappeared would stay behind as an empty
        orphan. Both link endpoints run this — the peer's still-enslaved port
        makes the delete fail with EBUSY (suppressed) and the last one wins,
        the same contract as link deletion. A node restart re-creates the
        bridge from the NIO in the attach path, so nothing is lost by
        deleting it.
        """

        if not self.ubridge:
            return
        for adapter in self._ethernet_adapters:
            for nio in adapter.ports.values():
                # bridge None = externally bridged (an Ethernet switch owns
                # the bridge); never delete a bridge this node does not own.
                if isinstance(nio, NIOBridge) and nio.bridge is not None:
                    with contextlib.suppress(UbridgeError):
                        await self._ubridge_send(f'brctl delete "{nio.bridge}"')

    # ------------------------------------------------------------------
    # Markers
    # ------------------------------------------------------------------

    async def _ubridge_add_marker_filter(
        self, bridge_name, name, bpf, pcap_path, tag=None, link_id=None, direction=None, data_link_type=None
    ):
        """
        Kernel-datapath variant of the `mark` filter attach: ``marker
        add_kernel`` binds an AF_PACKET socket to the anchor. Keyword pairs
        and semantics (match → MARK signal + pcap append) are identical to
        the relay ``bridge add_packet_filter … mark`` command.
        """

        if self._kernel_marker_anchor(bridge_name):
            self._validate_marker_name(name)
            cmd = f'marker add_kernel {name} {bridge_name} "{bpf}"'
            if tag is not None:
                cmd += f" tag {tag}"
            if link_id:
                cmd += f" link {link_id}"
            if direction is not None:
                cmd += f" dir {direction}"
            linktype = self._marker_linktype(data_link_type)
            if linktype is not None:
                cmd += f" linktype {linktype}"
            cmd += f' pcap "{pcap_path}"'
            await self._ubridge_send(cmd)
            return
        await super()._ubridge_add_marker_filter(
            bridge_name,
            name,
            bpf,
            pcap_path,
            tag=tag,
            link_id=link_id,
            direction=direction,
            data_link_type=data_link_type,
        )

    async def _ubridge_delete_marker_filter(self, bridge_name, name):
        """
        Kernel-datapath variant of the marker removal: ``marker delete_kernel``
        (idempotent in uBridge — a no-op when the marker is already gone).
        """

        if self._kernel_marker_anchor(bridge_name):
            if not (self._ubridge_hypervisor and self._ubridge_hypervisor.is_running()):
                return
            try:
                await self._ubridge_send(f"marker delete_kernel {bridge_name} {name}")
            except UbridgeError as e:
                log.warning("Could not remove kernel marker '%s' from %s: %s", name, bridge_name, e)
            return
        await super()._ubridge_delete_marker_filter(bridge_name, name)

    async def _ubridge_enable_marker_filter(self, anchor, name, state):
        """
        Kernel-datapath variant of the marker on/off toggle: ``marker
        enable_kernel`` — installed but silent when off, pcap preserved.
        """

        if self._kernel_marker_anchor(anchor):
            await self._ubridge_send(f"marker enable_kernel {anchor} {name} {state}")
            return
        await super()._ubridge_enable_marker_filter(anchor, name, state)

    async def _remove_kernel_markers(self, host_ifc):
        """
        Tear down every kernel marker anchored to *host_ifc*: the anchor
        survives link deletion (it is the adapter interface, not the link),
        so the AF_PACKET sockets must be closed explicitly — otherwise a
        deleted link's markers would keep sniffing and signaling. Mirrors the
        relay datapath where deleting the uBridge bridge silently drops its
        filters.
        """

        from gns3server.compute.marker.marker_manager import MarkerManager

        manager = MarkerManager.instance()
        markers_dir = self.project.markers_working_directory()
        for (name, link_id), anchor in list(self._marker_filter_bridges.items()):
            if anchor != host_ifc:
                continue
            self._marker_filter_bridges.pop((name, link_id))
            self._marker_specs.pop((name, link_id), None)
            await self._ubridge_delete_marker_filter(host_ifc, name)
            try:
                os.remove(os.path.join(markers_dir, f"{self._id}_{link_id}_{name}.pcap"))
            except FileNotFoundError:
                pass
            except OSError as e:
                log.warning("Could not remove marker pcap for '%s' on link %s: %s", name, link_id, e)
            manager.unregister(self._id, name)

    # ------------------------------------------------------------------
    # Packet filters (tc netem / cls_bpf / eBPF stateful classifier)
    # ------------------------------------------------------------------

    @staticmethod
    def _values_of(filters, key):
        """
        One filter's values as a list, tolerating the legacy bare-value
        shape ({"packet_loss": 10}).
        """

        values = filters.get(key)
        if isinstance(values, (list, tuple)):
            return list(values)
        return [values] if values else []

    @staticmethod
    def _netem_loss_parts(filters):
        """
        The loss keyword: gemodel when set, else packet_loss — mutually
        exclusive, both mapping to netem's single loss argument. The gemodel
        token is returned for the caller's capability check; a non-zero
        packet-loss correlation gates on "rate" as the extension build
        marker.

        :returns: (keyword sequence, required extension tokens)
        """

        values_of = KernelDatapathMixin._values_of
        parts = []
        ext_tokens = set()

        gemodel = values_of(filters, "gemodel")
        if gemodel:
            segment = f"loss gemodel {int(gemodel[0])}"
            if len(gemodel) > 1:
                segment += f" {int(gemodel[1])}"
                if len(gemodel) > 2:
                    segment += f" {int(gemodel[2])}"
            parts.append(segment)
            ext_tokens.add("gemodel")
            return parts, ext_tokens

        loss = values_of(filters, "packet_loss")
        if loss and int(loss[0]):
            parts.append(f"loss {int(loss[0])}")
            if len(loss) > 1 and int(loss[1]):
                parts.append(f"correl {int(loss[1])}")
                ext_tokens.add("rate")  # correl: extension build marker
        return parts, ext_tokens

    @staticmethod
    def _netem_surface_parts(filters):
        """
        The original netem surface in its frozen grammar order — delay/
        jitter, loss (or gemodel), dup (+correl), corrupt — plus the
        capability tokens it needs. Original-surface keywords need no
        probe; ``correl`` has no token of its own in the capabilities
        list, so it gates on "rate" as the netem-extension build marker.

        :returns: (keyword sequence, required extension tokens)
        """

        values_of = KernelDatapathMixin._values_of
        parts = []
        ext_tokens = set()

        delay = values_of(filters, "delay")
        if delay:
            parts.append(f"delay {int(delay[0])}")
            if len(delay) > 1 and int(delay[1]):
                parts.append(f"jitter {int(delay[1])}")

        loss_parts, loss_tokens = KernelDatapathMixin._netem_loss_parts(filters)
        parts.extend(loss_parts)
        ext_tokens |= loss_tokens

        duplicate = values_of(filters, "duplicate")
        if duplicate and int(duplicate[0]):
            parts.append(f"dup {int(duplicate[0])}")
            if len(duplicate) > 1 and int(duplicate[1]):
                parts.append(f"correl {int(duplicate[1])}")
                ext_tokens.add("rate")  # correl: extension build marker

        corrupt = values_of(filters, "corrupt")
        if corrupt and int(corrupt[0]):
            parts.append(f"corrupt {int(corrupt[0])}")

        return parts, ext_tokens

    @staticmethod
    def _netem_extension_parts(filters):
        """
        The netem extensions in their frozen grammar order — reorder, rate,
        limit, distribution, seed — plus each keyword's capability token.
        The tokens (rate, reorder, dist, seed, limit) are checked against
        ``tc capabilities`` by the caller.

        :returns: (keyword sequence, required extension tokens)
        """

        values_of = KernelDatapathMixin._values_of
        parts = []
        ext_tokens = set()

        reorder = values_of(filters, "reorder")
        if reorder:
            segment = f"reorder {int(reorder[0])}"
            if len(reorder) > 1 and int(reorder[1]):
                segment += f" correl {int(reorder[1])}"
            if len(reorder) > 2 and int(reorder[2]):
                segment += f" gap {int(reorder[2])}"
            parts.append(segment)
            ext_tokens.add("reorder")

        rate = values_of(filters, "rate")
        if rate and str(rate[0]).strip():
            parts.append(f"rate {str(rate[0]).strip()}")
            ext_tokens.add("rate")

        limit = values_of(filters, "limit")
        if limit and int(limit[0]):
            parts.append(f"limit {int(limit[0])}")
            ext_tokens.add("limit")

        delay = values_of(filters, "delay")
        if delay and len(delay) > 2 and str(delay[2]).strip().lower() not in ("", "uniform"):
            # "uniform" is the kernel default — emitting nothing keeps the
            # command compatible with the original netem surface.
            parts.append(f"distribution {str(delay[2]).strip().lower()}")
            ext_tokens.add("dist")

        seed = values_of(filters, "seed")
        if seed and int(seed[0]):
            # 0 is the "disabled" convention everywhere else — treat it so
            # here too (the controller's inactive-filter pass drops it).
            parts.append(f"seed {int(seed[0])}")
            ext_tokens.add("seed")

        return parts, ext_tokens

    @staticmethod
    def _netem_command_parts(filters):
        """
        Build the ``tc netem set`` keyword sequence (in the frozen grammar
        order: delay/jitter, loss|gemodel, dup, corrupt, reorder, rate,
        limit, distribution, seed) plus the set of capability tokens the
        sequence needs beyond the original netem surface.

        :param filters: NIO filters dictionary ({"delay": [ms, jitter, dist], ...})

        :returns: (keyword sequence, required extension tokens)
        """

        parts, ext_tokens = KernelDatapathMixin._netem_surface_parts(filters)
        extension_parts, extension_tokens = KernelDatapathMixin._netem_extension_parts(filters)
        parts.extend(extension_parts)
        ext_tokens |= extension_tokens
        return parts, ext_tokens

    async def _ubridge_apply_netem(self, host_ifc, filters):
        """
        Translate the NIO's impairment filters into one tc netem qdisc on the
        anchor. The netem-expressible types (delay, packet_loss, corrupt and
        the netem extensions rate/reorder/gemodel/duplicate/seed/limit) merge
        into a single qdisc — its egress covers the traffic entering this
        node, and with both link endpoints applying theirs, every direction
        of the link is impaired exactly once (the same net effect as the
        relay, where both directions cross the single filtered bridge).

        The kernel's netem replace MERGES optional attributes (rate,
        correlation, reorder, corrupt, gemodel, distribution: absent attr =
        previous value kept), so re-applying a filter set with a parameter
        *removed* would silently keep the old value. A ``tc reset`` before
        every ``netem set`` makes the re-apply a true reconcile (reset also
        drops clsact and its bpf_drop filters — the caller re-applies them
        right after in the same flow). An empty filter set is the reset
        alone.

        :param host_ifc: anchor interface name
        :param filters: NIO filters dictionary ({"delay": [ms, jitter], ...})
        """

        try:
            parts, ext_tokens = self._netem_command_parts(filters)
        except (TypeError, ValueError) as e:
            # int() on a stray value from an unvalidated direct-API update
            # (e.g. {"delay": ["abc"]}) would otherwise surface as a 500.
            raise self._kernel_error(f"Malformed packet filter values on a kernel-datapath link: {e}")
        if parts and ext_tokens:
            # Extension keywords need the netem-extension uBridge. Plain
            # delay/loss/corrupt/dup never probes — an old uBridge serves
            # the original surface untouched (mirrors bpf_drop's guard).
            # Checked before the reset so a failed update leaves the
            # previously applied qdisc in place.
            caps = await self._ubridge_tc_capabilities()
            missing = ext_tokens - set(caps.get("netem", "").split(","))
            if missing:
                raise self._kernel_error(
                    "Packet filter(s) using {} need a uBridge with the netem extensions "
                    "(tc capabilities reports '{}'); upgrade uBridge on this compute".format(
                        ", ".join(sorted(missing)), caps.get("netem") or "no tc support"
                    )
                )
        try:
            await self._ubridge_send(f'tc reset "{host_ifc}"')
        except UbridgeError as e:
            # "No such file or directory" = no qdisc was attached: already
            # clean. Everything else is a real failure and must surface.
            if "No such file" not in str(e):
                raise
        if not parts:
            return
        await self._ubridge_send('tc netem set "{ifc}" {params}'.format(ifc=host_ifc, params=" ".join(parts)))

    async def _ubridge_tc_capabilities(self):
        """
        uBridge's tc-module feature report (``tc capabilities``), probed once
        per uBridge process and cached — the reply shape is
        ``netem=<kw,...>;ebpf=0|1;cbpf=0|1[;ebpf_modes=<mode,...>]`` (parsed
        by parse_tc_capabilities). uBridge builds without the tc module
        answer "Unknown module" and old builds without the command answer
        "Unknown command": both mean no kernel filter support, cached as an
        empty dict.
        """

        if self._ubridge_tc_caps is None:
            caps = {}
            if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
                try:
                    reply = await self._ubridge_hypervisor.send("tc capabilities")
                except UbridgeError:
                    reply = []
                caps = parse_tc_capabilities(reply[0] if reply else "")
            self._ubridge_tc_caps = caps
        return self._ubridge_tc_caps

    async def _ubridge_apply_bpf_drops(self, host_ifc, filters):
        """
        Translate the NIO's ``bpf`` filter (one expression per line, any line
        matching drops the packet) into cls_bpf classifiers on the anchor's
        clsact egress: ``tc bpf_drop`` compiles each line with libpcap (same
        compiler as the relay's bpf filter) and drops matches with a gact
        TC_ACT_SHOT. Reconcile is always flush + re-add — same-prio resend
        replaces the filter node in uBridge, and the flush drops lines the
        user removed.

        :param host_ifc: anchor interface name
        :param filters: NIO filters dictionary
        """

        bpf = filters.get("bpf")
        # Accept the bare-value shape ({"bpf": "icmp"}): a str is the
        # expression itself — indexing it would install its first character.
        if isinstance(bpf, str):
            bpf = [bpf]
        elif not isinstance(bpf, (list, tuple)):
            bpf = []
        lines = [line.strip() for line in (str(bpf[0]).split("\n") if bpf else []) if line.strip()]
        if not lines and self._ubridge_tc_caps is None:
            # Nothing to add and nothing was ever installed (no tc module
            # probed yet) — skip touching an old uBridge entirely.
            return
        caps = await self._ubridge_tc_capabilities()
        if not lines:
            if caps:
                await self._ubridge_send(f'tc bpf_drop flush "{host_ifc}"')
            return
        if caps.get("cbpf") != "1":
            raise self._kernel_error(
                "Packet filter 'bpf' on a kernel-datapath link needs a uBridge with cBPF support "
                "(tc capabilities reports no cbpf); upgrade uBridge on this compute or keep the "
                "link on the relay datapath"
            )
        await self._ubridge_send(f'tc bpf_drop flush "{host_ifc}"')
        for offset, line in enumerate(lines):
            try:
                await self._ubridge_send(f'tc bpf_drop add "{host_ifc}" {10 + offset} "{line}"')
            except UbridgeError as e:
                if "Cannot compile filter" not in str(e):
                    raise
                # Mirror the relay path: a line that no longer compiles on
                # this uBridge's libpcap is skipped with a warning instead
                # of breaking the link (the controller already validated
                # the syntax with tcpdump at create/update time).
                message = f"Warning: ignoring BPF packet filter '{self.name}' due to syntax error: {line}"
                log.warning(message)
                self.project.emit("log.warning", {"message": message})

    async def _ubridge_apply_ebpf_drops(self, host_ifc, filters):
        """
        Translate the NIO's stateful filters into uBridge's eBPF impairment
        classifier on the anchor's clsact egress (prio 1, below bpf_drop's
        10-99): ``frequency_drop`` becomes the exact every-Nth mode
        (``tc nth_drop``; -1 = drop everything maps to every 1st), the
        kernel-only ``quota`` type the byte-cap mode (``tc quota_drop``),
        and the kernel-only ``window_drop`` type the time-window mode
        (``tc window_drop``: single outage, or recurring flaps with an
        optional per-cycle jitter). The program evaluates the modes in the
        fixed order nth → quota → window → flow. A mode is only sent when
        ``tc capabilities`` declares its token (``ebpf_modes``); builds
        predating the field keep their shipped modes (everything but
        window).

        Reconcile is a plain re-set on every apply: the preceding netem
        apply resets the interface (which detaches the program and drops
        uBridge's per-interface registry entry), so a mode set re-loads the
        program from scratch, and a mode left absent is turned off
        explicitly (idempotent) so a removed filter stops dropping. For
        window_drop this also means the schedule restarts on every apply:
        the first window opens Start-ms from the moment of this call.

        Semantic difference vs the relay, documented server-side: the relay
        counts packets of BOTH directions through its single filtered
        bridge, while each anchor's classifier counts only the traffic
        entering that node — with both endpoints applying theirs, each
        direction drops every Nth independently (their window schedules
        start ~simultaneously, so a round trip survives only when both
        directions are outside their windows).

        :param host_ifc: anchor interface name
        :param filters: NIO filters dictionary
        """

        def numeric_values(key, minimum, maximum):
            """
            The filter's values as ints, refusing a malformed shape here: the
            direct compute API is unvalidated (the controller's validation
            does not run for it), and indexing a short list or int()-ing a
            stray string further down would surface as a bare IndexError or
            ValueError 500 after the bridge/netem state was already applied.
            """

            values = self._values_of(filters, key)
            if not values:
                return []
            try:
                numbers = [int(value) for value in values]
            except (TypeError, ValueError):
                raise self._kernel_error(f"Packet filter '{key}' needs integer values, got {values!r}")
            if not minimum <= len(numbers) <= maximum:
                raise self._kernel_error(
                    f"Packet filter '{key}' needs between {minimum} and {maximum} integer values, got {len(numbers)}"
                )
            return numbers

        frequency = numeric_values("frequency_drop", 1, 1)
        quota = numeric_values("quota", 2, 2)
        window = numeric_values("window_drop", 3, 5)
        requested = {filter_type: self._values_of(filters, filter_type) for filter_type in FILTER_EBPF_MODES}
        if not any(requested.values()) and self._ubridge_tc_caps is None:
            # Nothing to set and nothing was ever installed (no probe yet) —
            # skip touching an old uBridge entirely.
            return
        caps = await self._ubridge_tc_capabilities()
        # A mode is usable iff ebpf=1 and the build declares its token
        # (ebpf_modes); builds predating the field keep their shipped modes.
        modes = usable_ebpf_modes(caps)
        if not any(requested.values()):
            await self._ebpf_turn_off_modes(host_ifc, modes)
            return
        unsupported = sorted(f for f, values in requested.items() if values and FILTER_EBPF_MODES[f] not in modes)
        if unsupported:
            self._reject_unsupported_ebpf_modes(unsupported, modes)
        await self._ebpf_apply_modes(host_ifc, frequency, quota, window, modes)

    async def _ebpf_turn_off_modes(self, host_ifc, modes):
        """
        Turn off every mode this build declares. Only declared modes can
        ever have been installed — sending "off" for an undeclared mode
        would hit an unknown command; "off" is idempotent in uBridge.
        """

        for mode in FILTER_EBPF_MODES.values():
            if mode in modes:
                await self._ubridge_send(f'tc {mode}_drop "{host_ifc}" off')

    def _reject_unsupported_ebpf_modes(self, unsupported, modes):
        """
        Refuse filters whose mode this uBridge cannot run: a clear error
        naming the missing capability (no eBPF at all vs. an older build)
        beats a late uBridge failure.
        """

        if not modes:
            raise self._kernel_error(
                "Packet filter(s) {} on a kernel-datapath link need a uBridge with eBPF support "
                "(tc capabilities reports no ebpf; setcap cap_bpf,cap_net_admin,cap_net_raw=ep on "
                "the uBridge binary); upgrade uBridge on this compute or keep the link on the "
                "relay datapath".format(", ".join(unsupported))
            )
        raise self._kernel_error(
            "Packet filter(s) {} on a kernel-datapath link need a newer uBridge (tc capabilities "
            "reports ebpf_modes={}); upgrade uBridge on this compute or keep the link on the "
            "relay datapath".format(", ".join(unsupported), ",".join(modes))
        )

    async def _ebpf_apply_modes(self, host_ifc, frequency, quota, window, modes):
        """
        Set the requested modes (and clear the absent ones) in the
        classifier's fixed order nth → quota → window. A mode left absent
        is turned off explicitly (idempotent) so a removed filter stops
        dropping; for window_drop this means the schedule restarts on every
        apply (the first window opens Start-ms from the moment of the call).
        """

        if frequency:
            # relay semantics: -1 = drop everything, N = every Nth packet
            nth = 1 if frequency[0] == -1 else frequency[0]
            await self._ubridge_send(f'tc nth_drop "{host_ifc}" {nth}')
        elif "nth" in modes:
            await self._ubridge_send(f'tc nth_drop "{host_ifc}" off')
        if quota:
            await self._ubridge_send(f'tc quota_drop "{host_ifc}" {quota[0]} {quota[1]}')
        elif "quota" in modes:
            await self._ubridge_send(f'tc quota_drop "{host_ifc}" off')
        if window:
            # [start, outage, chance, period?, jitter?] — start is relative
            # to this apply (the schedule restarts on every reconcile).
            params = " ".join(str(v) for v in window)
            await self._ubridge_send(f'tc window_drop "{host_ifc}" {params}')
        elif "window" in modes:
            await self._ubridge_send(f'tc window_drop "{host_ifc}" off')
