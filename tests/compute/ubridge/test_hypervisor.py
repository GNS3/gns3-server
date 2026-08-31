#!/usr/bin/env python
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
Tests for the uBridge ``Hypervisor`` wrapper — the configurable control-channel
transport (AF_UNIX ``-U`` vs TCP ``-H``), command building, the human-readable
``endpoint``, socket cleanup on stop, and the fail-fast detection of an
immediately-exiting uBridge process (e.g. an old build that rejects ``-U``).
"""

import os
import re
import stat
import logging

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from gns3server.compute.ubridge.hypervisor import Hypervisor
from gns3server.compute.ubridge.ubridge_error import UbridgeError


def _make(transport, tmp_path, monkeypatch, node_id="abc123", host="127.0.0.1"):
    """Build a Hypervisor with ``XDG_RUNTIME_DIR`` pinned to ``tmp_path``.

    The unix transport creates its socket dir under ``$XDG_RUNTIME_DIR/gns3``;
    pinning it keeps creation predictable and avoids touching the real runtime
    dir. ``host`` is unused for the unix transport but always accepted.
    """

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    return Hypervisor(MagicMock(), "ubridge", str(tmp_path), transport, host=host, node_id=node_id)


# ---------------------------------------------------------------------------
# __init__: transport selection
# ---------------------------------------------------------------------------

def test_init_unix_creates_socket_dir_and_path(tmp_path, monkeypatch):

    hyp = _make("unix", tmp_path, monkeypatch, node_id="abc123")
    assert hyp._socket_path == str(tmp_path / "gns3" / "ubridge-abc123.sock")

    socket_dir = os.path.dirname(hyp._socket_path)
    assert os.path.isdir(socket_dir)
    # 0o700 regardless of umask — __init__ chmods explicitly.
    assert stat.S_IMODE(os.stat(socket_dir).st_mode) == 0o700
    # TCP-only attributes are unused on the unix transport.
    assert hyp._host is None
    assert hyp._port is None


def test_init_unix_fallback_name_without_node_id(tmp_path, monkeypatch):
    # node_id is normally always passed (one ubridge per node); the counter
    # fallback only fires when it's missing. Match the numbered pattern so the
    # assertion is independent of class-counter ordering across the suite.
    hyp = _make("unix", tmp_path, monkeypatch, node_id=None)
    assert re.search(r"ubridge-\d+\.sock$", hyp._socket_path)


def test_init_tcp_sets_host_port(tmp_path, monkeypatch):

    hyp = _make("tcp", tmp_path, monkeypatch)
    assert hyp._socket_path is None
    assert hyp._host == "127.0.0.1"
    assert isinstance(hyp._port, int) and hyp._port > 0


# ---------------------------------------------------------------------------
# _build_command + endpoint
# ---------------------------------------------------------------------------

def test_build_command_unix(tmp_path, monkeypatch):

    hyp = _make("unix", tmp_path, monkeypatch)
    cmd = hyp._build_command()
    assert cmd[0] == "ubridge"
    assert "-U" in cmd
    assert hyp._socket_path in cmd
    assert "-H" not in cmd
    assert "-d" not in cmd  # debug flag only at DEBUG level


def test_build_command_tcp(tmp_path, monkeypatch):

    hyp = _make("tcp", tmp_path, monkeypatch)
    cmd = hyp._build_command()
    assert cmd[0] == "ubridge"
    assert "-H" in cmd
    assert f"{hyp._host}:{hyp._port}" in cmd
    assert "-U" not in cmd


def test_build_command_debug_flag(tmp_path, monkeypatch):

    hyp = _make("unix", tmp_path, monkeypatch)
    logger = logging.getLogger("gns3server.compute.ubridge.hypervisor")
    original = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        cmd = hyp._build_command()
        assert "-d" in cmd and "1" in cmd
    finally:
        logger.setLevel(original)


def test_endpoint_unix(tmp_path, monkeypatch):

    hyp = _make("unix", tmp_path, monkeypatch)
    assert hyp.endpoint == hyp._socket_path


def test_endpoint_tcp(tmp_path, monkeypatch):

    hyp = _make("tcp", tmp_path, monkeypatch)
    assert hyp.endpoint == f"{hyp._host}:{hyp._port}"


# ---------------------------------------------------------------------------
# stop: AF_UNIX socket cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_unlinks_unix_socket(tmp_path, monkeypatch):

    hyp = _make("unix", tmp_path, monkeypatch)
    # Simulate the socket file ubridge would have created.
    open(hyp._socket_path, "w").close()
    # Stopped process => is_running() is False => skips UBridgeHypervisor.stop (no send).
    hyp._process = MagicMock()
    hyp._process.returncode = 0
    assert os.path.exists(hyp._socket_path)

    await hyp.stop()

    assert not os.path.exists(hyp._socket_path)


@pytest.mark.asyncio
async def test_stop_tcp_has_no_socket_to_unlink(tmp_path, monkeypatch):
    # TCP transport: no socket_path, so stop must simply not raise.
    hyp = _make("tcp", tmp_path, monkeypatch)
    hyp._process = MagicMock()
    hyp._process.returncode = 0
    await hyp.stop()


# ---------------------------------------------------------------------------
# start: fail-fast on an immediately-exiting uBridge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_detects_immediate_exit(tmp_path, monkeypatch):
    # An unsupported flag (e.g. -U on an old ubridge) makes the process exit at
    # once. start() must surface that from ubridge.log instead of timing out in
    # connect() with a confusing "couldn't connect" error.
    hyp = _make("unix", tmp_path, monkeypatch)
    proc = MagicMock()
    proc.pid = 1234
    proc.returncode = 2  # already exited
    with patch.object(Hypervisor, "_check_ubridge_version", new_callable=AsyncMock), \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
        with pytest.raises(UbridgeError, match="exited immediately"):
            await hyp.start()


@pytest.mark.asyncio
async def test_start_proceeds_when_process_keeps_running(tmp_path, monkeypatch):
    # Healthy startup: the process stays up, so start() returns normally.
    hyp = _make("unix", tmp_path, monkeypatch)
    proc = MagicMock()
    proc.pid = 1234
    proc.returncode = None  # still running
    with patch.object(Hypervisor, "_check_ubridge_version", new_callable=AsyncMock), \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
        await hyp.start()  # must NOT raise
    assert hyp._process is proc
