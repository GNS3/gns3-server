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

from ...base_node import BaseNode
from ...nios.nio_udp import NIOUDP
from ...error import NodeError
from gns3server.compute.ubridge.ubridge_error import UbridgeError

import logging

log = logging.getLogger(__name__)

# VLAN ethertypes the Linux kernel bridge can realise. ``brctl setvlanproto``
# accepts only 0x8100 (802.1Q) and 0x88a8 (802.1ad). The GNS3 schema also allows
# the legacy 0x9100/0x9200 QinQ ethertypes; the kernel bridge cannot do those, so
# configuring them on a qinq port is rejected.
_SUPPORTED_VLAN_ETHERTYPE = {"0x8100", "0x88a8"}
_QINQ_ETHERTYPE = "0x88a8"


class EthernetSwitch(BaseNode):

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
        self._tap_by_port = {}          # port_number -> kernel TAP enslaved to the bridge
        self._bridge_name = None        # kernel bridge interface name (allocated on start)
        self._bridge_created = False
        self._bridge_proto_set = False  # whether ``brctl setvlanproto`` has been applied
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
            await self._ensure_bridge()
            for port_number in self._nios:
                if self._nios[port_number]:
                    try:
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
        self._tap_by_port.clear()

        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running() and self._bridge_created:
            try:
                # Deleting the bridge releases its enslaved TAPs; uBridge destroys
                # them when it stops below.
                await self._ubridge_send(f'brctl delete "{self._bridge_name}"')
            except UbridgeError as e:
                log.warning(f'Could not delete kernel bridge "{self._bridge_name}": {e}')
            self._bridge_created = False
            self._bridge_proto_set = False
            self._bridge_name = None
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

        :param nio: NIO instance to add
        :param port_number: port to allocate for the NIO
        """

        if port_number in self._nios:
            raise NodeError(f"Port {port_number} isn't free")
        if not isinstance(nio, NIOUDP):
            raise NodeError("Ethernet switch ports only support UDP NIOs")

        log.debug(
            'Ethernet switch "{name}" [{id}]: NIO {nio} bound to port {port}'.format(
                name=self._name, id=self._id, nio=nio, port=port_number
            )
        )
        try:
            await self.start()
            await self._add_ubridge_connection(nio, port_number)
            self._nios[port_number] = nio
        except (NodeError, UbridgeError) as e:
            log.error('Cannot add NIO on Ethernet switch "{name}": {error}'.format(name=self._name, error=e))
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
        await self._ubridge_send(
            "bridge add_nio_udp {name} {lport} {rhost} {rport}".format(
                name=ubridge_bridge, lport=nio.lport, rhost=nio.rhost, rport=nio.rport
            )
        )
        await self._ubridge_apply_filters(ubridge_bridge, nio.filters)
        await self._ubridge_apply_markers(ubridge_bridge, nio)
        if nio.capturing:
            await self._ubridge_send(
                'bridge start_capture {name} "{output_file}"'.format(
                    name=ubridge_bridge, output_file=nio.pcap_output_file
                )
            )
        await self._ubridge_send(f"bridge start {ubridge_bridge}")
        self._tap_by_port[port_number] = tap

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

        log.debug(
            'Ethernet switch "{name}" [{id}]: NIO {nio} removed from port {port}'.format(
                name=self._name, id=self._id, nio=nio, port=port_number
            )
        )
        del self._nios[port_number]
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
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
        Re-applies uBridge filters/markers for a port (called when a link is updated).
        """

        ubridge_bridge = self._ubridge_bridge_name(port_number)
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
            await self._ubridge_apply_filters(ubridge_bridge, nio.filters)
            await self._ubridge_apply_markers(ubridge_bridge, nio)

    # ------------------------------------------------------------------ #
    # VLAN mode translation
    # ------------------------------------------------------------------ #

    async def _reset_port_vlan(self, tap):
        """
        Resets a port's VLAN membership to the kernel default (PVID 1, untagged)
        by re-enslaving it. Used before re-applying a changed mode so stale VIDs
        from the previous mode do not leak.
        """

        await self._ubridge_send(f'brctl delif "{self._bridge_name}" "{tap}"')
        await self._ubridge_send(f'brctl addif "{self._bridge_name}" "{tap}"')

    async def _apply_port_vlan(self, port_settings, tap):
        """
        Translates an ESW port mode into ``brctl`` VLAN primitives. The port must
        already be enslaved to the bridge and carry the default PVID 1.

        - access VLAN N: drop default 1, add N as PVID + egress untagged.
        - dot1q trunk (native N): drop default 1, admit all VIDs tagged, then mark
          the native VLAN PVID + untagged. (The ESW model declares only the native
          VLAN per trunk port, so the trunk admits all VIDs, like the emulated ESW.)
        - qinq (outer N): the bridge-level protocol is set separately; the port
          gets the service VLAN as PVID + untagged so customer frames are S-tagged.
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

    async def update_port_settings(self):
        """
        Re-applies port settings (called after ``ports_mapping`` is updated). For
        ports already wired, reset then re-apply so a mode/VLAN change fully
        replaces the previous VLAN membership.
        """

        await self._apply_bridge_proto_if_needed()
        if not (self._ubridge_hypervisor and self._ubridge_hypervisor.is_running() and self._bridge_created):
            return
        for port_settings in self._ports_mapping:
            port_number = port_settings["port_number"]
            tap = self._tap_by_port.get(port_number)
            if tap is None:
                continue
            await self._reset_port_vlan(tap)
            await self._apply_port_vlan(port_settings, tap)

    # ------------------------------------------------------------------ #
    # capture
    # ------------------------------------------------------------------ #

    async def start_capture(self, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture on a port (uBridge captures on the per-port relay).

        :param port_number: allocated port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        nio = self.get_nio(port_number)
        if nio.capturing:
            raise NodeError(f"Packet capture is already activated on port {port_number}")
        nio.start_packet_capture(output_file)
        if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
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
            ubridge_bridge = self._ubridge_bridge_name(port_number)
            await self._ubridge_send(f"bridge stop_capture {ubridge_bridge}")
        log.debug(
            'Ethernet switch "{name}" [{id}]: stopping packet capture on port {port}'.format(
                name=self.name, id=self.id, port=port_number
            )
        )
