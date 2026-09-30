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
Docker's half of the kernel datapath: the veth pair lifecycle (deterministic
names, creation, teardown) plus the three hooks that tell the shared
KernelDatapathMixin which host interface plays the anchor role. Everything
datapath-agnostic — tc filters, the uBridge tc-capability probe, kernel
markers, attach/detach, adapter carrier — lives in
``gns3server.compute.kernel_datapath`` and is shared with QEMU.
"""

import contextlib

from gns3server.compute.kernel_datapath import KernelDatapathMixin
from gns3server.compute.ubridge.ubridge_error import UbridgeError, UbridgeNamespaceError

from .docker_error import DockerError

import logging

log = logging.getLogger(__name__)


class DockerKernelDatapathMixin(KernelDatapathMixin):
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

    # ------------------------------------------------------------------
    # Anchor hooks (see KernelDatapathMixin)
    # ------------------------------------------------------------------

    def _kernel_host_ifc(self, adapter_number, port_number=0):
        """
        The veth host end of an adapter port, or None for an adapter without
        one (unix-socket vendor containers).
        """

        return self._kernel_veths.get((adapter_number, port_number))

    def _kernel_anchors(self):
        """
        Every veth host end this container currently owns.
        """

        return set(self._kernel_veths.values())

    def _relay_carrier_bridge(self, adapter_number, port_number=0):
        """
        The uBridge relay bridge whose TAP carrier replicates the adapter
        state — only reachable for adapters without a veth host end.
        """

        return self._bridge_name(adapter_number, port_number)

    def _kernel_error(self, message):
        return DockerError(message)

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

        The per-link kernel bridges go too (``_remove_kernel_bridges``), since
        deleting a node or closing a project never runs the link-teardown
        path. Both link endpoints run this — the peer's port still enslaved
        makes the bridge delete fail with EBUSY (suppressed) and the last one
        wins, the same contract as _remove_kernel_nio. A node restart
        re-creates the bridge from the NIO in the attach path, so nothing is
        lost by deleting it.
        """

        if self.ubridge:
            for host_ifc in self._kernel_veths.values():
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'docker delete_veth "{host_ifc}"')
            await self._remove_kernel_bridges()
        self._kernel_veths.clear()
