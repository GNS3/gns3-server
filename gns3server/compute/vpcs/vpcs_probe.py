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
#

"""
Standalone VPCS tap-mode probe.

A VPCS node anchors a kernel-datapath link on a persistent TAP the vpcs
process attaches to by name (``-e -d <anchor>``). That shape needs a vpcs
build that also refuses to auto-configure the host side of the TAP (``-n``):
without the flag every ``ip`` command inside the guest runs
``ifconfig <tap> … up`` on the anchor — the server owns the anchor's
addresses and bridge membership, so a vpcs touching them ranges from noise
(an ifconfig on a name that cannot resolve) to sabotage (reconfiguring an
interface that does exist).

The probe asks the configured binary for its usage (``vpcs -h``) and looks
for the ``-n`` line, caching the answer by binary identity (path, mtime,
size, ctime) exactly like the uBridge probes — the same binary never
answers differently, but replacing it must re-probe. This feeds the compute
``/capabilities`` payload (``vpcs_tap``) so the controller can gate VPCS
kernel links on it. Never raises: any failure (missing binary, timeout)
means unknown, reported as None and cached as such — the safe answer keeps
the node on the relay datapath.
"""

import asyncio
import logging
import os
import shutil

from gns3server.config import Config
from gns3server.utils.asyncio import subprocess_check_output

log = logging.getLogger(__name__)

# binary identity (path, mtime, size, ctime) -> whether -n is available
# (None = probed and unknown)
_cache: dict[tuple[str, int, int, int], bool | None] = {}
_lock = asyncio.Lock()

# The stable tail of the -n usage line (the flag itself is wrapped in ANSI
# escapes, the description is not).
_NO_HOSTCONF_NEEDLE = "do not auto-configure"


async def probe_vpcs_tap(timeout: float = 5.0) -> bool | None:
    """
    Whether this host's VPCS binary can anchor a kernel link (tap mode with
    ``-n``), probed once per binary identity.

    :returns: True when the usage advertises ``-n``, False when it does not
        (an upstream build), None when the probe failed (unknown binary).
    """

    config = Config.instance()
    vpcs_path = config.settings.VPCS.vpcs_path
    if not os.path.isabs(vpcs_path):
        vpcs_path = shutil.which(vpcs_path)
    if not vpcs_path or not os.path.isfile(vpcs_path):
        return None
    try:
        stat = os.stat(vpcs_path)
        key = (vpcs_path, stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns)
    except OSError:
        return None

    async with _lock:
        if key in _cache:
            return _cache[key]
        try:
            output = await asyncio.wait_for(subprocess_check_output(vpcs_path, "-h"), timeout=timeout)
        except (OSError, asyncio.TimeoutError, ValueError) as e:
            log.debug("VPCS tap-mode probe failed: %s", e)
            supported = None
        else:
            supported = _NO_HOSTCONF_NEEDLE in output
        _cache[key] = supported
        return supported
