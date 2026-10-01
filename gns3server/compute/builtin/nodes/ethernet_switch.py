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

"""
Ethernet switch backed by a Linux kernel bridge driven through uBridge's
``brctl`` module.

The historical GNS3 Ethernet switch was an emulated L2 device inside Dynamips
(``ethsw``). This implementation replaces it with a *real* Linux kernel bridge:
one bridge per switch node, managed over uBridge's hypervisor socket. Each
switch port is a persistent TAP that plays two roles at once -- uBridge holds
its file descriptor as a ``nio_tap`` relay endpoint, and the same TAP is
enslaved to the kernel bridge as a port. This dual-role TAP is exactly the
pattern the Cloud node already uses for host bridges (see
``cloud.py::_add_linux_ethernet``).

Data path (UDP link mode)::

    peer --UDP-- ubridge[nio_udp <-> nio_tap(tap)] --tap-- kernel bridge --tap-- ... (other ports)

The kernel bridge performs MAC learning/forwarding and VLAN filtering; uBridge
is only the per-port UDP transport (uBridge is strictly a 2-NIO pipe, it cannot
be the switch). ESW ``access``/``dot1q``/``qinq`` port modes are composed from
the ``brctl`` VLAN primitives here -- see ``_apply_port_vlan``.
"""

import contextlib
import logging
import os

from gns3server.compute.ubridge.ubridge_error import UbridgeError

from ...base_node import BaseNode
from ...error import NodeError
from ...kernel_datapath import KernelDatapathMixin
from ...nios.nio_anchor import NIOAnchor
from ...nios.nio_udp import NIOUDP

log = logging.getLogger(__name__)

# VLAN ethertypes the Linux kernel bridge can realise. ``brctl setvlanproto``
# accepts only 0x8100 (802.1Q) and 0x88a8 (802.1ad). The GNS3 schema also allows
# the legacy 0x9100/0x9200 QinQ ethertypes; the kernel bridge cannot do those, so
# configuring them on a qinq port is rejected.
_SUPPORTED_VLAN_ETHERTYPE = {"0x8100", "0x88a8"}
_QINQ_ETHERTYPE = "0x88a8"


class EthernetSwitch(KernelDatapathMixin, BaseNode):
    """
    Ethernet switch.

    :param name: name for this switch
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param ports: initial switch ports
    """

    def __init__(self, name, node_id, project, manager, console=None, console_type=None, ports=None):

        super().__init__(name, node_id, project, manager, console=console, console_type=console_type or "none")
        # The switch has no console; ``console_type="none"`` makes BaseNode skip
        # reserving a TCP console port entirely.
        self._ubridge_require_privileged_access = True

        self._nios = {}
        self._tap_by_port = {}  # port_number -> kernel TAP enslaved to the bridge
        self._kernel_ports = {}  # port_number -> foreign anchor absorbed into the bridge
        # port_number -> the other end's name, for the ports that are one end
        # of a switch-to-switch cascade veth pair (created when missing,
        # destroyed on teardown — symmetrically, from either side). Absent
        # for absorbed anchors and relay ports.
        self._cascade_peers = {}
        self._bridge_name = None  # kernel bridge interface name (allocated on start)
        self._bridge_created = False
        self._bridge_proto_set = False  # whether ``brctl setvlanproto`` has been applied
        self._ubridge_tc_caps = None  # probed once per uBridge process (mixin)
        # Idempotency flag for start(). Decoupled from ``status`` so the node can
        # report "started" (always-on, like the ESW) while ``duplicate_node`` still
        # sees status "stopped" and refuses only genuinely running stateful nodes.
        self._started = False

        if ports is None:
            # 8 access ports in VLAN 1 by default, matching the historical ESW.
            self._ports_mapping = []
            for port_number in range(0, 8):
                self._ports_mapping.append(
                    {"port_number": port_number, "name": f"Ethernet{port_number}", "type": "access", "vlan": 1}
                )
        else:
            self._ports_mapping = self._normalize_ports(ports)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize_ports(ports):
        """Assign sequential port numbers/names like the Dynamips ESW did."""
        port_number = 0
        normalized = []
        for port in ports:
            port = dict(port)
            port["name"] = f"Ethernet{port_number}"
            port["port_number"] = port_number
            normalized.append(port)
            port_number += 1
        return normalized

    def _ubridge_bridge_name(self, port_number):
        """Name of the per-port uBridge relay bridge (not a kernel interface)."""
        return f"{self._id}-{port_number}"

    def _tap_name(self, port_number):
        """Kernel TAP name for a port: ``<bridge>-<port>`` (host-unique via the bridge)."""
        return f"{self._bridge_name}-{port_number}"

    def _port_settings(self, port_number):
        for port in self._ports_mapping:
            if port["port_number"] == port_number:
                return port
        return None

    # ------------------------------------------------------------------ #
    # properties / serialisation
    # ------------------------------------------------------------------ #

    @property
    def nios(self):
        return self._nios

    @property
    def ports_mapping(self):
        return self._ports_mapping

    @ports_mapping.setter
    def ports_mapping(self, ports):
        if ports != self._ports_mapping:
            if len(self._nios) > 0 and len(ports) != len(self._ports_mapping):
                raise NodeError("Cannot change the port count of a switch that is already connected.")
            self._ports_mapping = self._normalize_ports(ports)

    @property
    def console(self):
        return self._console

    @console.setter
    def console(self, console):
        self._console = console

    @property
    def console_type(self):
        return self._console_type

    @console_type.setter
    def console_type(self, console_type):
        self._console_type = console_type

    def asdict(self):

        return {
            "name": self.name,
            "usage": self.usage,
            "node_id": self.id,
            "project_id": self.project.id,
            "ports_mapping": self._ports_mapping,
            "console": self.console,
            "console_type": self.console_type,
            # The switch is always-on once created (a kernel bridge), like the ESW.
            "status": "started",
        }

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #

    async def create(self):
        """
        Creates this switch.
        """

        await self.start()
        log.debug(f'Ethernet switch "{self._name}" [{self._id}] has been created')

    async def start(self):
        """
        Starts this switch: bring up uBridge, create the kernel bridge, and
        re-wire any ports already bound before a restart.
        """

        if not self._started:
            if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
                await self._stop_ubridge()
            await self._start_ubridge(self._ubridge_require_privileged_access)
            # A fresh uBridge process: the tc capabilities must be probed again.
            self._ubridge_tc_caps = None
            await self._ensure_bridge()
            for port_number in self._nios:
                if self._nios[port_number]:
                    try:
                        if isinstance(self._nios[port_number], NIOAnchor):
                            await self._add_kernel_port(self._nios[port_number], port_number)
                        else:
                            await self._add_ubridge_connection(self._nios[port_number], port_number)
                    except (UbridgeError, NodeError) as e:
                        self._started = False
                        raise e
            self._started = True

    async def _ensure_bridge(self):
        """
        Creates the per-node kernel bridge once and enables VLAN filtering.
        Applies the bridge-level QinQ ethertype if any port needs it.

        The bridge name is deterministic: ``gns3`` + the first 6 hex chars of
        this switch's UUID (kernel interface names are ≤ 15 chars).  A stale
        bridge from a previous crash is deleted first so ``brctl create`` never
        hits EEXIST.
        """

        if self._bridge_created:
            return
        # deterministic short name — 10 chars, always fits the 15-char kernel cap
        self._bridge_name = "gns3" + self._id.replace("-", "")[:6]
        # crash recovery: best-effort delete any leftover bridge
        try:
            await self._ubridge_send(f'brctl delete "{self._bridge_name}"')
        except UbridgeError:
            pass  # not found = nothing to clean
        await self._ubridge_send(f'brctl create "{self._bridge_name}"')
        # ``brctl create`` leaves the bridge DOWN; bring it UP so it forwards.
        await self._ubridge_send(f'link set "{self._bridge_name}" up')
        await self._ubridge_send(f'brctl vlanfiltering "{self._bridge_name}" on')
        self._bridge_created = True
        await self._apply_bridge_proto_if_needed()

    async def _apply_bridge_proto_if_needed(self):
        """
        If any port is a QinQ port using the 802.1ad ethertype (0x88a8), switch
        the whole bridge to that protocol. A Linux bridge has a single VLAN
        protocol, so mixed QinQ ethertypes within one switch are not supported.
        """

        proto = None
        for port in self._ports_mapping:
            if port.get("type") == "qinq":
                # normalise case: the schema carries uppercase (e.g. "0x88A8") but
                # brctl setvlanproto wants lowercase hex
                ethertype = port.get("ethertype", "0x8100").lower()
                if ethertype not in _SUPPORTED_VLAN_ETHERTYPE:
                    raise NodeError(
                        f"VLAN ethertype {ethertype} is not supported by the Linux bridge "
                        f"(only 0x8100/0x88a8) for QinQ port {port['name']}"
                    )
                if ethertype == _QINQ_ETHERTYPE:
                    proto = _QINQ_ETHERTYPE
        if proto and not self._bridge_proto_set:
            await self._ubridge_send(f'brctl setvlanproto "{self._bridge_name}" {proto}')
            self._bridge_proto_set = True

    async def delete(self):
        """
        Deletes this switch.
        """

        return await self.close()

    async def close(self):
        """
        Closes this switch: release UDP ports, tear down the kernel bridge, stop uBridge.
        """

        if not (await super().close()):
            return False

        for nio in self._nios.values():
            if nio and isinstance(nio, NIOUDP):
                self.manager.port_manager.release_udp_port(nio.lport, self._project)
        self._nios.clear()

        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running() and self._bridge_created:
            # Project close runs every node's close concurrently: a peer's
            # anchor may still be enslaved at this instant (its node's close
            # is in flight), which would make the bridge delete fail EBUSY
            # and leak an empty bridge. Detach every member we know first —
            # a peer anchor that is already gone answers ENOENT (suppressed;
            # the kernel removed it with the interface), and our own TAPs go
            # with the relay teardown — so the delete always sees an empty
            # bridge. The foreign anchors themselves are not ours to delete.
            for anchor in self._kernel_ports.values():
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'brctl delif "{self._bridge_name}" "{anchor}"')
            # Cascade pairs die with the switch: the delif above released
            # this end, and deleting it takes the peer end (still enslaved
            # on the other side, if that close is still in flight) out of
            # its bridge as well — which is where the pair is headed anyway,
            # the link is going away with the project. The other switch's
            # own delete answers ENOENT, suppressed.
            for port_number in self._cascade_peers:
                anchor = self._kernel_ports.get(port_number)
                if anchor is not None:
                    with contextlib.suppress(UbridgeError):
                        await self._ubridge_send(f'docker delete_veth "{anchor}"')
            for tap in self._tap_by_port.values():
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'brctl delif "{self._bridge_name}" "{tap}"')
            try:
                # Deleting the bridge releases any enslaved TAPs; uBridge destroys
                # them when it stops below.
                await self._ubridge_send(f'brctl delete "{self._bridge_name}"')
            except UbridgeError as e:
                log.warning(f'Could not delete kernel bridge "{self._bridge_name}": {e}')
            self._bridge_created = False
            self._bridge_proto_set = False
            self._bridge_name = None
        self._tap_by_port.clear()
        self._kernel_ports.clear()
        self._cascade_peers.clear()
        self._started = False

        await self._stop_ubridge()
        log.debug(f'Ethernet switch "{self._name}" [{self._id}] has been closed')
        return True

    # ------------------------------------------------------------------ #
    # per-port wiring
    # ------------------------------------------------------------------ #

    async def add_nio(self, nio, port_number):
        """
        Adds a NIO as a new port on this switch.

        Two kinds are accepted: a UDP NIO (relay datapath — the per-port
        uBridge relay ends in a bridge TAP) and the kernel datapath's
        NIOAnchor (the peer's anchor is absorbed straight into this switch's
        kernel bridge).

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        if port_number in self._nios:
            raise NodeError(f"Port {port_number} isn't free")
        if not isinstance(nio, (NIOUDP, NIOAnchor)):
            raise NodeError("Ethernet switch ports only support UDP NIOs and anchor NIOs")

        log.debug(f'Ethernet switch "{self._name}" [{self._id}]: NIO {nio} bound to port {port_number}')
        try:
            await self.start()
            if isinstance(nio, NIOAnchor):
                await self._add_kernel_port(nio, port_number)
            else:
                await self._add_ubridge_connection(nio, port_number)
            self._nios[port_number] = nio
        except (NodeError, UbridgeError) as e:
            log.error(f'Cannot add NIO on Ethernet switch "{self._name}": {e}')
            await self._stop_ubridge()
            self.status = "stopped"
            self._nios[port_number] = nio
            self.project.emit("log.error", {"message": str(e)})

    async def _add_ubridge_connection(self, nio, port_number):
        """
        Wires one port: a per-port uBridge relay (nio_tap <-> nio_udp) whose TAP
        is enslaved to the kernel bridge, with the port's VLAN mode applied.
        """

        port_settings = self._port_settings(port_number)
        if port_settings is None:
            raise NodeError(f"Port {port_number} doesn't exist on Ethernet switch '{self.name}'")

        ubridge_bridge = self._ubridge_bridge_name(port_number)
        tap = self._tap_name(port_number)

        # per-port uBridge relay -- uBridge holds the TAP fd
        await self._ubridge_send(f"bridge create {ubridge_bridge}")
        await self._ubridge_send(f'bridge add_nio_tap {ubridge_bridge} "{tap}"')
        # enslave the same TAP to the kernel bridge (the cloud.py::_add_linux_ethernet move)
        await self._ubridge_send(f'brctl addif "{self._bridge_name}" "{tap}"')
        # VLAN membership for this port's access/trunk/qinq mode
        await self._apply_port_vlan(port_settings, tap)
        # GNS3 link endpoint
        await self._ubridge_send(f"bridge add_nio_udp {ubridge_bridge} {nio.lport} {nio.rhost} {nio.rport}")
        await self._ubridge_apply_filters(ubridge_bridge, nio.filters)
        await self._ubridge_apply_markers(ubridge_bridge, nio)
        if nio.capturing:
            await self._ubridge_send(f'bridge start_capture {ubridge_bridge} "{nio.pcap_output_file}"')
        await self._ubridge_send(f"bridge start {ubridge_bridge}")
        self._tap_by_port[port_number] = tap

    # ------------------------------------------------------------------ #
    # kernel datapath: absorb the peer's anchor (fast path)
    # ------------------------------------------------------------------ #

    def _kernel_host_ifc(self, adapter_number, port_number=0):
        """
        The foreign anchor absorbed on a port, or None for a relay port. The
        switch has no adapters, so *adapter_number* is always 0.
        """

        return self._kernel_ports.get(port_number)

    def _kernel_anchors(self):
        """
        Every absorbed anchor — the interfaces this switch bridges and on
        which kernel markers may attach (the mixin's marker polymorphism).
        """

        return set(self._kernel_ports.values())

    def _kernel_error(self, message):
        return NodeError(message)

    async def _add_kernel_port(self, nio, port_number):
        """
        Absorbs the peer's anchor for one port: joins the anchor straight to
        this switch's kernel bridge and applies the port's VLAN mode — no
        relay, no per-port TAP, the peer anchor *is* the port.

        The anchor only exists on the host while the peer is running (its
        compute creates it at node start), so a link created against a
        stopped peer defers the join: the port remembers the anchor and
        ``update_nio`` completes the wiring when the controller re-pushes
        the NIO after the peer starts (UdpLink.node_started). A peer
        restart can also replace the interface under the same name, so the
        membership is re-checked rather than assumed.

        The link state the anchored end carries (capture, markers, tc
        impairments) is applied by the shared mixin flow: NIOAnchor reports
        no per-link bridge, so only the link state is applied here, while
        the bridge membership above is this switch's own.
        """

        port_settings = self._port_settings(port_number)
        if port_settings is None:
            raise NodeError(f"Port {port_number} doesn't exist on Ethernet switch '{self.name}'")

        anchor = nio.anchor
        if nio.peer is not None:
            # Cascade: this port is one end of a link-owned veth pair. Both
            # sides create the pair when their end is missing — the two
            # uBridge processes may race (the project-open batch even wires
            # different nodes concurrently), one create wins and the other's
            # failure is re-checked against the kernel: an existing pair
            # means the race was lost, anything else is a real failure the
            # link must not paper over. A pre-existing end (this switch
            # restarted, or a leftover from a previous life of this link id
            # — the names are a function of it) is reused as-is: the other
            # end may still be a live port of the peer switch, and a stale
            # tc qdisc is all a reused end can carry (VLAN entries die with
            # the bridge that held them).
            self._cascade_peers[port_number] = nio.peer
            if not os.path.exists(f"/sys/class/net/{anchor}"):
                try:
                    await self._ubridge_send(f'docker create_veth "{anchor}" "{nio.peer}"')
                except UbridgeError:
                    if not os.path.exists(f"/sys/class/net/{anchor}"):
                        raise
            else:
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'tc reset "{anchor}"')
        # Register before _kernel_attach: the marker reconcile recognises
        # kernel anchors through _kernel_anchors().
        self._kernel_ports[port_number] = anchor
        if not os.path.exists(f"/sys/class/net/{anchor}"):
            log.info(
                'Ethernet switch "{name}" [{id}]: anchor {anchor} for port {port} does not exist yet '
                "(peer not started); join deferred".format(
                    name=self._name, id=self._id, anchor=anchor, port=port_number
                )
            )
            return
        try:
            await self._ubridge_send(f'brctl addif "{self._bridge_name}" "{anchor}"')
            await self._apply_port_vlan(port_settings, anchor)
            await self._kernel_attach(anchor, nio)
            await self._set_adapter_carrier(0, not nio.suspend, port_number)
        except (NodeError, UbridgeError):
            self._kernel_ports.pop(port_number, None)
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'brctl delif "{self._bridge_name}" "{anchor}"')
            raise

    async def _remove_kernel_port(self, port_number):
        """
        Releases an absorbed anchor: detaches the link state (markers,
        impairments, carrier) and takes the anchor out of the switch bridge.
        The anchor itself belongs to the peer and survives. A cascade end
        dies with the link instead: deleting one veth end destroys the pair
        (and the peer end with it), so either side's teardown converges on
        the same gone pair — the other side's delif then answers ENOENT,
        suppressed.
        """

        anchor = self._kernel_ports.pop(port_number, None)
        peer = self._cascade_peers.pop(port_number, None)
        if anchor is None:
            return
        await self._remove_kernel_markers(anchor)
        with contextlib.suppress(UbridgeError):
            await self._ubridge_send(f'tc reset "{anchor}"')
        if self._bridge_created:
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'brctl delif "{self._bridge_name}" "{anchor}"')
        with contextlib.suppress(UbridgeError):
            await self._ubridge_send(f'link set "{anchor}" down')
        if peer is not None:
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'docker delete_veth "{anchor}"')

    async def _delete_ubridge_connection(self, port_number):
        """
        Tears down one port's wiring: release the TAP from the bridge and delete
        the per-port uBridge relay.
        """

        tap = self._tap_by_port.pop(port_number, None)
        ubridge_bridge = self._ubridge_bridge_name(port_number)
        if tap is not None and self._bridge_created:
            try:
                await self._ubridge_send(f'brctl delif "{self._bridge_name}" "{tap}"')
            except UbridgeError as e:
                log.warning(f'Could not remove TAP "{tap}" from bridge "{self._bridge_name}": {e}')
        try:
            await self._ubridge_send(f"bridge delete {ubridge_bridge}")
        except UbridgeError as e:
            log.warning(f"Could not delete uBridge bridge {ubridge_bridge}: {e}")

    async def remove_nio(self, port_number):
        """
        Removes the specified NIO from this switch.

        :param port_number: allocated port number
        :returns: the NIO that was bound to the allocated port
        """

        if port_number not in self._nios:
            raise NodeError(f"Port {port_number} is not allocated")

        await self.stop_capture(port_number)
        nio = self._nios[port_number]
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)

        log.debug(f'Ethernet switch "{self._name}" [{self._id}]: NIO {nio} removed from port {port_number}')
        del self._nios[port_number]
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            if isinstance(nio, NIOAnchor):
                await self._remove_kernel_port(port_number)
            else:
                await self._delete_ubridge_connection(port_number)
        return nio

    def get_nio(self, port_number):
        """
        Gets a port NIO binding.

        :param port_number: port number
        :returns: NIO instance
        """

        if port_number not in self._nios:
            raise NodeError(f"Port {port_number} is not connected")
        return self._nios[port_number]

    async def update_nio(self, port_number, nio):
        """
        Re-applies filters/markers (and carrier) for a port when a link is
        updated: on the per-port uBridge relay for a relay port, on the
        absorbed anchor (tc + kernel markers) for a kernel port.
        """

        if not (self._ubridge_hypervisor and self._ubridge_hypervisor.is_running()):
            return
        if port_number in self._kernel_ports:
            anchor = self._kernel_ports[port_number]
            if not os.path.exists(f"/sys/class/net/{self._bridge_name}/brif/{anchor}"):
                # Not joined (a deferred link whose peer has just started, or
                # a peer restart that replaced its anchor under the same
                # name): complete the whole wiring now.
                await self._add_kernel_port(nio, port_number)
                return
            # Kernel port: reconcile on the anchor — markers, tc impairments
            # and the carrier the suspend flag drives. No re-joining, no
            # VLAN re-programming (the port mode did not change).
            await self._kernel_update(anchor, nio)
            await self._set_adapter_carrier(0, not nio.suspend, port_number)
            return
        ubridge_bridge = self._ubridge_bridge_name(port_number)
        await self._ubridge_apply_filters(ubridge_bridge, nio.filters)
        await self._ubridge_apply_markers(ubridge_bridge, nio)

    # ------------------------------------------------------------------ #
    # VLAN mode translation
    # ------------------------------------------------------------------ #

    async def _reconfigure_port_vlan(self, iface, old_settings, new_settings):
        """
        Moves one port's VLAN membership from its previous mode to the new one
        **in place**: the port never leaves the bridge, so there is no traffic
        gap, no FDB flush, and nothing that detaches an interface this switch
        does not own (an absorbed kernel anchor belongs to the peer's node —
        re-enslaving it from here is not this switch's business).

        Each mode's membership, as installed on a clean port by
        ``_apply_port_vlan``: access(N) = {N, PVID untagged}; dot1q(V) =
        {1..4094, tagged} plus V as PVID untagged (the all-VIDs entry is a
        single range entry); qinq(O) = {O, PVID untagged}. The transition
        deletes exactly the previous mode's entries the new mode does not
        want, then adds the new mode's entries — the dot1q range is added and
        deleted as one range operation.
        """

        old_type, old_vlan = old_settings["type"], int(old_settings["vlan"])
        new_type, new_vlan = new_settings["type"], int(new_settings["vlan"])
        if old_type == new_type and old_vlan == new_vlan:
            return

        br = self._bridge_name
        commands = []

        if old_type == "dot1q" and new_type != "dot1q":
            # the admits-all-VIDs range, the old native VLAN included in it
            commands.append(f'brctl vlan_del "{br}" "{iface}" 1 vid 4094')
        elif old_type == "dot1q":
            if old_vlan != new_vlan:
                commands.append(f'brctl vlan_del "{br}" "{iface}" {old_vlan}')
        elif new_type == "dot1q" or old_vlan != new_vlan:
            # access/qinq single-VID entry, replaced by the new mode's
            commands.append(f'brctl vlan_del "{br}" "{iface}" {old_vlan}')

        if new_type == "dot1q":
            if old_type != "dot1q":
                commands.append(f'brctl vlan_add "{br}" "{iface}" 1 vid 4094')
            commands.append(f'brctl vlan_add "{br}" "{iface}" {new_vlan} pvid untagged')
        else:
            commands.append(f'brctl vlan_add "{br}" "{iface}" {new_vlan} pvid untagged')

        for command in commands:
            await self._ubridge_send(command)

    async def _apply_port_vlan(self, port_settings, tap):
        """
        Translates an ESW port mode into ``brctl`` VLAN primitives, for a
        **newly wired** port. The port must already be enslaved to the bridge
        and carry the default PVID 1.

        - access VLAN N: drop default 1, add N as PVID + egress untagged.
        - dot1q trunk (native N): drop default 1, admit all VIDs tagged, then mark
          the native VLAN PVID + untagged. (The ESW model declares only the native
          VLAN per trunk port, so the trunk admits all VIDs, like the emulated ESW.)
        - qinq (outer N): the bridge-level protocol is set separately; the port
          gets the service VLAN as PVID + untagged so customer frames are S-tagged.

        Mode *changes* on an already-wired port go through
        ``_reconfigure_port_vlan`` (in place, no re-enslaving) instead.
        """

        br = self._bridge_name
        port_type = port_settings["type"]
        vlan = int(port_settings["vlan"])

        if port_type == "access":
            await self._ubridge_send(f'brctl vlan_del "{br}" "{tap}" 1')
            await self._ubridge_send(f'brctl vlan_add "{br}" "{tap}" {vlan} pvid untagged')
        elif port_type == "dot1q":
            await self._ubridge_send(f'brctl vlan_del "{br}" "{tap}" 1')
            await self._ubridge_send(f'brctl vlan_add "{br}" "{tap}" 1 vid 4094')
            await self._ubridge_send(f'brctl vlan_add "{br}" "{tap}" {vlan} pvid untagged')
        elif port_type == "qinq":
            # setvlanproto is applied at the bridge level by _apply_bridge_proto_if_needed
            await self._ubridge_send(f'brctl vlan_del "{br}" "{tap}" 1')
            await self._ubridge_send(f'brctl vlan_add "{br}" "{tap}" {vlan} pvid untagged')
        else:
            raise NodeError(f"Unknown port type '{port_type}' on Ethernet switch '{self.name}'")

    async def update_port_settings(self, previous_mapping=None):
        """
        Reconciles port settings after a ``ports_mapping`` update. Only the
        wired ports whose mode/VLAN actually changed are touched, and each
        change is applied in place (``_reconfigure_port_vlan``) — no port is
        ever detached from the bridge just to change its VLANs, on the
        switch's own relay TAPs and on absorbed kernel anchors alike.

        :param previous_mapping: the ports_mapping as it was before this
            update (the caller's duty — the setter has already stored the new
            one); without it nothing can be diffed and no port is touched.
        """

        await self._apply_bridge_proto_if_needed()
        if not (self._ubridge_hypervisor and self._ubridge_hypervisor.is_running() and self._bridge_created):
            return

        previous = {port["port_number"]: port for port in (previous_mapping or [])}
        wired = dict(self._tap_by_port)
        for port_number, anchor in self._kernel_ports.items():
            wired[port_number] = anchor
        for port_number, iface in wired.items():
            new_settings = self._port_settings(port_number)
            if new_settings is None:
                continue
            old_settings = previous.get(port_number)
            if old_settings is None:
                # a wired port always has previous settings; without them a
                # diff is impossible and re-enslaving would be guessing
                log.warning(
                    'Ethernet switch "{name}" [{id}]: no previous settings for wired port {port}; '
                    "VLAN reconfiguration skipped".format(name=self._name, id=self._id, port=port_number)
                )
                continue
            await self._reconfigure_port_vlan(iface, old_settings, new_settings)

    # ------------------------------------------------------------------ #
    # capture
    # ------------------------------------------------------------------ #

    async def start_capture(self, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture on a port — on the per-port relay bridge for
        a relay port, on the absorbed anchor (AF_PACKET, capture start_kernel)
        for a kernel port.

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        nio = self.get_nio(port_number)
        if nio.capturing:
            raise NodeError(f"Packet capture is already activated on port {port_number}")
        nio.start_packet_capture(output_file)
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            anchor = self._kernel_ports.get(port_number)
            if anchor is not None:
                await self._ubridge_send(f'capture start_kernel {anchor} "{output_file}"')
            else:
                ubridge_bridge = self._ubridge_bridge_name(port_number)
                await self._ubridge_send(f'bridge start_capture {ubridge_bridge} "{output_file}"')
        log.debug(
            'Ethernet switch "{name}" [{id}]: starting packet capture on port {port}'.format(
                name=self.name, id=self.id, port=port_number
            )
        )

    async def stop_capture(self, port_number):
        """
        Stops a packet capture on a port.

        :param port_number: allocated port number
        """

        nio = self.get_nio(port_number)
        if not nio.capturing:
            return
        nio.stop_packet_capture()
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            if port_number in self._kernel_ports:
                await self._ubridge_send("capture stop_kernel")
            else:
                ubridge_bridge = self._ubridge_bridge_name(port_number)
                await self._ubridge_send(f"bridge stop_capture {ubridge_bridge}")
        log.debug(
            'Ethernet switch "{name}" [{id}]: stopping packet capture on port {port}'.format(
                name=self.name, id=self.id, port=port_number
            )
        )
