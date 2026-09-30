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
