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
Standalone ``tc capabilities`` probe.

Spawns the configured uBridge outside any node lifecycle, asks its tc module
for the feature report and caches the answer by binary identity (path,
mtime, size) — the same binary never answers differently, but replacing it
must re-probe. This feeds the compute ``/capabilities`` payload so the
controller and clients can gate kernel-datapath filter types on what this
host's uBridge can actually run, as the server's own user — which is the
point: the runtime ``ebpf`` flag flips between users and kernels for the
same binary, so a probe run as root would lie for a non-root server.

A node's own probe (DockerVM._ubridge_tc_capabilities) stays per-process;
this one only answers "what can this binary do here". Never raises: any
failure (missing binary, old build answering "Unknown command", timeout)
means unknown, reported as None and cached as such.
"""

import os
import uuid
import shutil
import asyncio
import tempfile
import logging
import contextlib

from gns3server.config import Config
from gns3server.utils.tc_capabilities import parse_tc_capabilities
from .hypervisor import Hypervisor
from .ubridge_error import UbridgeError

log = logging.getLogger(__name__)

# binary identity -> parsed report (None = probed and unusable)
_cache = {}
# binary identity -> whether the tap module works (None = unknown)
_tap_cache = {}
# binary identity -> whether iol_bridge can bind a port to a TAP (None = unknown)
_iol_tap_cache = {}
_lock = asyncio.Lock()


async def probe_tc_capabilities(timeout: float = 15.0):
    """
    Probe the configured uBridge's tc module once per binary identity.

    :param timeout: overall timeout for spawn + ask, in seconds
    :returns: parsed ``tc capabilities`` dict, or None when unknown
    """

    config = Config.instance()
    path = shutil.which(config.settings.Server.ubridge_path)
    if not path:
        return None
    try:
        stat = os.stat(path)
        key = (path, stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None

    async with _lock:
        if key in _cache:
            return _cache[key]
        caps = await _probe(path, config, timeout)
        _cache[key] = caps
        return caps


async def _probe(path, config, timeout):
    """
    Spawn a throwaway uBridge, ask ``tc capabilities``, tear it down.
    """

    working_dir = tempfile.mkdtemp(prefix="gns3-tc-probe-")
    hypervisor = Hypervisor(
        None,
        path,
        working_dir,
        config.settings.Server.ubridge_control_transport,
        config.settings.Server.host,
        str(uuid.uuid4()),
    )
    try:

        async def ask():
            await hypervisor.start()
            await hypervisor.connect()
            reply = await hypervisor.send("tc capabilities")
            return parse_tc_capabilities(reply[0] if reply else "")

        try:
            caps = await asyncio.wait_for(ask(), timeout=timeout)
        except (UbridgeError, OSError, asyncio.TimeoutError, ValueError) as e:
            # Old uBridge builds answer "Unknown command"/"Unknown module";
            # anything else here is a broken install — either way: unknown.
            log.debug("uBridge tc capabilities probe failed: %s", e)
            return None
        return caps if caps else None
    finally:
        with contextlib.suppress(Exception):
            await hypervisor.stop()
        shutil.rmtree(working_dir, ignore_errors=True)


async def probe_tap_support(timeout: float = 15.0):
    """
    Whether this host's uBridge can create persistent TAPs (the ``tap``
    module), probed the same way as the tc report — a throwaway uBridge, the
    answer cached by binary identity. QEMU adapters anchor on such a TAP, so
    this is what makes a QEMU node kernel-datapath eligible; an old build
    answers "Unknown command", reported as None (unknown) and cached as such.
    """

    config = Config.instance()
    path = shutil.which(config.settings.Server.ubridge_path)
    if not path:
        return None
    try:
        stat = os.stat(path)
        key = (path, stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None

    async with _lock:
        if key in _tap_cache:
            return _tap_cache[key]
        supported = await _probe_tap(path, config, timeout)
        _tap_cache[key] = supported
        return supported


async def _probe_tap(path, config, timeout):
    """
    Spawn a throwaway uBridge and try to create (then delete) one persistent
    TAP. The probe device is named after a uuid so a concurrent probe on the
    same host cannot collide; a delete that fails leaves it behind, which is
    worth a warning but not a failure of the probe.
    """

    working_dir = tempfile.mkdtemp(prefix="gns3-tap-probe-")
    hypervisor = Hypervisor(
        None,
        path,
        working_dir,
        config.settings.Server.ubridge_control_transport,
        config.settings.Server.host,
        str(uuid.uuid4()),
    )
    name = f"gns3tap{uuid.uuid4().hex[:6]}"
    try:

        async def ask():
            await hypervisor.start()
            await hypervisor.connect()
            await hypervisor.send(f"tap create {name}")
            try:
                await hypervisor.send(f"tap delete {name}")
            except UbridgeError as e:
                log.warning("Probe TAP %s could not be deleted: %s", name, e)
            return True

        try:
            return await asyncio.wait_for(ask(), timeout=timeout)
        except (UbridgeError, OSError, asyncio.TimeoutError, ValueError) as e:
            # Missing module, old build, or no CAP_NET_ADMIN: unknown.
            log.debug("uBridge tap-module probe failed: %s", e)
            return None
    finally:
        with contextlib.suppress(Exception):
            await hypervisor.stop()
        shutil.rmtree(working_dir, ignore_errors=True)


# Above the per-node IOL bridge ids: a real node's application id is 1..512,
# so its bridge locks /tmp/netio<uid>/513..1024. 1050 cannot collide with a
# node — only with another probe process, whose failure then answers "unknown"
# (the safe answer: IOU stays on the relay datapath).
_IOL_PROBE_BRIDGE_ID = 1050


async def probe_iol_tap_support(timeout: float = 15.0):
    """
    Whether this host's uBridge can terminate an IOL port on a persistent
    TAP (``iol_bridge add_nio_tap``) — the anchor IOU's Ethernet ports need
    for the kernel datapath. Probed on a scratch IOL bridge with a scratch
    TAP (both cleaned up), cached by binary identity like the tap probe;
    any failure (missing binary, old build answering "Unknown command",
    lock contention with another server process) means unknown, reported as
    None and cached as such.
    """

    config = Config.instance()
    path = shutil.which(config.settings.Server.ubridge_path)
    if not path:
        return None
    try:
        stat = os.stat(path)
        key = (path, stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None

    async with _lock:
        if key in _iol_tap_cache:
            return _iol_tap_cache[key]
        supported = await _probe_iol_tap(path, config, timeout)
        _iol_tap_cache[key] = supported
        return supported


async def _probe_iol_tap(path, config, timeout):
    """
    Spawn a throwaway uBridge and run one add_nio_tap/delete_nio_tap cycle on
    a scratch bridge and scratch TAP — attaching works on a stopped bridge,
    so no iol_bridge start is needed. The scratch resources are cleaned up
    best-effort even when the probe itself fails.
    """

    working_dir = tempfile.mkdtemp(prefix="gns3-iol-probe-")
    hypervisor = Hypervisor(
        None,
        path,
        working_dir,
        config.settings.Server.ubridge_control_transport,
        config.settings.Server.host,
        str(uuid.uuid4()),
    )
    bridge = f"gns3iolprobe{uuid.uuid4().hex[:4]}"
    tap = f"gns3ita{uuid.uuid4().hex[:6]}"
    try:

        async def ask():
            await hypervisor.start()
            await hypervisor.connect()
            await hypervisor.send(f"iol_bridge create {bridge} {_IOL_PROBE_BRIDGE_ID}")
            try:
                await hypervisor.send(f"tap create {tap}")
                await hypervisor.send(
                    f"iol_bridge add_nio_tap {bridge} {_IOL_PROBE_BRIDGE_ID - 1} 0 0 {tap}"
                )
                await hypervisor.send(f"iol_bridge delete_nio_tap {bridge} 0 0")
            finally:
                # iol_bridge delete releases every port NIO (the TAP fd),
                # so the subsequent tap delete cannot hit EBADFD.
                with contextlib.suppress(UbridgeError):
                    await hypervisor.send(f"iol_bridge delete {bridge}")
                with contextlib.suppress(UbridgeError):
                    await hypervisor.send(f"tap delete {tap}")
            return True

        try:
            return await asyncio.wait_for(ask(), timeout=timeout)
        except (UbridgeError, OSError, asyncio.TimeoutError, ValueError) as e:
            # Old build ("Unknown command"), missing module, or no
            # CAP_NET_ADMIN: unknown.
            log.debug("uBridge iol-tap probe failed: %s", e)
            return None
    finally:
        with contextlib.suppress(Exception):
            await hypervisor.stop()
        shutil.rmtree(working_dir, ignore_errors=True)
