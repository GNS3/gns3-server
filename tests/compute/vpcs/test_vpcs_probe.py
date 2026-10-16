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

import os
import stat

import pytest

from gns3server.compute.vpcs.vpcs_probe import probe_vpcs_tap

pytestmark = pytest.mark.asyncio


def _fake_vpcs(path, usage):
    path.write_text(f"#!/bin/sh\ncat <<'EOF'\n{usage}\nEOF\n")
    mode = path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    os.chmod(path, mode)


async def test_probe_reports_dash_n_build(config, tmp_path):

    binary = tmp_path / "vpcs"
    _fake_vpcs(
        binary,
        "  -d device      device name, works only when -i is set to 1\n"
        "  -n             do not auto-configure the host tap interface\n",
    )
    config.settings.VPCS.vpcs_path = str(binary)
    assert await probe_vpcs_tap() is True


async def test_probe_reports_upstream_build(config, tmp_path):

    binary = tmp_path / "vpcs"
    _fake_vpcs(
        binary,
        "  -d device      device name, works only when -i is set to 1\n",
    )
    config.settings.VPCS.vpcs_path = str(binary)
    assert await probe_vpcs_tap() is False


async def test_probe_reports_missing_binary(config, tmp_path):

    config.settings.VPCS.vpcs_path = str(tmp_path / "does-not-exist")
    assert await probe_vpcs_tap() is None


async def test_probe_caches_by_binary_identity(config, tmp_path):
    """
    The same binary answers once; replacing it (a different mtime/size)
    re-probes.
    """

    binary = tmp_path / "vpcs"
    _fake_vpcs(binary, "  -n             do not auto-configure\n")
    config.settings.VPCS.vpcs_path = str(binary)
    assert await probe_vpcs_tap() is True

    # replace with a build without the flag: the binary identity changed,
    # so the cached True must not answer
    _fake_vpcs(binary, "  -d device      device name\n")
    os.utime(binary, (0, 0))
    assert await probe_vpcs_tap() is False
