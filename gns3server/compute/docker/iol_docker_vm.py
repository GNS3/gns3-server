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
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.docker.vendor_docker_vm import VendorDockerVM
from gns3server.compute.iou.utils.iou_export import nvram_export
from gns3server.compute.iou.utils.iou_import import nvram_import

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
