import asyncio
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gns3server.compute.configurations import ConfigurationService, wipe_configuration
from gns3server.compute.iou.iou_vm import IOUVM
from gns3server.schemas.configurations import Engine
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.node_lease import node_lease
from gns3server.services.configurations.shared.startup_journal import mark_started, runtime
from tests.support.configurations import native_node, qemu_disk_node
from tests.support.configurations import status_queries as status_queries


def node_at(root, **kwargs):
    return SimpleNamespace(working_dir=str(root), status="stopped", **kwargs)


@pytest.mark.asyncio
async def test_cancelled_wipe_holds_lifecycle_lease_until_files_and_journal_are_final(tmp_path, monkeypatch):
    from gns3server.compute import configurations

    node = node_at(tmp_path)
    (tmp_path / "startup.vpc").write_text("saved")
    started, acquired = asyncio.Event(), asyncio.Event()
    release = Event()
    loop = asyncio.get_running_loop()

    def paused_wipe(*args):
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        wipe_configuration(*args)

    async def wipe():
        async with node_lease(node):
            await ConfigurationService(node, Engine.vpcs).wipe()

    async def next_lifecycle_action():
        async with node_lease(node):
            acquired.set()
            assert runtime(node)["state"] == "clean"

    monkeypatch.setattr(configurations, "wipe_configuration", paused_wipe)
    wiping = asyncio.create_task(wipe())
    await asyncio.wait_for(started.wait(), timeout=2)
    contender = asyncio.create_task(next_lifecycle_action())
    try:
        for _ in range(2):
            wiping.cancel()
            await asyncio.sleep(0)
        assert not wiping.done()
        assert not acquired.is_set()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await wiping
    await contender
    assert not (tmp_path / "startup.vpc").exists()


def qemu_node(directory):
    return qemu_disk_node(directory)


@pytest.mark.parametrize(
    "engine,files,properties",
    [
        ("iou", ["nvram_00001", "nvram_00002", "vlan.dat-00001", "startup-config.cfg", "private-config.cfg"], {}),
        ("vpcs", ["startup.vpc"], {}),
        ("docker", ["etc/network/interfaces"], {"extra_configs": []}),
    ],
)
def test_native_wipe_is_repeatable_and_preserves_other_files(tmp_path, engine, files, properties):
    node = node_at(tmp_path, **properties)
    for filename in [*files, "keep.img"]:
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("saved state")
    wipe_configuration(node, engine)
    wipe_configuration(node, engine)
    assert all(not (tmp_path / filename).exists() for filename in files)
    assert (tmp_path / "keep.img").read_text() == "saved state"


@pytest.mark.parametrize("status", ["started", "suspended"])
def test_wipe_requires_stopped_node(tmp_path, status):
    path = tmp_path / "startup.vpc"
    path.write_text("saved config")
    node = node_at(tmp_path)
    node.status = status
    with pytest.raises(ConfigurationError, match="stop_required"):
        wipe_configuration(node, "vpcs")
    assert path.exists()


@pytest.mark.parametrize("filename", ["private-config.cfg", ".startup-runtime.json"])
def test_wipe_rejects_symlinks_before_erasing_other_configs(tmp_path, filename):
    saved = tmp_path / "startup-config.cfg"
    saved.write_text("saved config")
    (tmp_path / filename).symlink_to(saved)
    with pytest.raises(ConfigurationError, match="unsafe_configuration_path"):
        wipe_configuration(node_at(tmp_path), "iou")
    assert saved.read_text() == "saved config"


@pytest.mark.parametrize("linked,local", [(False, False), (True, True)])
def test_qemu_wipe_rejects_non_disposable_disks_without_partial_erasure(tmp_path, linked, local):
    root = tmp_path / "node"
    root.mkdir()
    base = tmp_path / "base.qcow2"
    base.write_text("base")
    other = root / "imported.qcow2"
    other.write_text("only copy")
    overlay = root / "hda_disk.qcow2"
    overlay.write_text("changes")
    node = node_at(
        root,
        linked_clone=linked,
        create_config_disk=False,
        _hda_disk_image=str(base),
        _hdb_disk_image=str(other) if local else "",
        _hdc_disk_image="",
        _hdd_disk_image="",
    )
    with pytest.raises(ConfigurationError, match="configuration_wipe_unsupported"):
        wipe_configuration(node, "qemu")
    assert overlay.read_text() == "changes"
    assert other.read_text() == "only copy"


@pytest.mark.parametrize("properties", [{"_gns3_init": False}, {"extra_configs": ["custom"]}])
def test_docker_wipe_rejects_unmanaged_configuration(tmp_path, properties):
    node = node_at(tmp_path, **{"extra_configs": [], **properties})
    with pytest.raises(ConfigurationError, match="configuration_wipe_unsupported"):
        wipe_configuration(node, "docker")


@pytest.mark.asyncio
@pytest.mark.parametrize("engine", ["docker", "dynamips"])
@pytest.mark.parametrize("outcome", ["stopped", "unavailable"])
async def test_wipe_runtime_checks_preserve_files_on_failure_and_allow_stopped_nodes(
    tmp_path, monkeypatch, engine, outcome
):
    from unittest.mock import AsyncMock

    from gns3server.compute.configurations import ConfigurationService
    from gns3server.schemas.configurations import Engine

    saved = tmp_path / "etc/network/interfaces" if engine == "docker" else tmp_path / "startup.cfg"
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_text("saved")
    node = node_at(
        tmp_path,
        extra_configs=[],
        _hypervisor=object(),
        startup_config_path=str(saved),
        private_config_path=str(tmp_path / "private.cfg"),
        platform="c7200",
        dynamips_id=1,
    )

    async def check(*args):
        if outcome == "unavailable":
            raise ConfigurationError("container_state_unavailable" if engine == "docker" else "hypervisor_unavailable")
        return True if engine == "docker" else ["0"]

    check = AsyncMock(side_effect=check)
    monkeypatch.setattr(
        "gns3server.compute.configurations." + ("docker_stopped" if engine == "docker" else "dynamips_query"), check
    )
    service = ConfigurationService(node, Engine(engine))
    if outcome == "stopped":
        await service.wipe()
        assert not saved.exists()
    else:
        with pytest.raises(ConfigurationError):
            await service.wipe()
        assert saved.read_text() == "saved"
    check.assert_awaited_once()


def test_qemu_wipe_discards_all_normal_overlays_but_preserves_the_hdd_overlay_and_other_files(tmp_path):
    root = tmp_path / "node"
    root.mkdir()
    bases = {}
    for drive in "abcd":
        base = tmp_path / f"base-{drive}.qcow2"
        base.write_text("base")
        bases[f"_hd{drive}_disk_image"] = str(base)
        (root / f"hd{drive}_disk.qcow2").write_text("changes")
    keep = root / "keep.cfg"
    keep.write_text("keep")
    wipe_configuration(node_at(root, linked_clone=True, create_config_disk=True, **bases), "qemu")
    assert all(not (root / f"hd{drive}_disk.qcow2").exists() for drive in "abc")
    assert (root / "hdd_disk.qcow2").read_text() == "changes"
    assert all((tmp_path / f"base-{drive}.qcow2").read_text() == "base" for drive in "abcd")
    assert keep.read_text() == "keep"


@pytest.mark.asyncio
async def test_wipe_preflight_reports_ineligible_storage_without_touching_a_running_node(tmp_path):
    node = qemu_node(tmp_path / "node")
    node.status = "started"
    overlay = Path(node.working_dir) / "hda_disk.qcow2"
    overlay.write_text("changes")
    await ConfigurationService(node, Engine.qemu).preflight_wipe()
    node.linked_clone = False
    with pytest.raises(ConfigurationError, match="configuration_wipe_unsupported"):
        await ConfigurationService(node, Engine.qemu).preflight_wipe()
    assert overlay.read_text() == "changes"


def test_qemu_wipe_is_a_factory_reset_of_the_config_disk_and_tpm_state(tmp_path):
    node = qemu_node(tmp_path / "node")
    root = Path(node.working_dir)
    (root / "tpm").mkdir()
    owned = [root / name for name in ("config.img", "config.zip", "tpm/tpm2-00.permall", "tpm/.lock")]
    for path in (*owned, root / "hda_disk.qcow2"):
        path.write_text("guest state")
    wipe_configuration(node, "qemu")
    assert not any(path.exists() for path in owned)


def test_qemu_wipe_refuses_a_tpm_directory_that_is_a_link(tmp_path):
    node = qemu_node(tmp_path / "node")
    root = Path(node.working_dir)
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "elsewhere" / "keep").write_text("keep")
    (root / "tpm").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(ConfigurationError, match="unsafe_configuration_path"):
        wipe_configuration(node, "qemu")
    assert (tmp_path / "elsewhere" / "keep").read_text() == "keep"


@pytest.mark.parametrize(
    "options",
    [
        "-drive file=data.qcow2,if=virtio",
        "-drive file=/srv/shared/data.img,format=raw",
        "-drive if=pflash,format=raw,file=vars-extra.fd",
        "-hdb data.qcow2",
        "-mtdblock flash.bin",
        "-blockdev driver=file,node-name=d,filename=data.img",
        '-drive file="unterminated',
    ],
)
def test_qemu_wipe_refuses_writable_storage_added_through_the_options(tmp_path, options):
    node = qemu_node(tmp_path / "node")
    node.options = options
    overlay = Path(node.working_dir) / "hda_disk.qcow2"
    overlay.write_text("changes")
    with pytest.raises(ConfigurationError, match="configuration_extra_storage"):
        wipe_configuration(node, "qemu")
    assert overlay.read_text() == "changes"


@pytest.mark.parametrize(
    "options",
    [
        "-machine q35 -smbios type=1,product=x -hdachs 980,16,32",
        "-drive file=/srv/firmware.fd,if=pflash,readonly=on",
        "-drive file=/srv/tools.iso,media=cdrom",
        "-drive file=/srv/scratch.img,snapshot=on",
        "-snapshot -drive file=/srv/data.img",
        "-drive if=none,id=empty",
        "-drive if=pflash,format=raw,file=OVMF_VARS.fd",
        "-cdrom /srv/tools.iso",
        "-blockdev driver=file,node-name=d,filename=data.img,read-only=on",
    ],
)
def test_qemu_wipe_accepts_options_that_leave_nothing_behind(tmp_path, options):
    node = qemu_node(tmp_path / "node")
    node.options = options
    (Path(node.working_dir) / "hda_disk.qcow2").write_text("changes")
    wipe_configuration(node, "qemu")
    assert not (Path(node.working_dir) / "hda_disk.qcow2").exists()


def test_iou_wipe_removes_only_the_files_the_emulator_generates(tmp_path):
    root = tmp_path / "node"
    root.mkdir()
    generated = [root / name for name in ("nvram_00007", "nvram_00912", "vlan.dat-00007")]
    other = [root / name for name in ("nvram_notes.txt", "nvram_00007.bak", "vlan.dat-backup")]
    for path in (*generated, *other):
        path.write_text("data")
    wipe_configuration(node_at(root), "iou")
    assert not any(path.exists() for path in generated)
    assert all(path.exists() for path in other)


@pytest.mark.parametrize("journal", [False, True])
def test_qemu_wipe_is_repeatable_and_resets_only_the_runtime_state(tmp_path, journal):
    """Overlays and private UEFI variables go every time, with or without the journal the first wipe leaves."""
    from gns3server.services.configurations.shared.startup_journal import journal_path

    node = qemu_node(tmp_path / "node")
    root = Path(node.working_dir)
    if journal:
        journal_path(node).write_text('{"version": 1, "generation": 1, "state": "clean"}')
    firmware = root / "OVMF_CODE_4M.fd"
    firmware.write_bytes(b"read-only firmware code")
    runtime = ("hda_disk.qcow2", "OVMF_VARS.fd", "OVMF_VARS_4M.fd", "AAVMF_VARS.fd")
    for attempt in ("first", "second"):
        for name in runtime:
            (root / name).write_bytes(b"previous runtime")
        wipe_configuration(node, "qemu")
        assert not any((root / name).exists() for name in runtime), attempt
    assert firmware.read_bytes() == b"read-only firmware code"
    assert Path(node._hda_disk_image).read_bytes() == b"shared base image"


def test_a_wipe_that_fails_halfway_blocks_start_until_it_is_repeated(tmp_path, monkeypatch):
    """Retry rule: files already gone stay gone, the node is not startable meanwhile, and a second wipe finishes."""
    from gns3server.services.configurations.shared.startup_journal import (
        journal_path,
        mark_wiped,
        require_launchable,
        runtime,
    )

    root = tmp_path / "node"
    root.mkdir()
    node = node_at(root)
    for name in ("startup-config.cfg", "private-config.cfg"):
        (root / name).write_text(name)
    original = Path.unlink

    def failing_on_the_second(self, *args, **kwargs):
        if self.name == "private-config.cfg":
            raise OSError("disk error")
        return original(self, *args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(Path, "unlink", failing_on_the_second)
        with pytest.raises(ConfigurationError, match="configuration_wipe_failed"):
            wipe_configuration(node, "iou")
    assert not (root / "startup-config.cfg").exists() and (root / "private-config.cfg").exists()
    assert runtime(node)["state"] == "resetting"
    with pytest.raises(ConfigurationError, match="configuration_outcome_unknown"):
        require_launchable(node)

    wipe_configuration(node, "iou")
    mark_wiped(node)
    assert not (root / "private-config.cfg").exists()
    assert runtime(node)["state"] == "clean"
    require_launchable(node)
    assert journal_path(node).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine", ["iou", "dynamips"])
async def test_wipe_is_node_scoped_and_leaves_a_clean_generation(tmp_path, engine, status_queries):
    node = native_node(tmp_path / "target", engine)
    neighbor = native_node(tmp_path / "neighbor", engine, 2)
    neighbor.status = "started"
    keep = Path(neighbor.working_dir) / "neighbor.nvram"
    keep.write_bytes(b"live neighbor state")
    if engine == "iou":
        stale = [Path(node.working_dir) / name for name in ("startup-config.cfg", "nvram_00007", "vlan.dat-00001")]
    else:
        stale = [Path(node.startup_config_path), Path(node.private_config_path)]
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"stale config")
    await ConfigurationService(node, Engine(engine)).wipe()
    assert not any(path.exists() for path in stale)
    assert runtime(node)["state"] == "clean" and runtime(node)["generation"] == 1
    assert keep.read_bytes() == b"live neighbor state"
    assert neighbor.status == "started"
    assert all(node_id == node.id for node_id, _ in status_queries)
    # Starting consumes the clean generation: a later wipe is a new one.
    mark_started(node)
    assert runtime(node)["state"] == "initialized"
    await ConfigurationService(node, Engine(engine)).wipe()
    assert runtime(node)["generation"] == 2


@pytest.mark.asyncio
async def test_dynamips_shared_directory_wipe_does_not_touch_neighbor(tmp_path, status_queries):
    first, second = native_node(tmp_path, "dynamips", 1), native_node(tmp_path, "dynamips", 2)
    first._hypervisor = second._hypervisor = object()
    for node in (first, second):
        for path in (
            Path(node.startup_config_path),
            Path(node.private_config_path),
            tmp_path / f"c7200_i{node.dynamips_id}_nvram",
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"original")
    await ConfigurationService(first, Engine.dynamips).wipe()
    for path in (Path(first.startup_config_path), Path(first.private_config_path), tmp_path / "c7200_i1_nvram"):
        assert not path.exists()
    for path in (Path(second.startup_config_path), Path(second.private_config_path), tmp_path / "c7200_i2_nvram"):
        assert path.read_bytes() == b"original"


@pytest.mark.asyncio
async def test_shutdown_save_and_watcher_close_precede_a_wipe(tmp_path):
    node = native_node(tmp_path, "iou")
    events = []
    node._stop_l1_keepalive_responder = lambda: events.append("l1-stopped")
    node._stop_ubridge = AsyncMock()
    node._nvram_watcher = SimpleNamespace(close=lambda: events.append("watcher-closed"))
    node._telnet_server = None
    node.path = str(tmp_path / "base-iou-image")

    def save():
        events.append("shutdown-save")
        (tmp_path / "startup-config.cfg").write_bytes(b"old shutdown config")

    node.save_configs = save
    await IOUVM.stop(node)
    assert events == ["l1-stopped", "watcher-closed", "shutdown-save"]
    node._nvram_watcher = None
    node.application_id = 1
    await ConfigurationService(node, Engine.iou).wipe()
    assert not (tmp_path / "startup-config.cfg").exists()
