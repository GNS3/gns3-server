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
Kernel-datapath machinery for DockerVM, extracted from docker_vm.py: the
veth pair lifecycle (deterministic names, creation, teardown together with
the per-link kernel bridges), the adapter carrier control, the kernel
marker primitives and the tc packet-filter translation (netem, classic-BPF
match-drop, eBPF stateful drops). Every method runs with a DockerVM
instance as ``self`` and reads the same state (_kernel_veths,
_ubridge_tc_caps, the uBridge hypervisor through the BaseNode helpers).
"""

import os
import contextlib

from gns3server.utils.tc_capabilities import FILTER_EBPF_MODES, parse_tc_capabilities, usable_ebpf_modes
from gns3server.compute.ubridge.ubridge_error import UbridgeError, UbridgeNamespaceError

from ..nios.nio_bridge import NIOBridge
from .docker_error import DockerError

import logging

log = logging.getLogger(__name__)


class DockerKernelDatapathMixin:
    """
    The kernel-datapath half of a Docker node — consumed by DockerVM so
    docker_vm.py stays focused on the container lifecycle.
    """

    def _veth_names(self, adapter_number, port_number=0):
        """
        Deterministic veth pair names for a kernel-datapath adapter port.
        The host end stays in the root namespace (enslaved to the per-link
        kernel bridge); the guest end is moved into the container namespace
        and renamed. The ``gv``/``gc`` prefixes keep these out of the ``gns3``
        bridge/TAP name space and serve as search keys for stale-interface
        cleanup. 8 hex chars of the node id + adapter/port keep the names
        unique and within IFNAMSIZ (15).
        """

        suffix = f"{self._id.replace('-', '')[:8]}e{adapter_number}p{port_number}"
        return f"gv{suffix}", f"gc{suffix}"

    async def _create_veth(self, adapter_number, port_number=0):
        """
        Create the adapter's unified veth pair: the guest end moves into the
        container namespace as eth{N} (the role the TAP used to play on the
        relay path), the host end stays in the root namespace with carrier
        off until a link attaches. Both datapaths anchor here — kernel links
        enslave the host end into a Linux bridge; relay links attach it to
        the uBridge relay via AF_PACKET.
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(
                    name=self.name, adapter_number=adapter_number
                )
            )

        host_ifc, guest_ifc = self._veth_names(adapter_number, port_number)
        # The host end lives in the root namespace and survives container
        # death: best-effort removal of a stale pair from a previous run
        # (unclean stop or crash) before recreating it.
        for stale_ifc in (host_ifc, guest_ifc):
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'docker delete_veth "{stale_ifc}"')

        mac_address = self._adapter_mac_address(adapter_number)
        try:
            await self._ubridge_send(f'docker create_veth "{host_ifc}" "{guest_ifc}"')
            # create_veth leaves the host end UP; carrier must be off until
            # a link attaches (mirrors the old "bridge add_nio_tap ... off").
            await self._ubridge_send(f'link set "{host_ifc}" down')
            try:
                await self._ubridge_send(f"docker set_mac_addr {guest_ifc} {mac_address}")
            except UbridgeError:
                log.warning(f"Could not set MAC address {mac_address} on interface {guest_ifc}")

            ifname = self._get_container_ifname(adapter_number)
            log.debug(f"Move container {self.name} adapter {guest_ifc} -> {ifname} in ns {self._namespace}")
            try:
                await self._ubridge_send(f"docker move_to_ns {guest_ifc} {self._namespace} {ifname}")
            except UbridgeError as e:
                raise UbridgeNamespaceError(e)
        except UbridgeNamespaceError:
            raise
        except Exception:
            # Don't leave a half-created pair behind (the next start would
            # fail on create_veth EEXIST until the stale sweep runs).
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'docker delete_veth "{host_ifc}"')
            raise

        adapter.host_ifc = host_ifc
        self._kernel_veths[(adapter_number, port_number)] = host_ifc
        log.debug(
            "Created veth adapter {adapter_number} port {port_number} with MAC address {mac_address} in namespace {namespace}".format(
                adapter_number=adapter_number,
                port_number=port_number,
                mac_address=mac_address,
                namespace=self._namespace,
            )
        )

    async def _remove_kernel_veths(self):
        """
        Delete the root-namespace veth host ends. Unlike relay TAPs (which die
        with the container network namespace) the host end outlives the
        container and must be removed explicitly. Deleting an enslaved veth
        detaches it from its bridge automatically.

        The per-link kernel bridges go too: deleting a node (or closing a
        project) never runs the link-teardown path, so a bridge whose ports
        just disappeared would stay behind as an empty orphan. Both link
        endpoints run this — the peer's port still enslaved makes the delete
        fail with EBUSY (suppressed) and the last one wins, the same
        contract as _remove_kernel_nio. A node restart re-creates the bridge
        from the NIO in _connect_nio, so nothing is lost by deleting it.
        """

        if self.ubridge:
            for host_ifc in self._kernel_veths.values():
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'docker delete_veth "{host_ifc}"')
            for adapter in self._ethernet_adapters:
                for nio in adapter.ports.values():
                    if isinstance(nio, NIOBridge):
                        with contextlib.suppress(UbridgeError):
                            await self._ubridge_send(f'brctl delete "{nio.bridge}"')
        self._kernel_veths.clear()

    async def _set_adapter_carrier(self, adapter_number, connected, port_number=0):
        """Replicate a Docker adapter's connection state on its host interface.

        Kernel-datapath adapters toggle the veth host end's admin state (the
        container end loses carrier when its peer is down); relay adapters
        toggle the TAP carrier from the uBridge fd holder.
        """

        host_ifc = self._kernel_veths.get((adapter_number, port_number))
        if host_ifc is not None:
            state = "up" if connected else "down"
            await self._ubridge_send(f'link set "{host_ifc}" {state}')
            return

        bridge_name = self._bridge_name(adapter_number, port_number)
        state = "on" if connected else "off"
        await self._ubridge_send(f"bridge set_nio_tap_carrier {bridge_name} {state}")

    def _kernel_marker_anchor(self, anchor):
        """
        Whether *anchor* names one of this container's kernel-datapath veth
        host ends. Marker anchors are polymorphic: a relay bridge name on the
        relay datapath, the veth host interface on the kernel datapath. A veth
        name can never collide with a uBridge bridge name (relay bridges are
        ``bridge{adapter}``, veths are ``gv…e…p…``).
        """

        return anchor in self._kernel_veths.values()

    async def _ubridge_add_marker_filter(
        self, bridge_name, name, bpf, pcap_path, tag=None, link_id=None, direction=None, data_link_type=None
    ):
        """
        Kernel-datapath variant of the `mark` filter attach: ``marker
        add_kernel`` binds an AF_PACKET socket to the veth host end. Keyword
        pairs and semantics (match → MARK signal + pcap append) are identical
        to the relay ``bridge add_packet_filter … mark`` command.
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
        veth host end. The netem-expressible types (delay, packet_loss,
        corrupt and the netem extensions rate/reorder/gemodel/duplicate/
        seed/limit) merge into a single qdisc — its egress covers the traffic
        entering this container, and with both link endpoints applying
        theirs, every direction of the link is impaired exactly once (the
        same net effect as the relay, where both directions cross the single
        filtered bridge).

        The kernel's netem replace MERGES optional attributes (rate,
        correlation, reorder, corrupt, gemodel, distribution: absent attr =
        previous value kept), so re-applying a filter set with a parameter
        *removed* would silently keep the old value. A ``tc reset`` before
        every ``netem set`` makes the re-apply a true reconcile (reset also
        drops clsact and its bpf_drop filters — the caller re-applies them
        right after in the same flow). An empty filter set is the reset
        alone.

        :param host_ifc: veth host-end interface name
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
                raise DockerError(
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
        matching drops the packet) into cls_bpf classifiers on the veth host
        end's clsact egress: ``tc bpf_drop`` compiles each line with libpcap
        (same compiler as the relay's bpf filter) and drops matches with a
        gact TC_ACT_SHOT. Reconcile is always flush + re-add — same-prio
        resend replaces the filter node in uBridge, and the flush drops
        lines the user removed.

        :param host_ifc: veth host-end interface name
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
            raise DockerError(
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
        classifier on the veth host end's clsact egress (prio 1, below
        bpf_drop's 10-99): ``frequency_drop`` becomes the exact every-Nth
        mode (``tc nth_drop``; -1 = drop everything maps to every 1st), the
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
        bridge, while each veth end's classifier counts only the traffic
        entering that container — with both endpoints applying theirs, each
        direction drops every Nth independently (their window schedules
        start ~simultaneously, so a round trip survives only when both
        directions are outside their windows).

        :param host_ifc: veth host-end interface name
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
                raise DockerError(
                    "Packet filter(s) {} on a kernel-datapath link need a uBridge with eBPF support "
                    "(tc capabilities reports no ebpf; setcap cap_bpf,cap_net_admin,cap_net_raw=ep on "
                    "the uBridge binary); upgrade uBridge on this compute or keep the link on the "
                    "relay datapath".format(", ".join(unsupported))
                )
            raise DockerError(
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

    async def _remove_kernel_markers(self, host_ifc):
        """
        Tear down every kernel marker anchored to *host_ifc*: the veth survives
        link deletion (it is the adapter interface, not the link), so the
        AF_PACKET sockets must be closed explicitly — otherwise a deleted
        link's markers would keep sniffing and signaling. Mirrors the relay
        datapath where deleting the uBridge bridge silently drops its filters.
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

    async def _remove_kernel_nio(self, nio, adapter_number, port_number=0):
        """
        Detach a kernel-datapath adapter port from its per-link kernel bridge.
        Both endpoints run this concurrently: deleting a bridge that still has
        the peer's port enslaved fails with EBUSY, so the last endpoint to
        remove its port wins the deletion and the loser's failure is expected
        and suppressed.
        """

        host_ifc = self._kernel_veths.get((adapter_number, port_number))
        if host_ifc is not None:
            await self._remove_kernel_markers(host_ifc)
            # The veth survives link deletion, so an orphaned netem qdisc
            # would keep impairing whatever attaches to the adapter next
            # (kernel link or relay). Best-effort: ENOENT just means no
            # qdisc was attached.
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'tc reset "{host_ifc}"')
            if self.status == "started":
                await self._set_adapter_carrier(adapter_number, False, port_number)
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'brctl delif "{nio.bridge}" "{host_ifc}"')
        with contextlib.suppress(UbridgeError):
            await self._ubridge_send(f'brctl delete "{nio.bridge}"')
