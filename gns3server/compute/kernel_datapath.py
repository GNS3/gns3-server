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
* optionally ``_relay_carrier_bridge(adapter_number, port_number)`` — the
  uBridge bridge carrying the adapter's TAP relay, for node types whose relay
  datapath still rides a uBridge-owned TAP instead of an anchor;
* optionally ``_kernel_error(message)`` — the module's own error type, so
  failures surface as ``DockerError`` / ``QemuError`` rather than ``NodeError``.
"""

import os
import contextlib

from gns3server.utils.tc_capabilities import FILTER_EBPF_MODES, parse_tc_capabilities, usable_ebpf_modes
from gns3server.compute.ubridge.ubridge_error import UbridgeError
from gns3server.compute.error import NodeError

from .nios.nio_bridge import NIOBridge

import logging

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
    # Link attach / detach
    # ------------------------------------------------------------------

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
        state the anchor carries (capture, markers, impairment filters) is
        applied. Exactly one end of such a link owns the anchor's bridge
        state; the other end is a passive carrier.
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
            # (mirrors the relay path's start_capture).
            await self._ubridge_send(f'capture start_kernel {anchor} "{nio.pcap_output_file}"')
        # Markers carried by the NIO attach to the anchor (AF_PACKET taps) —
        # the anchor is the interface, not a relay bridge.
        await self._ubridge_apply_markers(anchor, nio)
        # Impairment filters become one tc netem qdisc on the anchor
        # (restored here on node restart, like the capture above); bpf
        # expressions become cls_bpf match-drop classifiers and
        # frequency_drop/quota/window_drop become the eBPF stateful
        # classifier.
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
        await self._ubridge_send(
            "bridge add_nio_udp {bridge_name} {lport} {rhost} {rport}".format(
                bridge_name=bridge_name, lport=nio.lport, rhost=nio.rhost, rport=nio.rport
            )
        )
        if nio.capturing:
            await self._ubridge_send(
                'bridge start_capture {bridge_name} "{pcap_file}"'.format(
                    bridge_name=bridge_name, pcap_file=nio.pcap_output_file
                )
            )
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
        create.
        """

        await self._ubridge_apply_markers(anchor, nio)
        # The netem apply resets the interface first (the kernel merges
        # optional netem attrs on replace), so everything anchored on clsact
        # must re-apply after it: bpf drops flush + re-add, eBPF modes re-set.
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
            cmd = 'marker add_kernel {name} {ifc} "{bpf}"'.format(name=name, ifc=bridge_name, bpf=bpf)
            if tag is not None:
                cmd += f" tag {tag}"
            if link_id:
                cmd += f" link {link_id}"
            if direction is not None:
                cmd += f" dir {direction}"
            linktype = self._marker_linktype(data_link_type)
            if linktype is not None:
                cmd += f" linktype {linktype}"
            cmd += ' pcap "{path}"'.format(path=pcap_path)
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
    def _netem_command_parts(filters):
        """
        Build the ``tc netem set`` keyword sequence (in the frozen grammar
        order: delay/jitter, loss|gemodel, dup, corrupt, reorder, rate,
        limit, distribution, seed) plus the set of capability tokens the
        sequence needs beyond the original netem surface. Original-surface
        keywords (delay, jitter, loss, corrupt, dup) need no probe; the
        extension tokens (rate, reorder, gemodel, dist, seed, limit) are
        checked against ``tc capabilities`` by the caller. ``correl`` has no
        token of its own in the capabilities list, so it gates on "rate" as
        the netem-extension build marker.

        :param filters: NIO filters dictionary ({"delay": [ms, jitter, dist], ...})

        :returns: (keyword sequence, required extension tokens)
        """

        def values_of(key):
            # tolerate the legacy bare-value shape ({"packet_loss": 10})
            values = filters.get(key)
            if isinstance(values, (list, tuple)):
                return list(values)
            return [values] if values else []

        parts = []
        ext_tokens = set()

        delay = values_of("delay")
        if delay:
            parts.append(f"delay {int(delay[0])}")
            if len(delay) > 1 and int(delay[1]):
                parts.append(f"jitter {int(delay[1])}")

        gemodel = values_of("gemodel")
        if gemodel:
            segment = f"loss gemodel {int(gemodel[0])}"
            if len(gemodel) > 1:
                segment += f" {int(gemodel[1])}"
                if len(gemodel) > 2:
                    segment += f" {int(gemodel[2])}"
            parts.append(segment)
            ext_tokens.add("gemodel")
        else:
            loss = values_of("packet_loss")
            if loss and int(loss[0]):
                parts.append(f"loss {int(loss[0])}")
                if len(loss) > 1 and int(loss[1]):
                    parts.append(f"correl {int(loss[1])}")
                    ext_tokens.add("rate")  # correl: extension build marker

        duplicate = values_of("duplicate")
        if duplicate and int(duplicate[0]):
            parts.append(f"dup {int(duplicate[0])}")
            if len(duplicate) > 1 and int(duplicate[1]):
                parts.append(f"correl {int(duplicate[1])}")
                ext_tokens.add("rate")  # correl: extension build marker

        corrupt = values_of("corrupt")
        if corrupt and int(corrupt[0]):
            parts.append(f"corrupt {int(corrupt[0])}")

        reorder = values_of("reorder")
        if reorder:
            segment = f"reorder {int(reorder[0])}"
            if len(reorder) > 1 and int(reorder[1]):
                segment += f" correl {int(reorder[1])}"
            if len(reorder) > 2 and int(reorder[2]):
                segment += f" gap {int(reorder[2])}"
            parts.append(segment)
            ext_tokens.add("reorder")

        rate = values_of("rate")
        if rate and str(rate[0]).strip():
            parts.append(f"rate {str(rate[0]).strip()}")
            ext_tokens.add("rate")

        limit = values_of("limit")
        if limit and int(limit[0]):
            parts.append(f"limit {int(limit[0])}")
            ext_tokens.add("limit")

        if delay and len(delay) > 2 and str(delay[2]).strip().lower() not in ("", "uniform"):
            # "uniform" is the kernel default — emitting nothing keeps the
            # command compatible with the original netem surface.
            parts.append(f"distribution {str(delay[2]).strip().lower()}")
            ext_tokens.add("dist")

        seed = values_of("seed")
        if seed and int(seed[0]):
            # 0 is the "disabled" convention everywhere else — treat it so
            # here too (the controller's inactive-filter pass drops it).
            parts.append(f"seed {int(seed[0])}")
            ext_tokens.add("seed")

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

        parts, ext_tokens = self._netem_command_parts(filters)
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
        lines = [line.strip() for line in (bpf[0].split("\n") if bpf else []) if line.strip()]
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
                await self._ubridge_send(
                    'tc bpf_drop add "{ifc}" {prio} "{expr}"'.format(ifc=host_ifc, prio=10 + offset, expr=line)
                )
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
        fixed order nth → quota → window. A mode is only sent when
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

        def values_of(key):
            values = filters.get(key)
            if isinstance(values, (list, tuple)):
                return list(values)
            return [values] if values else []

        frequency = values_of("frequency_drop")
        quota = values_of("quota")
        window = values_of("window_drop")
        requested = {filter_type: values_of(filter_type) for filter_type in FILTER_EBPF_MODES}
        if not any(requested.values()) and self._ubridge_tc_caps is None:
            # Nothing to set and nothing was ever installed (no probe yet) —
            # skip touching an old uBridge entirely.
            return
        caps = await self._ubridge_tc_capabilities()
        # A mode is usable iff ebpf=1 and the build declares its token
        # (ebpf_modes); builds predating the field keep their shipped modes.
        modes = usable_ebpf_modes(caps)
        if not any(requested.values()):
            # Only modes this build declares can ever have been installed —
            # sending "off" for an undeclared mode would hit an unknown
            # command; "off" is idempotent in uBridge.
            for filter_type, mode in FILTER_EBPF_MODES.items():
                if mode in modes:
                    await self._ubridge_send(f'tc {mode}_drop "{host_ifc}" off')
            return
        unsupported = sorted(f for f, values in requested.items() if values and FILTER_EBPF_MODES[f] not in modes)
        if unsupported:
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
        if frequency:
            # relay semantics: -1 = drop everything, N = every Nth packet
            nth = 1 if int(frequency[0]) == -1 else int(frequency[0])
            await self._ubridge_send(f'tc nth_drop "{host_ifc}" {nth}')
        elif "nth" in modes:
            await self._ubridge_send(f'tc nth_drop "{host_ifc}" off')
        if quota:
            await self._ubridge_send(
                'tc quota_drop "{ifc}" {bytes} {pct}'.format(ifc=host_ifc, bytes=int(quota[0]), pct=int(quota[1]))
            )
        elif "quota" in modes:
            await self._ubridge_send(f'tc quota_drop "{host_ifc}" off')
        if window:
            # [start, outage, chance, period?, jitter?] — start is relative
            # to this apply (the schedule restarts on every reconcile).
            params = " ".join(str(int(v)) for v in window)
            await self._ubridge_send(f'tc window_drop "{host_ifc}" {params}')
        elif "window" in modes:
            await self._ubridge_send(f'tc window_drop "{host_ifc}" off')
