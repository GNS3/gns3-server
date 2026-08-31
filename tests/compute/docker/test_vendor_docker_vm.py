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
Tests for the VendorDockerVM subclass (vendor NOS containers, e.g. Nokia SR
Linux) and the Docker manager's class-selection factory.

These tests cover:
  * the factory selecting VendorDockerVM iff console_type == "docker_exec";
  * GNS3_* env parsing (SKIP_INIT, INTERFACE_NAMES, CONSOLE_CMD);
  * init.sh prepend being skipped with GNS3_SKIP_INIT;
  * GNS3_INTERFACE_NAMES renaming injected interfaces (move_to_ns target);
  * the hardcoded /etc/network mount being dropped for SKIP_INIT containers;
  * persistent volumes being seeded host-side and bound directly at their
    real in-container paths (no post-start bridge racing the NOS boot);
  * the docker_exec console dispatch in start();
  * the container-side _fix_permissions passes.
"""

import uuid
import os

import pytest
import pytest_asyncio

from unittest.mock import patch, MagicMock, call

from tests.utils import asyncio_patch, AsyncioMagicMock

from gns3server.compute.docker import Docker
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.docker.vendor_docker_vm import VendorDockerVM, _LazyExecTelnetServer
from gns3server.compute.docker.docker_error import DockerError, DockerHttp404Error


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _create_response(vm, entrypoint=None, volumes=None):
    """Build the Docker /containers/create response (with image info merged)."""
    return {
        "Id": "e90e34656806",
        "Warnings": [],
        "Config": {
            "Entrypoint": entrypoint,
            "Cmd": [],
            "Volumes": volumes,
        },
    }


@pytest_asyncio.fixture
async def manager(port_manager):

    m = Docker.instance()
    m.port_manager = port_manager
    return m


def _make_vm(compute_project, manager, environment=None, console_type="docker_exec",
             extra_volumes=None, adapters=4):
    """Build a VendorDockerVM with a fake cid (no create() called)."""
    vm = VendorDockerVM(
        "srlinux-1", str(uuid.uuid4()), compute_project, manager, "srlinux:latest",
        console_type=console_type, environment=environment,
        extra_volumes=extra_volumes or [], adapters=adapters,
    )
    vm._cid = "e90e34656842"
    return vm


# ---------------------------------------------------------------------------
# Factory selection
# ---------------------------------------------------------------------------

def test_factory_selects_vendor_when_docker_exec(manager):

    assert manager._select_node_class(console_type="docker_exec") is VendorDockerVM


def test_factory_selects_base_for_other_console_types(manager):

    for ct in ("telnet", "ssh", "vnc", "http", "https", "none", "spice"):
        assert manager._select_node_class(console_type=ct) is DockerVM, ct


def test_factory_default_is_base(manager):

    assert manager._select_node_class() is DockerVM


@pytest.mark.asyncio
async def test_create_node_sets_node_class(manager, compute_project, monkeypatch):
    """create_node() must switch _NODE_CLASS based on console_type."""

    captured = {}

    async def fake_super_create_node(name, project_id, node_id, *args, **kwargs):
        # record which class create_node selected before delegating
        captured["cls"] = manager._NODE_CLASS
        return None

    monkeypatch.setattr(
        "gns3server.compute.base_manager.BaseManager.create_node",
        fake_super_create_node,
    )

    await manager.create_node("v", compute_project.id, str(uuid.uuid4()),
                              "srlinux:latest", console_type="docker_exec")
    assert captured["cls"] is VendorDockerVM

    await manager.create_node("v", compute_project.id, str(uuid.uuid4()),
                              "ubuntu:latest", console_type="telnet")
    assert captured["cls"] is DockerVM


# ---------------------------------------------------------------------------
# GNS3_* env parsing
# ---------------------------------------------------------------------------

def test_env_skip_init_true(compute_project, manager):

    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1")
    assert vm._gns3_init is False


def test_env_skip_init_absent_defaults_true(compute_project, manager):

    vm = _make_vm(compute_project, manager, environment="FOO=bar")
    assert vm._gns3_init is True


def test_env_interface_names(compute_project, manager):

    vm = _make_vm(compute_project, manager,
                  environment="GNS3_INTERFACE_NAMES=mgmt0,e1-1,e1-2,e1-3")
    assert vm._interface_names == ["mgmt0", "e1-1", "e1-2", "e1-3"]


def test_env_console_cmd(compute_project, manager):

    vm = _make_vm(compute_project, manager,
                  environment="GNS3_CONSOLE_CMD=/opt/srlinux/bin/sr_cli")
    assert vm._console_cmd == "/opt/srlinux/bin/sr_cli"


def test_env_multiple_lines(compute_project, manager):

    vm = _make_vm(compute_project, manager,
                  environment=("GNS3_SKIP_INIT=1\n"
                               "GNS3_INTERFACE_NAMES=mgmt0,e1-1\n"
                               "GNS3_CONSOLE_CMD=/opt/srlinux/bin/sr_cli\n"))
    assert vm._gns3_init is False
    assert vm._interface_names == ["mgmt0", "e1-1"]
    assert vm._console_cmd == "/opt/srlinux/bin/sr_cli"


def test_env_console_cmd_default_none(compute_project, manager):

    vm = _make_vm(compute_project, manager)
    assert vm._console_cmd is None


# ---------------------------------------------------------------------------
# create() — init.sh skip, GNS3_MAX_ETHERNET, /etc/network drop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_skip_init_omits_init_sh(compute_project, manager):

    response = _create_response(None, entrypoint=["/init"])
    with asyncio_patch("gns3server.compute.docker.Docker.list_images",
                       return_value=[{"image": "srlinux"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query",
                           return_value=response) as mock:
            vm = VendorDockerVM("srlinux-1", str(uuid.uuid4()), compute_project,
                                manager, "srlinux:latest",
                                console_type="docker_exec",
                                environment="GNS3_SKIP_INIT=1")
            await vm.create()
            # the Entrypoint must NOT contain /gns3/init.sh
            sent = mock.call_args.kwargs["data"]
            assert "/gns3/init.sh" not in sent["Entrypoint"]
            assert sent["Entrypoint"] == ["/init"]


@pytest.mark.asyncio
async def test_create_without_skip_init_prepends_init_sh(compute_project, manager):

    response = _create_response(None, entrypoint=["/init"])
    with asyncio_patch("gns3server.compute.docker.Docker.list_images",
                       return_value=[{"image": "srlinux"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query",
                           return_value=response) as mock:
            vm = VendorDockerVM("srlinux-1", str(uuid.uuid4()), compute_project,
                                manager, "srlinux:latest",
                                console_type="docker_exec")
            await vm.create()
            sent = mock.call_args.kwargs["data"]
            # init.sh IS prepended when not skipping
            assert sent["Entrypoint"][0] == "/gns3/init.sh"


@pytest.mark.asyncio
async def test_create_interface_names_sets_max_ethernet(compute_project, manager):

    response = _create_response(None)
    with asyncio_patch("gns3server.compute.docker.Docker.list_images",
                       return_value=[{"image": "srlinux"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query",
                           return_value=response) as mock:
            vm = VendorDockerVM("srlinux-1", str(uuid.uuid4()), compute_project,
                                manager, "srlinux:latest", adapters=4,
                                console_type="docker_exec",
                                environment="GNS3_SKIP_INIT=1\nGNS3_INTERFACE_NAMES=mgmt0,e1-1,e1-2,e1-3")
            await vm.create()
            sent = mock.call_args.kwargs["data"]
            # last interface (adapter index 3) should be e1-3, not eth3
            assert any(v == "GNS3_MAX_ETHERNET=e1-3" for v in sent["Env"])


@pytest.mark.asyncio
async def test_create_drops_etc_network_for_skip_init(compute_project, manager):

    response = _create_response(None, volumes={"/opt/srlinux/appmgr": None})
    seed_proc = MagicMock()
    seed_proc.communicate = AsyncioMagicMock(return_value=(b"seedcid", b""))
    seed_proc.returncode = 0
    with asyncio_patch("gns3server.compute.docker.Docker.list_images",
                       return_value=[{"image": "srlinux"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query",
                           return_value=response) as mock:
            with patch("asyncio.subprocess.create_subprocess_exec",
                       return_value=seed_proc):
                vm = VendorDockerVM("srlinux-1", str(uuid.uuid4()), compute_project,
                                    manager, "srlinux:latest",
                                    console_type="docker_exec",
                                    environment="GNS3_SKIP_INIT=1",
                                    extra_volumes=["/etc/opt/srlinux"])
                await vm.create()
                sent = mock.call_args.kwargs["data"]
                targets = [m["Target"] for m in sent["HostConfig"]["Mounts"]]
                # /etc/network must NOT be mounted
                assert "/gns3volumes/etc/network" not in targets
                assert "/etc/network" not in targets
                # the declared volumes are bound DIRECTLY at their real paths —
                # no /gns3volumes aliasing and no post-start bridge
                assert "/opt/srlinux/appmgr" in targets
                assert "/etc/opt/srlinux" in targets
                assert not any(t.startswith("/gns3volumes/") for t in targets)
                # GNS3_VOLUMES env must also exclude /etc/network
                vol_env = [v for v in sent["Env"] if v.startswith("GNS3_VOLUMES=")][0]
                assert "/etc/network" not in vol_env
                # host skeleton dir removed
                assert not os.path.exists(os.path.join(vm.working_dir, "etc", "network"))


@pytest.mark.asyncio
async def test_create_keeps_etc_network_without_skip_init(compute_project, manager):

    response = _create_response(None)
    with asyncio_patch("gns3server.compute.docker.Docker.list_images",
                       return_value=[{"image": "srlinux"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query",
                           return_value=response) as mock:
            vm = VendorDockerVM("srlinux-1", str(uuid.uuid4()), compute_project,
                                manager, "srlinux:latest",
                                console_type="docker_exec")
            await vm.create()
            sent = mock.call_args.kwargs["data"]
            targets = [m["Target"] for m in sent["HostConfig"]["Mounts"]]
            assert "/gns3volumes/etc/network" in targets


# ---------------------------------------------------------------------------
# Interface renaming (_get_container_ifname / move_to_ns)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_move_to_ns_uses_renamed_interface(compute_project, manager):

    vm = _make_vm(compute_project, manager,
                  environment="GNS3_SKIP_INIT=1\nGNS3_INTERFACE_NAMES=mgmt0,e1-1,e1-2,e1-3")
    vm._ubridge_hypervisor = MagicMock()
    vm._namespace = 42
    nio = manager.create_nio({"type": "nio_udp", "lport": 4242, "rport": 4343, "rhost": "127.0.0.1"})
    await vm._add_ubridge_connection(nio, 0)
    # adapter 0 should be renamed to mgmt0
    move_calls = [c for c in vm._ubridge_hypervisor.method_calls if "move_to_ns" in str(c)]
    assert move_calls, "move_to_ns was not sent"
    assert call.send("docker move_to_ns tap-gns3-e0 42 mgmt0") in move_calls


@pytest.mark.asyncio
async def test_move_to_ns_falls_back_to_eth(compute_project, manager):

    vm = _make_vm(compute_project, manager)  # no INTERFACE_NAMES
    vm._ubridge_hypervisor = MagicMock()
    vm._namespace = 42
    nio = manager.create_nio({"type": "nio_udp", "lport": 4242, "rport": 4343, "rhost": "127.0.0.1"})
    await vm._add_ubridge_connection(nio, 1)
    move_calls = [c for c in vm._ubridge_hypervisor.method_calls if "move_to_ns" in str(c)]
    assert call.send("docker move_to_ns tap-gns3-e0 42 eth1") in move_calls


# ---------------------------------------------------------------------------
# start() — docker_exec console dispatch + volume bridge + permission fix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_docker_exec_dispatches_console(compute_project, manager):

    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1")
    vm.adapters = 1
    vm._get_container_state = AsyncioMagicMock(return_value="stopped")
    vm._start_ubridge = AsyncioMagicMock()
    vm._get_namespace = AsyncioMagicMock(return_value=42)
    vm._add_ubridge_connection = AsyncioMagicMock()
    vm._start_docker_exec_console = AsyncioMagicMock()
    vm._fix_permissions = AsyncioMagicMock()

    with patch("gns3server.compute.docker.Docker.install_busybox"):
        with asyncio_patch("gns3server.compute.docker.Docker.query"):
            await vm.start()

    vm._start_docker_exec_console.assert_called_once()
    assert vm.status == "started"
    # SKIP_INIT path still runs the permission fix (volumes are already
    # seeded and bound at create time — no post-start bridge anymore)
    vm._fix_permissions.assert_called_once()


@pytest.mark.asyncio
async def test_start_without_skip_init_skips_vendor_passes(compute_project, manager):

    vm = _make_vm(compute_project, manager)  # no SKIP_INIT
    vm.adapters = 1
    vm.console_type = "docker_exec"
    vm._get_container_state = AsyncioMagicMock(return_value="stopped")
    vm._start_ubridge = AsyncioMagicMock()
    vm._get_namespace = AsyncioMagicMock(return_value=42)
    vm._add_ubridge_connection = AsyncioMagicMock()
    vm._start_docker_exec_console = AsyncioMagicMock()
    vm._fix_permissions = AsyncioMagicMock()

    with patch("gns3server.compute.docker.Docker.install_busybox"):
        with asyncio_patch("gns3server.compute.docker.Docker.query"):
            await vm.start()

    # init.sh runs (no SKIP_INIT) → no vendor permission pass
    vm._fix_permissions.assert_not_called()


# ---------------------------------------------------------------------------
# _fix_permissions — container-side, skips dead containers, targets volume paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fix_permissions_skips_dead_container(compute_project, manager):

    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1")
    vm._volumes = ["/etc/opt/srlinux"]
    vm._get_container_state = AsyncioMagicMock(return_value="exited")

    with patch("asyncio.subprocess.create_subprocess_exec") as mock_exec:
        await vm._fix_permissions()
        # must NOT exec into a dead container
        mock_exec.assert_not_called()


@pytest.mark.asyncio
async def test_fix_permissions_skips_missing_container(compute_project, manager):

    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1")
    vm._volumes = ["/etc/opt/srlinux"]
    vm._get_container_state = AsyncioMagicMock(side_effect=DockerHttp404Error("nope"))

    with patch("asyncio.subprocess.create_subprocess_exec") as mock_exec:
        await vm._fix_permissions()
        mock_exec.assert_not_called()


@pytest.mark.asyncio
async def test_fix_permissions_targets_volume_paths(compute_project, manager):

    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1")
    vm._volumes = ["/etc/opt/srlinux", "/var/log/srlinux"]
    vm._get_container_state = AsyncioMagicMock(return_value="running")

    proc = MagicMock()
    proc.wait = AsyncioMagicMock(return_value=0)
    proc.returncode = 0
    proc.stderr = MagicMock()
    proc.stderr.read = AsyncioMagicMock(return_value=b"")

    with patch("asyncio.subprocess.create_subprocess_exec",
               return_value=proc) as mock_exec:
        await vm._fix_permissions()
        # one exec per volume
        assert mock_exec.call_count == 2
        # each script must target the real in-container path (the direct
        # bind mount), never the old /gns3volumes alias
        for call_obj in mock_exec.call_args_list:
            script = call_obj.args[-1]  # last positional arg is the sh -c script
            assert "/gns3volumes" not in script
            assert '"/etc/opt/srlinux"' in script or '"/var/log/srlinux"' in script
            assert 'chown' in script


# ---------------------------------------------------------------------------
# _prepare_volumes — host-side seeding (docker create + cp + rm)
# ---------------------------------------------------------------------------

def _seed_proc(stdout=b"seedcid\n", returncode=0):
    proc = MagicMock()
    proc.communicate = AsyncioMagicMock(return_value=(stdout, b""))
    proc.returncode = returncode
    return proc


@pytest.mark.asyncio
async def test_prepare_volumes_seeds_unmarked_volume(compute_project, manager):

    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1",
                  extra_volumes=["/etc/opt/srlinux"])
    image_info = {"Config": {"Volumes": {}}}

    with patch("asyncio.subprocess.create_subprocess_exec",
               return_value=_seed_proc()) as mock_exec:
        await vm._prepare_volumes(image_info)
        # docker create + docker cp + docker rm
        assert mock_exec.call_count == 3
        argvs = [c.args for c in mock_exec.call_args_list]
        assert argvs[0][1:3] == ("create", "srlinux:latest")
        assert argvs[1][1:4] == ("cp", "-a", "seedcid:/etc/opt/srlinux/.")
        assert argvs[2][1:3] == ("rm", "-f")
        host_dir = os.path.join(vm.working_dir, "etc", "opt", "srlinux")
        assert os.path.exists(os.path.join(host_dir, ".gns3_perms"))

        # a second create() must not re-seed (marker present): no docker CLI call
        await vm._prepare_volumes(image_info)
        assert mock_exec.call_count == 3


@pytest.mark.asyncio
async def test_prepare_volumes_never_overwrites_marked_volume(compute_project, manager):
    """Regression guard: a volume that ever started (marker present) holds the
    node's saved configuration — re-seeding would reset it to factory."""

    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1",
                  extra_volumes=["/etc/opt/srlinux"])
    host_dir = os.path.join(vm.working_dir, "etc", "opt", "srlinux")
    os.makedirs(host_dir, exist_ok=True)
    marker = os.path.join(host_dir, ".gns3_perms")
    open(marker, "w").close()
    saved = os.path.join(host_dir, "config.json")
    with open(saved, "w") as f:
        f.write('{"user": "config"}')

    with patch("asyncio.subprocess.create_subprocess_exec",
               return_value=_seed_proc()) as mock_exec:
        await vm._prepare_volumes({"Config": {"Volumes": {}}})
        mock_exec.assert_not_called()
    with open(saved) as f:
        assert f.read() == '{"user": "config"}'


@pytest.mark.asyncio
async def test_prepare_volumes_tolerates_missing_image_path(compute_project, manager):
    """A volume path the image does not contain (e.g. XRd's /xr-storage-shadow)
    starts empty — cp fails, the marker is still written, no raise."""

    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1",
                  extra_volumes=["/xr-storage-shadow"])
    calls = {"n": 0}

    def proc_factory(*args, **kwargs):
        # first call (docker create) succeeds, second (docker cp) fails,
        # third (docker rm) succeeds
        codes = [0, 1, 0]
        proc = _seed_proc(returncode=codes[calls["n"]])
        calls["n"] += 1
        return proc

    with patch("asyncio.subprocess.create_subprocess_exec",
               side_effect=proc_factory):
        await vm._prepare_volumes({"Config": {"Volumes": {}}})
        assert calls["n"] == 3  # rm still ran (finally path)
    host_dir = os.path.join(vm.working_dir, "xr-storage-shadow")
    assert os.path.exists(os.path.join(host_dir, ".gns3_perms"))


@pytest.mark.asyncio
async def test_prepare_volumes_skips_without_skip_init(compute_project, manager):

    vm = _make_vm(compute_project, manager)  # no SKIP_INIT
    with patch("asyncio.subprocess.create_subprocess_exec",
               return_value=_seed_proc()) as mock_exec:
        await vm._prepare_volumes({"Config": {"Volumes": {"/etc/opt/srlinux": None}}})
        mock_exec.assert_not_called()


@pytest.mark.asyncio
async def test_prepare_volumes_raises_when_seed_container_fails(compute_project, manager):
    """If `docker create` itself fails, creation must abort loudly instead of
    binding an empty directory over the NOS's config path."""

    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1",
                  extra_volumes=["/etc/opt/srlinux"])
    proc = _seed_proc(stdout=b"", returncode=1)

    with patch("asyncio.subprocess.create_subprocess_exec", return_value=proc):
        with pytest.raises(DockerError):
            await vm._prepare_volumes({"Config": {"Volumes": {}}})


# ---------------------------------------------------------------------------
# _cleanup_console_resources
# ---------------------------------------------------------------------------

def test_cleanup_console_resources_closes_writer(compute_project, manager):

    vm = _make_vm(compute_project, manager)
    writer = MagicMock()
    vm._console_exec_writer = writer
    vm._cleanup_console_resources()
    writer.close.assert_called_once()
    assert vm._console_exec_writer is None


def test_cleanup_console_resources_no_writer(compute_project, manager):

    vm = _make_vm(compute_project, manager)
    vm._console_exec_writer = None
    # must not raise
    vm._cleanup_console_resources()


# ---------------------------------------------------------------------------
# _LazyExecTelnetServer — upstream aliveness + reconnect/recreate logic
# ---------------------------------------------------------------------------

def _make_lazy_server(compute_project, manager, environment="GNS3_CONSOLE_CMD=/opt/srlinux/bin/sr_cli"):
    """Build a _LazyExecTelnetServer with _create_exec mocked out (no docker)."""
    vm = _make_vm(compute_project, manager, environment=environment)
    srv = _LazyExecTelnetServer(
        vm, manager, "e90e34656842", "/opt/srlinux/bin/sr_cli",
        allow_resize=vm._console_resize,
    )
    srv._create_exec = AsyncioMagicMock()
    srv._resize_exec = AsyncioMagicMock()
    return srv


def _live_writer():
    """A writer mock that reports as open (not closing)."""
    w = MagicMock()
    w.is_closing.return_value = False
    return w


def _dead_writer():
    """A writer mock that reports as closing (pty closed)."""
    w = MagicMock()
    w.is_closing.return_value = True
    return w


def test_upstream_alive_never_created(compute_project, manager):

    srv = _make_lazy_server(compute_project, manager)
    assert srv._upstream_alive() is False


def test_upstream_alive_writer_closing(compute_project, manager):

    srv = _make_lazy_server(compute_project, manager)
    srv._exec_id = "abc"
    srv._writer = _dead_writer()
    srv._broadcast_task = MagicMock()
    srv._broadcast_task.done.return_value = False
    assert srv._upstream_alive() is False


def test_upstream_alive_broadcast_done(compute_project, manager):

    srv = _make_lazy_server(compute_project, manager)
    srv._exec_id = "abc"
    srv._writer = _live_writer()
    srv._broadcast_task = MagicMock()
    srv._broadcast_task.done.return_value = True  # CLI exited → EOF → task ended
    assert srv._upstream_alive() is False


def test_upstream_alive_live(compute_project, manager):

    srv = _make_lazy_server(compute_project, manager)
    srv._exec_id = "abc"
    srv._writer = _live_writer()
    srv._broadcast_task = MagicMock()
    srv._broadcast_task.done.return_value = False
    assert srv._upstream_alive() is True


@pytest.mark.asyncio
async def test_first_connect_creates_exec(compute_project, manager):

    srv = _make_lazy_server(compute_project, manager)
    # never created → must create
    await srv.client_connected_hook()
    srv._create_exec.assert_called_once()


@pytest.mark.asyncio
async def test_first_connect_sets_tall_default_pty_geometry(compute_project, manager):
    """The exec PTY must start tall/wide: a 24-row initial geometry makes CLIs
    that page on the PTY window size (IOS-XR pager) park at --More-- for
    clients that never send NAWS (netmiko, bare telnet)."""

    srv = _make_lazy_server(compute_project, manager)
    await srv.client_connected_hook()
    srv._resize_exec.assert_called_once_with(511, 10000)


@pytest.mark.asyncio
async def test_client_naws_resizes_exec_by_default(compute_project, manager):
    """Client-driven NAWS (WS terminal-size frames) reaches the exec resize."""

    srv = _make_lazy_server(compute_project, manager)
    await srv._on_naws(120, 40)
    srv._resize_exec.assert_called_once_with(120, 40)


@pytest.mark.asyncio
async def test_client_naws_ignored_when_resize_disabled(compute_project, manager):
    """GNS3_CONSOLE_RESIZE=0: client resizes must not change the shared exec
    geometry (paging CLIs need the tall default for concurrent netmiko)."""

    srv = _make_lazy_server(
        compute_project, manager,
        environment="GNS3_CONSOLE_RESIZE=0",
    )
    assert srv._allow_resize is False
    await srv._on_naws(120, 40)
    srv._resize_exec.assert_not_called()
    # the tall default is still applied at exec creation (internal path)
    await srv.client_connected_hook()
    srv._resize_exec.assert_called_once_with(511, 10000)


@pytest.mark.asyncio
async def test_last_client_disconnect_restores_tall_default(compute_project, manager):
    """When the last console client leaves, the exec goes back to the tall
    no-NAWS default so a later non-NAWS client (netmiko) doesn't inherit a
    browser geometry and hit PTY-window paging."""

    srv = _make_lazy_server(compute_project, manager)
    srv._exec_id = "abc"
    writer = AsyncioMagicMock()
    await srv._disconnect_client(writer)
    srv._resize_exec.assert_called_once_with(511, 10000)


@pytest.mark.asyncio
async def test_size_arriving_before_exec_wins_over_default(compute_project, manager):
    """A client size that races the exec creation (WS control frame / NAWS
    arriving inside client_connected_hook) must not be overwritten by the
    tall default once the exec exists."""

    srv = _make_lazy_server(compute_project, manager)
    assert srv._exec_id is None
    # real _resize_exec (not the mock) records the size when no exec exists
    srv._resize_exec = _LazyExecTelnetServer._resize_exec.__get__(srv)
    await srv._on_naws(120, 40)
    assert srv._client_size == (120, 40)

    srv._resize_exec = AsyncioMagicMock()
    await srv.client_connected_hook()
    srv._resize_exec.assert_called_once_with(120, 40)


@pytest.mark.asyncio
async def test_reconnect_live_exec_not_recreated(compute_project, manager):
    """Reconnecting while the exec is alive must NOT recreate it."""

    srv = _make_lazy_server(compute_project, manager)
    srv._exec_id = "abc"
    srv._writer = _live_writer()
    srv._broadcast_task = MagicMock()
    srv._broadcast_task.done.return_value = False

    await srv.client_connected_hook()
    srv._create_exec.assert_not_called()
    # Ctrl-L redraw is still sent to the live writer
    srv._writer.write.assert_any_call(b"\x0c")


@pytest.mark.asyncio
async def test_reconnect_after_death_recreates_exec(compute_project, manager):
    """The core reconnect fix: after the CLI exits (broadcast task done),
    the next client connection recreates the exec so CPR gets answered."""

    srv = _make_lazy_server(compute_project, manager)
    # simulate a dead upstream: exec existed, but the pty closed / task ended
    srv._exec_id = "old-exec"
    srv._writer = _dead_writer()
    srv._broadcast_task = MagicMock()
    srv._broadcast_task.done.return_value = True

    await srv.client_connected_hook()
    srv._create_exec.assert_called_once()


@pytest.mark.asyncio
async def test_reconnect_closes_half_dead_writer(compute_project, manager):
    """If the writer is still open but the broadcast task died, the old writer
    must be closed before a new exec is created (no socket leak)."""

    srv = _make_lazy_server(compute_project, manager)
    srv._exec_id = "old-exec"
    srv._writer = _live_writer()  # still open, but...
    srv._broadcast_task = MagicMock()
    srv._broadcast_task.done.return_value = True  # ...task ended

    await srv.client_connected_hook()
    srv._writer.close.assert_called_once()
    srv._create_exec.assert_called_once()


@pytest.mark.asyncio
async def test_create_exec_cmd_has_no_while_true(compute_project, manager):
    """The command must NOT be wrapped in a while-true loop (regression guard:
    while-true restarts the CLI with no client to answer CPR → blank screen)."""

    vm = _make_vm(compute_project, manager)
    manager._server_url = "/var/run/docker.sock"
    manager._api_version = "1.40"
    srv = _LazyExecTelnetServer(vm, manager, "e90e34656842", "/opt/srlinux/bin/sr_cli")

    captured = {}

    async def fake_query(method, path, data=None, **kw):
        captured["data"] = data
        return {"Id": "exec123"}

    manager.query = fake_query

    with patch("asyncio.open_unix_connection") as mock_open:
        reader = MagicMock()
        reader.readuntil = AsyncioMagicMock(return_value=b"HTTP/1.1 101 Upgraded\r\n\r\n")
        writer = MagicMock()
        writer.is_closing.return_value = False
        mock_open.return_value = (reader, writer)
        await srv._create_exec()

    cmd = captured["data"]["Cmd"]
    assert cmd == ["sh", "-c", "/opt/srlinux/bin/sr_cli"]
    assert "while true" not in cmd[2]
    # must run as root with a pty and TERM
    assert captured["data"]["User"] == "root"
    assert captured["data"]["Tty"] is True
    assert "TERM=xterm" in captured["data"]["Env"]


# ---------------------------------------------------------------------------
# Container termination (graceful stop for vendor NOS)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_terminate_container_graceful_stop(compute_project, manager):
    """With graceful=True (explicit user stop) vendor containers are SIGTERMed
    with a grace period, not SIGKILLed on the spot: systemd NOS images
    (e.g. Cisco XRd) require a graceful shutdown, and Docker itself SIGKILLs
    the container once the grace period expires."""

    vm = _make_vm(compute_project, manager)
    manager.query = AsyncioMagicMock()
    manager.http_query = AsyncioMagicMock(return_value=MagicMock())

    await vm._terminate_container(graceful=True)

    manager.http_query.assert_called_once_with(
        "POST", "containers/e90e34656842/stop", params={"t": 60}, timeout=90)
    manager.query.assert_not_called()  # no kill on the graceful path


@pytest.mark.asyncio
async def test_terminate_container_default_is_kill(compute_project, manager):
    """Without graceful (delete/update/close/crash cleanup) the vendor
    container gets the base immediate kill — those paths force-delete or
    recreate the container right after anyway."""

    vm = _make_vm(compute_project, manager)
    manager.query = AsyncioMagicMock()
    manager.http_query = AsyncioMagicMock(return_value=MagicMock())

    await vm._terminate_container()

    manager.query.assert_called_once_with("POST", "containers/e90e34656842/kill")
    manager.http_query.assert_not_called()


@pytest.mark.asyncio
async def test_terminate_container_already_stopped_is_silent(compute_project, manager):
    """Docker answers 304 when the container is already stopped — that is not
    an error for the stop path."""

    from gns3server.compute.docker.docker_error import DockerHttp304Error

    vm = _make_vm(compute_project, manager)
    manager.http_query = AsyncioMagicMock(
        side_effect=DockerHttp304Error("Docker has returned an error: 304"))
    await vm._terminate_container(graceful=True)  # must not raise


@pytest.mark.asyncio
async def test_stop_uses_graceful_termination(compute_project, manager):
    """The full stop() path must route through _terminate_container (the
    vendor override); the default is the fast kill — only the explicit user
    stop route passes graceful=True."""

    vm = _make_vm(compute_project, manager)
    with patch.object(DockerVM, "_clean_servers", new=AsyncioMagicMock()):
        with patch.object(DockerVM, "_stop_ubridge", new=AsyncioMagicMock()):
            with patch.object(
                DockerVM, "_get_container_state", new=AsyncioMagicMock(return_value="running")
            ):
                vm._permissions_fixed = True
                with patch.object(
                    VendorDockerVM, "_terminate_container", new=AsyncioMagicMock()
                ) as mock_term:
                    await vm.stop()
    mock_term.assert_called_once_with(graceful=False)


def test_env_stop_timeout(compute_project, manager):
    vm = _make_vm(compute_project, manager, environment="GNS3_STOP_TIMEOUT=120")
    assert vm._stop_timeout == 120


def test_env_stop_timeout_default_60(compute_project, manager):
    vm = _make_vm(compute_project, manager, environment="GNS3_SKIP_INIT=1")
    assert vm._stop_timeout == 60


def test_env_stop_timeout_invalid_keeps_default(compute_project, manager):
    vm = _make_vm(compute_project, manager, environment="GNS3_STOP_TIMEOUT=abc")
    assert vm._stop_timeout == 60
    vm = _make_vm(compute_project, manager, environment="GNS3_STOP_TIMEOUT=9999")
    assert vm._stop_timeout == 60
    # ceiling: controller stop budget (240 s) minus the +30 s HTTP margin
    vm = _make_vm(compute_project, manager, environment="GNS3_STOP_TIMEOUT=211")
    assert vm._stop_timeout == 60
    vm = _make_vm(compute_project, manager, environment="GNS3_STOP_TIMEOUT=210")
    assert vm._stop_timeout == 210


@pytest.mark.asyncio
async def test_terminate_container_uses_env_timeout(compute_project, manager):
    vm = _make_vm(compute_project, manager, environment="GNS3_STOP_TIMEOUT=120")
    manager.http_query = AsyncioMagicMock(return_value=MagicMock())

    await vm._terminate_container(graceful=True)

    manager.http_query.assert_called_once_with(
        "POST", "containers/e90e34656842/stop", params={"t": 120}, timeout=150)


@pytest.mark.asyncio
async def test_create_reparse_refreshes_env_knobs(compute_project, manager):
    """A PUT to the node's environment must take effect on the next create(),
    not on the next project reload: create() re-parses the vendor knobs."""

    response = _create_response(None, entrypoint=["/init"])
    vm = _make_vm(compute_project, manager,
                  environment="GNS3_SKIP_INIT=1\nGNS3_STOP_TIMEOUT=120")
    assert vm._gns3_init is False and vm._stop_timeout == 120

    vm._environment = "GNS3_STOP_TIMEOUT=5"  # knob removed + value changed
    with asyncio_patch("gns3server.compute.docker.Docker.list_images",
                       return_value=[{"image": "srlinux"}]):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
            await vm.create()

    assert vm._stop_timeout == 5
    assert vm._gns3_init is True  # removed entry reset to default
