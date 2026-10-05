#
# Copyright (C) 2025 GNS3 Technologies Inc.
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
IOL (IOS on Linux) Docker container subclass.

Supports IOL images packaged with Cisco CML's container runner
(``iol-runner``, ``virl.lab/cmd/iol-runner``), e.g. ``iol-xe/iol-xe:17-18-02``:
a scratch image whose ENTRYPOINT is ``iol-runner -config /config/iol-config.json
-stdio``. The runner generates the license, writes the NETMAP, manages NVRAM
and muxes the IOS console onto PID 1 stdio (works with the plain ``telnet``
console type; requires a TTY, which GNS3 always allocates).

Networking does not use the container's network namespace at all: the runner's
netiomux exposes per-interface AF_UNIX datagram sockets in the container's
``/tmp`` (``s%02d.sock`` receive, ``c%02d.sock`` send — raw Ethernet frames),
wired by the generic ``GNS3_UNIX_SOCKET_NIO`` capability of VendorDockerVM
(uBridge reaches them through a per-node runtime directory bound at /tmp —
see ``VendorDockerVM._unix_socket_host_dir``). The controller allocates the
IOL application ID (upper half of the id space, disjoint from IOU's) so that
linked nodes get distinct MACs; starting a node without an allocation is an
error, not a fallback — an uncoordinated id could collide with the pool and
blackhole traffic as a MAC loop.

Kernel datapath: the unix-socket pair is this container's only physical
layer, so one userspace hop on its leg is irreducible — but the *link
segment* need not ride the relay. Every Ethernet bay/unit owns a persistent
TAP anchor (``gx`` names, created at node start like IOU's), and the
per-port uBridge bridge swaps its topology leg between UDP (relay) and the
anchor (kernel link) through ``bridge add_nio_tap`` / ``bridge
delete_nio_tap`` — stop → delete → add → start, the c-socket binding
surviving the swap. Eligibility needs the compute's uBridge to report both
``ubridge_tap`` (the tap module) and ``ubridge_bridge_tap`` (the swappable
leg); anything less keeps the node relay-only, exactly as before.

This class is selected by the ``GNS3_IOL_RUNNER=1`` environment marker.
"""

import contextlib
import glob
import json
import logging
import os
import re
import shutil

from gns3server.compute.adapters.ethernet_adapter import EthernetAdapter
from gns3server.compute.docker.docker_error import DockerError, DockerHttp404Error
from gns3server.compute.docker.vendor_docker_vm import VendorDockerVM
from gns3server.compute.iou.utils.iou_export import nvram_export
from gns3server.compute.iou.utils.iou_import import nvram_import
from gns3server.compute.kernel_datapath import KernelDatapathMixin
from gns3server.compute.nios.nio_bridge import NIOBridge
from gns3server.compute.ubridge.tc_probe import probe_bridge_tap_support, probe_tap_support
from gns3server.compute.ubridge.ubridge_error import UbridgeError
from gns3server.utils.kernel_anchor import kernel_anchor_name

log = logging.getLogger(__name__)


class IOLDockerVM(VendorDockerVM):
    """
    VendorDockerVM subclass for iol-runner images.

    Extra opt-in knob (beyond the inherited vendor ones):

    * ``GNS3_IOL_MEMORY=<MB>`` — IOL router memory passed via the generated
      config (default 2048). The template ``memory`` field caps the whole
      container: keep it at IOL memory + ~512 MB headroom or the kernel
      OOM-killer will fire.

    The marker itself forces ``GNS3_SKIP_INIT`` and the unix-socket NIO wiring,
    and auto-adds the ``/config`` and ``/tmp/run`` persistent volumes, so a
    template containing only ``GNS3_IOL_RUNNER=1`` is fully configured.

    Startup configuration follows the IOU model: a template may reference a
    config file with the ``GNS3_IOL_STARTUP_CONFIG`` environment knob; the
    controller materializes the file content into ``startup_config_content``
    when the node is created. The content is built into the node's NVRAM
    (``tmp/run/nvram_<app id>``) on the next start — IOL boots straight from
    NVRAM, so a plain stop/start never re-applies it and ``write memory``
    survives restarts.
    """

    _IOL_CONFIG_DIR = "/config"
    _IOL_RUN_DIR = "/tmp/run"
    # The runner launches IOL with a fixed 256KB nvram (-n 256)
    _IOL_NVRAM_SIZE_KB = 256

    # Payload-delivered state. Deliberately NOT initialized in
    # _parse_vendor_environment(): create() re-runs that parser on every
    # (re)create (a stop removes the container, so every start recreates it)
    # to pick up environment changes — resetting these there would lose the
    # controller-allocated application id (MACs would flip to the fallback
    # hash, colliding with the allocation pool) and any pending
    # startup-config delivered by a PUT.
    _application_id: int | None = None
    _startup_config_content: str | None = None
    _startup_config_dirty = False

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        # Kernel datapath (see KernelDatapathMixin): one persistent TAP per
        # Ethernet bay/unit, held by uBridge's port bridge while a kernel
        # link binds the port (bridge add_nio_tap).
        self._kernel_taps = {}
        self._tap_datapath = False

    def _parse_vendor_environment(self):

        super()._parse_vendor_environment()
        # The image has no shell (scratch): init.sh could neither run (its
        # #!/bin/sh shebang doesn't exist) nor wait for eth interfaces that
        # are never created. The console is IOS itself on PID 1 stdio.
        self._gns3_init = False
        self._unix_socket_nio = True
        self._unix_socket_dir = "/tmp"

        self._iol_memory = 2048
        if self._environment:
            for _line in self._environment.splitlines():
                _line = _line.strip().rstrip(",")
                if _line.startswith("GNS3_IOL_MEMORY="):
                    try:
                        memory = int(_line.split("=", 1)[1].strip())
                        if memory > 0:
                            self._iol_memory = memory
                    except ValueError:
                        pass

    @property
    def application_id(self) -> int | None:
        """
        IOL application ID: drives interface MACs (aabb.cc{app}{iface}) and
        the NVRAM file name. Allocated by the controller from the IOL Docker
        half of the id space (disjoint from IOU's) — there is deliberately
        no fallback: an id derived any other way could silently collide with
        an allocation and blackhole traffic as a MAC loop. Starting a node
        without one raises (see _prepare_iol_runtime).
        """

        return self._application_id

    @application_id.setter
    def application_id(self, value) -> None:
        self._application_id = int(value)

    @property
    def startup_config_content(self):
        """
        Startup-config content, delivered by the controller when the node is
        created from a template carrying GNS3_IOL_STARTUP_CONFIG (or updated
        with new content).
        """

        return self._startup_config_content

    @startup_config_content.setter
    def startup_config_content(self, content):
        """
        Record new startup-config content; it is built into the node's NVRAM
        on the next start. IOL boots from NVRAM whenever it holds a config, so
        the content is only pushed when it actually changes — a plain
        stop/start never re-applies it and `write memory` survives restarts.
        """

        if not content or content == self._startup_config_content:
            # An empty value is ignored: erasing the config is not supported
            # (mirrors the IOU setter) and Web clients PUT "" for unset fields.
            return
        self._startup_config_content = content
        self._startup_config_dirty = True

    def _iol_nvram_file(self) -> str:
        """
        The IOL NVRAM file inside the persistent /tmp/run volume. The name
        embeds the application id (nvram_00772-style, like CML).
        """

        return os.path.join(self.working_dir, "tmp", "run", f"nvram_{self.application_id:05d}")

    def _apply_pending_startup_config(self) -> None:
        """
        Build the node's NVRAM from the recorded startup-config content. IOL
        and IOU share the same NVRAM container format (startup-config stored
        as text inside the nvram file system), so the IOU nvram_import
        utility produces a file IOL boots from directly — valid config, no
        initial configuration dialog.
        """

        if self._startup_config_content is None:
            return
        content = self._startup_config_content.replace("%h", self._name)
        nvram_file = self._iol_nvram_file()
        os.makedirs(os.path.dirname(nvram_file), exist_ok=True)
        try:
            nvram = nvram_import(None, content.encode("utf-8"), None, self._IOL_NVRAM_SIZE_KB)
            with open(nvram_file, "wb") as f:
                f.write(nvram)
        except (OSError, ValueError) as e:
            raise DockerError(f"Could not write IOL startup-config to NVRAM of container '{self._name}': {e}")
        log.debug("IOL container '%s': startup-config written to %s", self._name, nvram_file)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name):
        """
        Override: keep the hostname line inside the NVRAM in sync with the
        node name (IOU parity), so a renamed or duplicated node boots under
        its new name. Skipped while a content change is pending — the next
        start pushes the new content with the already-updated name.
        """

        if not self._startup_config_dirty and self._application_id is not None:
            nvram_file = self._iol_nvram_file()
            if os.path.exists(nvram_file):
                try:
                    with open(nvram_file, "rb") as f:
                        startup_config, _ = nvram_export(f.read())
                    if startup_config:
                        content = re.sub(
                            r"hostname .+$",
                            "hostname " + new_name,
                            startup_config.decode("utf-8", errors="replace"),
                            flags=re.MULTILINE,
                        )
                        nvram = nvram_import(None, content.encode("utf-8"), None, self._IOL_NVRAM_SIZE_KB)
                        with open(nvram_file, "wb") as f:
                            f.write(nvram)
                except (OSError, ValueError) as e:
                    log.warning(f"Could not update hostname in NVRAM of IOL container '{self._name}': {e}")
        super(IOLDockerVM, IOLDockerVM).name.__set__(self, new_name)

    def asdict(self):
        """
        Override: expose the recorded startup-config content (empty for nodes
        created before the knob existed or reloaded from a topology).
        """

        result = super().asdict()
        result["startup_config_content"] = self._startup_config_content
        return result

    @property
    def adapters(self):
        return len(self._ethernet_adapters)

    @adapters.setter
    def adapters(self, adapters):
        """
        Override: one IOL adapter is a 4-port unit — the IOU model. The
        template's adapter count is the number of units (2 adapters =
        Ethernet0/0-3 + Ethernet1/0-3); the generated config asks the runner
        for adapters × 4 interfaces and links address ports as
        (adapter_number, port_number 0-3).
        """

        if len(self._ethernet_adapters) == adapters:
            return

        self._ethernet_adapters.clear()
        for _ in range(0, adapters):
            self._ethernet_adapters.append(EthernetAdapter(interfaces=4))

        log.debug(
            "IOL container '%s': number of 4-port Ethernet adapters set to %d",
            self._name,
            adapters,
        )

    def _persistent_volume_list(self, image_info, include_network_config=True):
        """
        Override: the runner requires ``/config`` (its config file, generated
        below) and ``/tmp/run`` (its working directory: startup-config and
        NVRAM live there — NETMAP and the netiomux sockets are ephemeral and
        stay in the container's own /tmp). Auto-add both so a minimal
        template cannot be misconfigured.
        """

        volumes = super()._persistent_volume_list(image_info, include_network_config)
        for needed in (self._IOL_CONFIG_DIR, self._IOL_RUN_DIR):
            if not any(needed == v or needed.startswith(v.rstrip("/") + "/") for v in volumes):
                volumes.append(needed)
        return volumes

    async def start(self):

        await self._prepare_iol_runtime()
        await super().start()

    async def restart(self):
        """
        Override: the base restart is a bare ``docker restart`` — the runner
        would read a stale config (no adapter-count/memory refresh) and
        uBridge would keep wiring to the previous run's sockets. Stop
        gracefully (SIGTERM lets the runner flush NVRAM) and start again.
        """

        await self.stop(graceful=True)
        await self.start()

    async def _prepare_iol_runtime(self):
        """
        Regenerate the node's runtime files before the container starts:

        * ``<working_dir>/tmp/run/`` must exist or the IOL process dies at
          boot (the runner writes NETMAP there but does not create it).
        * ``<working_dir>/config/iol-config.json`` is rewritten on every
          start so adapter-count and memory changes take effect.
        * Sockets and netio bus directories left in the wiring directory by a
          previous (possibly SIGKILLed) run are removed — the runner rebinds
          them on boot and would fail on a stale file.

        ``tmp/run`` (startup-config, NVRAM) is never touched. Neither is
        anything while the container is already running (idempotent start of
        a live node: the sockets belong to the running runner).
        """

        try:
            state = await self._get_container_state()
        except DockerHttp404Error:
            state = "stopped"

        if self._application_id is None:
            raise DockerError(
                f"IOL container '{self._name}' has no application ID: nodes must be "
                "created through the controller (which allocates one from the pool "
                "shared with IOU), or created with an explicit application_id "
                "(512-1022) on the compute API. Without a coordinated ID two nodes "
                "would share MACs and drop each other's frames as loops."
            )

        os.makedirs(os.path.join(self.working_dir, "tmp", "run"), exist_ok=True)
        self._write_iol_config()

        if state == "running":
            return

        # Pending startup-config is materialized here rather than in the
        # property setter: at create-payload time the application id may not
        # be final yet (the create route applies fields in schema order) and
        # a running container must not have its NVRAM swapped mid-flight.
        if self._startup_config_dirty:
            self._apply_pending_startup_config()
            self._startup_config_dirty = False

        wiring_dir = self._unix_socket_wiring_dir()
        for pattern in ("s??.sock", "c??.sock"):
            for stale in glob.glob(os.path.join(wiring_dir, pattern)):
                with contextlib.suppress(OSError):
                    os.unlink(stale)
        for netio_dir in glob.glob(os.path.join(wiring_dir, "netio*")):
            shutil.rmtree(netio_dir, ignore_errors=True)

    def _write_iol_config(self):
        """
        Write the runner's config file on the host side of the /config volume.
        The runner drops to user-id/group-id after its setup, so everything it
        creates is owned by the server user — which is also what lets the
        (unprivileged) uBridge write into the node's socket directory.
        """

        config = {
            "binary": "/binary.iol",
            "memory": self._iol_memory,
            "num-eth": self.adapters * 4,  # every adapter is a 4-port unit
            "num-serial": 0,  # GNS3 docker adapters are ethernet-only
            # IOL derives interface MACs from the local application ID
            # (aabb.cc{app}{iface}); every node needs a distinct one or
            # linked routers share MACs and drop each other's frames as
            # loops. Allocated by the controller per node (upper half of
            # the id space, disjoint from IOU's — CML does the same with
            # its per-deployment iol_app_id).
            "local-app": self.application_id,
            "remote-app": 1023,  # netiomux's fake peer application ID
            "user-id": os.getuid(),
            "group-id": os.getgid(),
        }
        config_file = os.path.join(self.working_dir, "config", "iol-config.json")
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        log.debug("Wrote iol-runner config for '%s': %s", self._name, config)

    async def _fix_permissions(self):
        """
        Override: no-op. The generated config maps the runner to the server's
        uid/gid, so no root-owned files ever appear in the volumes, and this
        image has no shell for the container-side busybox pass anyway.
        """

        self._permissions_fixed = True

    # ------------------------------------------------------------------
    # Kernel datapath (see KernelDatapathMixin)
    # ------------------------------------------------------------------

    def _kernel_host_ifc(self, adapter_number, port_number=0):
        """
        The persistent TAP this Ethernet bay/unit owns (one 4-port unit per
        adapter, the IOU model), or None before the node started — or on a
        uBridge that cannot serve the anchor lifecycle, in which case the
        node runs relay-only.
        """

        return self._kernel_taps.get((adapter_number, port_number))

    def _kernel_anchors(self):
        """
        Every anchor TAP this node currently owns.
        """

        return set(self._kernel_taps.values())

    def _kernel_error(self, message):
        return DockerError(message)

    def _tap_name(self, adapter_number, port_number):
        """
        Deterministic anchor TAP name for an Ethernet bay/unit — the shared
        utils.kernel_anchor naming contract under the ``iol_docker`` key, so
        the controller names a peer's anchor with the same function when an
        Ethernet switch absorbs it.
        """

        return kernel_anchor_name("iol_docker", self._id, adapter_number, port_number)

    async def _start_ubridge(self, require_privileged_access=False):
        """
        Override: with the control channel up, give every Ethernet bay/unit
        its persistent TAP anchor — before the first link can attach (the
        start loop calls _add_ubridge_connection right after this). The
        anchors exist whether or not any link ever uses them: an anchor born
        with the link would leave the switch fast path's deferred join
        waiting forever (a link to a stopped node must not fail — and one to
        a just-started node must not silently miss its anchor either).
        """

        await super()._start_ubridge(require_privileged_access=require_privileged_access)
        await self._prepare_tap_datapath()

    async def _prepare_tap_datapath(self):
        """
        Probe uBridge for the commands the anchor lifecycle needs — the tap
        module (``tap create``/``tap delete``, the ``ubridge_tap``
        capability) and the bridge module's swappable TAP leg
        (``bridge delete_nio_tap``, ``ubridge_bridge_tap``) — and when both
        answer, create the persistent TAP every Ethernet bay/unit owns.
        A uBridge missing either keeps this node on the relay datapath:
        every link rides unix ↔ UDP through the port bridges, exactly as
        before the kernel datapath existed.
        """

        self._tap_datapath = False
        self._kernel_taps.clear()

        if await probe_bridge_tap_support() is not True:
            log.info(
                "IOL container '%s': this compute's uBridge cannot swap a bridge's TAP leg "
                "(bridge delete_nio_tap); the node runs on the relay datapath and cannot "
                "carry kernel links",
                self._name,
            )
            return
        if await probe_tap_support() is not True:
            log.info(
                "IOL container '%s': this compute's uBridge has no persistent-TAP module; "
                "the node runs on the relay datapath and cannot carry kernel links",
                self._name,
            )
            return

        self._tap_datapath = True
        for adapter_number in range(0, len(self._ethernet_adapters)):
            for port_number in range(0, self._ethernet_adapters[adapter_number].interfaces):
                tap = self._tap_name(adapter_number, port_number)
                # A persistent TAP outlives a crash: sweep any leftover of a
                # previous run before recreating it (a surviving device would
                # also keep its stale tc qdisc).
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'tap delete "{tap}"')
                await self._ubridge_send(f'tap create "{tap}"')
                # Carrier off until a link attaches (the anchor contract).
                await self._ubridge_send(f'link set "{tap}" down')
                self._kernel_taps[(adapter_number, port_number)] = tap
                log.debug(
                    "IOL container '%s': anchor TAP %s created for bay %d unit %d",
                    self._name,
                    tap,
                    adapter_number,
                    port_number,
                )

    async def _ensure_anchor(self, adapter_number, port_number):
        """
        The ensure half of the frozen ensure-then-add contract: ``bridge
        add_nio_tap`` deliberately opens a *transient* TAP when the name is
        absent (cloud's bridge-interface path depends on it), so a persistent
        anchor swept away between the node's start and the link's attach
        would silently become a device that dies with the fd. ``tap create``
        is strictly create-only (``IFF_TUN_EXCL`` — re-creating an existing
        persistent device answers EBUSY), so the existence check is local:
        uBridge runs on this host, and /sys/class/net names every device.
        The repair create starts DOWN like every anchor at birth, so the
        carrier pass in the attach flow is what brings it up.
        """

        tap = self._tap_name(adapter_number, port_number)
        if os.path.exists(os.path.join("/sys/class/net", tap)):
            return
        await self._ubridge_send(f'tap create "{tap}"')

    async def _add_ubridge_connection(self, nio, adapter_number, port_number=0):
        """
        Override: the vendor rejection of kernel-datapath NIOs does not
        apply here — IOL runner adapters own persistent TAP anchors, so a
        NIOBridge wires the port bridge's topology leg to the anchor instead
        of raising (_connect_nio routes it; the port bridge and its unix NIO
        are ensured inside).
        """

        if isinstance(nio, NIOBridge):
            await self._connect_nio(adapter_number, nio, port_number)
            return
        await super()._add_ubridge_connection(nio, adapter_number, port_number)

    async def _connect_nio(self, adapter_number, nio, port_number=0):
        """
        Override: route the NIO onto the port bridge's topology leg. A
        kernel link (NIOBridge) swaps that leg to the port's anchor TAP and
        runs the shared mixin flow on it; a relay NIO keeps the unix ↔ UDP
        shape of the base class (the port bridge and its unix NIO ensured
        first, so the base path only adds the UDP half).
        """

        if isinstance(nio, NIOBridge):
            await self._attach_kernel_link(adapter_number, port_number, nio)
            return

        await self._ensure_unix_port_bridge(adapter_number, port_number)
        await super()._connect_nio(adapter_number, nio, port_number)

    async def _attach_kernel_link(self, adapter_number, port_number, nio):
        """
        Wire a kernel link's NIO (NIOBridge) on this port: the port bridge's
        topology leg becomes the anchor TAP (``bridge add_nio_tap`` — uBridge
        opens and holds the fd, relaying the unix-socket guest leg onto the
        device), then the anchor is enslaved into the per-link kernel bridge
        — the shared mixin flow, with the TAP playing the role Docker's veth
        and QEMU's TAP play. The relay starts only once both NIOs are in
        (uBridge requires two), which is also what carries the guest frames
        onto the anchor.
        """

        anchor = self._kernel_host_ifc(adapter_number, port_number)
        if anchor is None:
            raise DockerError(
                f"Bay {adapter_number}/{port_number} of IOL container '{self._name}' has no TAP anchor to carry a kernel "
                "link (this compute's uBridge lacks the tap module or bridge delete_nio_tap, "
                "or the node was started before the kernel-datapath support); restart the "
                "node after upgrading uBridge"
            )
        await self._ensure_unix_port_bridge(adapter_number, port_number)
        await self._ensure_anchor(adapter_number, port_number)
        bridge_name = self._bridge_name(adapter_number, port_number)
        await self._ubridge_send(f'bridge add_nio_tap {bridge_name} "{anchor}"')
        # Per-link kernel bridge (brctl), capture, markers and impairment
        # filters on the anchor — everything keyed on the interface name.
        await self._kernel_attach(anchor, nio)
        # Two NIOs now: start the [unix ↔ tap] relay.
        await self._ubridge_send(f"bridge start {bridge_name}")
        # The carrier pass refines the anchor's admin state (a suspended NIO
        # sets it back down) — it is also what brings a born-down anchor up.
        await self._set_adapter_carrier(adapter_number, not nio.suspend, port_number)

    async def _release_port_tap(self, adapter_number, port_number):
        """
        The teardown half of the swap contract: stop the port bridge (its
        relay threads hold the NIO pointers for their whole life — freeing a
        NIO under them is a use-after-free, which is why delete_nio_tap
        refuses while running), then release the TAP NIO by name. The anchor
        device itself survives (the node owns it, not the link); the c-socket
        binding survives too (stop keeps every NIO), so the container's
        egress frames queue on the socket until a leg is swapped in again.
        """

        bridge_name = self._bridge_name(adapter_number, port_number)
        with contextlib.suppress(UbridgeError):
            await self._ubridge_send(f"bridge stop {bridge_name}")
        tap = self._kernel_taps.get((adapter_number, port_number))
        if tap is not None:
            with contextlib.suppress(UbridgeError):
                await self._ubridge_send(f'bridge delete_nio_tap {bridge_name} "{tap}"')

    async def adapter_remove_nio_binding(self, adapter_number, port_number=0):
        """
        Override: a kernel link leaves through the port-leg swap (stop +
        delete_nio_tap) before the shared anchor-side teardown — markers,
        tc reset, brctl delif and the per-link bridge deletion — runs in the
        base path.
        """

        if self.ubridge:
            try:
                adapter = self._ethernet_adapters[adapter_number]
            except IndexError:
                adapter = None
            if adapter is not None and isinstance(adapter.get_nio(port_number), NIOBridge):
                await self._release_port_tap(adapter_number, port_number)
        await super().adapter_remove_nio_binding(adapter_number, port_number)

    async def _stop_ubridge(self):
        """
        Override: release the kernel datapath's host state while the control
        channel is still up, in the order the fd holders dictate — the port
        bridges hold the anchor TAP fds (``bridge add_nio_tap``), so they go
        first (``bridge delete`` stops their relay threads and frees the
        NIOs), then the anchors themselves (``tap delete`` answers EBADFD on
        a device another fd still holds), then the per-link kernel bridges.
        The port bridges die with the process anyway, but the anchors are
        persistent: deleting them here is what keeps a stopped node from
        littering the host with ``gx`` devices. The next start sweeps and
        re-creates everything.
        """

        if self.ubridge:
            # stop() clears _bridges before this point, so derive the port
            # bridge names from the adapters (the historical naming is a
            # pure function of adapter/port).
            for adapter_number in range(0, len(self._ethernet_adapters)):
                adapter = self._ethernet_adapters[adapter_number]
                for port_number in range(0, adapter.interfaces):
                    with contextlib.suppress(UbridgeError):
                        await self._ubridge_send(f"bridge delete {self._bridge_name(adapter_number, port_number)}")
            for tap in self._kernel_taps.values():
                with contextlib.suppress(UbridgeError):
                    await self._ubridge_send(f'tap delete "{tap}"')
            await self._remove_kernel_bridges()
        self._kernel_taps.clear()
        self._tap_datapath = False
        self._ubridge_tc_caps = None
        await super()._stop_ubridge()

    async def _set_adapter_carrier(self, adapter_number, connected, port_number=0):
        """
        Override: refine the vendor no-op. A port with an anchor (the kernel
        datapath) toggles the anchor's admin state — the port bridge's TAP
        NIO writes answer EIO and its reads fall silent while it is down,
        which is the suspend semantics of every other anchored node type. A
        port without an anchor (relay datapath on a uBridge without the
        swappable leg) keeps the no-op: the unix-socket pair has no carrier,
        and the port bridge carries no TAP NIO for the base class to toggle.
        """

        if self._kernel_host_ifc(adapter_number, port_number) is not None:
            await KernelDatapathMixin._set_adapter_carrier(self, adapter_number, connected, port_number)
