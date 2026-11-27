import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from gns3server.compute import configurations as module
from gns3server.compute.configurations import ConfigurationService
from gns3server.schemas.configurations import (
    ApplyOptions,
    Engine,
    ExportOptions,
    Source,
)
from gns3server.services.configurations.shared import preparation
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.startup_journal import mark_started, mark_wiped, runtime
from gns3server.utils.asyncio import loop_limit


@pytest.mark.asyncio
async def test_vpcs_service_round_trip_uses_native_file_without_console(tmp_path, monkeypatch):
    from tests.support.configurations import export_node

    console = AsyncMock()
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", console)
    service = ConfigurationService(export_node(tmp_path), Engine.vpcs)
    content = "set pcname PC1\nip 192.0.2.1/24\n"
    await service.apply(ApplyOptions(device_type="vpcs", content=content))
    result = await service.export()
    assert result.files[0].content == content.encode()
    console.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["console_busy", "console_unavailable", "capture_capacity_exhausted"])
async def test_startup_service_retries_transient_admission_failures(monkeypatch, reason):
    run = AsyncMock(side_effect=[ConfigurationError(reason), b"applied\n", b"hostname R1\n"])
    pause = AsyncMock()
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", run)
    monkeypatch.setattr("gns3server.compute.configurations.wait_for_console_ready", AsyncMock())
    monkeypatch.setattr("gns3server.compute.configurations.asyncio.sleep", pause)
    await ConfigurationService(SimpleNamespace(), Engine.qemu).apply(
        ApplyOptions(device_type="cisco_ios", content="hostname R1\n", wait_ready=True)
    )
    # The rejected admission is retried once and the restored configuration is
    # then read back to confirm the guest kept it.
    assert run.await_count == 3
    pause.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_startup_service_does_not_retry_credentials_or_mutation_failures(monkeypatch):
    run = AsyncMock(side_effect=ConfigurationError("configuration_apply_failed"))
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", run)
    with pytest.raises(ConfigurationError, match="configuration_apply_failed"):
        await ConfigurationService(SimpleNamespace(), Engine.qemu).apply(
            ApplyOptions(device_type="cisco_ios", content="hostname R1\n", wait_ready=True)
        )
    run.assert_awaited_once()


@pytest.mark.asyncio
async def test_iou_selected_configuration_reaches_native_nvram_and_exports(isolated_compute_project, monkeypatch):
    from gns3server.compute.iou import IOU
    from gns3server.compute.iou.iou_vm import IOUVM
    from gns3server.schemas.configurations import ExportOptions

    console = AsyncMock()
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", console)
    image = Path(IOU.instance().get_images_directory()) / "iou.bin"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"image-placeholder")
    node = IOUVM(
        "iou-audit", str(uuid4()), isolated_compute_project, IOU.instance(), application_id=42, path=str(image)
    )
    node.private_config_content = "private-test\n"
    service = ConfigurationService(node, Engine.iou)
    await service.apply(ApplyOptions(device_type="cisco_ios", content="hostname selected-native\nend\n"))
    node._push_configs_to_nvram()  # The engine's actual pre-boot encoder, without launching an image.
    result = await service.export(ExportOptions())
    assert b"hostname selected-native" in result.files[0].content
    assert len(result.files) == 1
    console.assert_not_called()


@pytest.mark.asyncio
async def test_iol_selected_set_reapplies_identical_text_after_guest_saves_changes(
    isolated_compute_project, monkeypatch
):

    from gns3server.compute.docker import Docker
    from gns3server.compute.iou.utils.iou_export import nvram_export
    from gns3server.compute.iou.utils.iou_import import nvram_import
    from tests.support.configurations.fixtures import make_iol_vm

    console = AsyncMock()
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", console)
    node = make_iol_vm(isolated_compute_project, Docker.instance())
    service = ConfigurationService(node, Engine.docker)
    options = ApplyOptions(device_type="cisco_ios", content="hostname selected-set\nend\n")
    await service.apply(options)
    node._apply_pending_startup_config()
    node._startup_config_dirty = False
    nvram = Path(node._iol_nvram_file())
    nvram.write_bytes(nvram_import(None, b"hostname saved-by-guest\nend\n", None, node._IOL_NVRAM_SIZE_KB))
    await service.apply(options)
    assert node._startup_config_dirty is True
    node._apply_pending_startup_config()
    assert b"hostname selected-set" in nvram_export(nvram.read_bytes())[0]
    console.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine", [Engine.iou, Engine.dynamips])
async def test_native_startup_service_refuses_running_nodes_before_writing(engine):
    node = SimpleNamespace(status="started")
    with pytest.raises(ConfigurationError, match="stop_required"):
        await ConfigurationService(node, engine).apply(
            ApplyOptions(device_type="cisco_ios", content="hostname selected\n")
        )
    assert not hasattr(node, "startup_config_content")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "engine,driver", [(Engine.iou, "cisco_asa"), (Engine.vpcs, "cisco_ios"), (Engine.qemu, "vpcs")]
)
async def test_service_rejects_cross_engine_formats_before_touching_runtime(engine, driver):
    with pytest.raises(ConfigurationError, match="configuration_apply_unsupported"):
        await ConfigurationService(SimpleNamespace(), engine).apply(ApplyOptions(device_type=driver, content="test\n"))


@pytest.mark.asyncio
async def test_dynamips_selected_and_direct_node_imports_share_native_writer(isolated_compute_project):
    from gns3server.compute.dynamips import Dynamips
    from gns3server.compute.dynamips.nodes.router import Router

    manager = Dynamips.instance()
    node = Router("native-audit", str(uuid4()), isolated_compute_project, manager)
    service = ConfigurationService(node, Engine.dynamips)
    await manager.set_vm_configs(
        node, {"startup_config_content": "hostname direct\n", "private_config_content": "private-test\n"}
    )
    assert "hostname direct" in Path(node.startup_config_path).read_text()
    await service.apply(ApplyOptions(device_type="cisco_ios", content="hostname selected\nend\n"))
    assert "hostname selected" in Path(node.startup_config_path).read_text()
    assert Path(node.private_config_path).read_text() == "!\nprivate-test\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("engine", [Engine.iou, Engine.dynamips, Engine.qemu])
async def test_live_apply_uses_console_instead_of_native_startup_files(monkeypatch, engine):
    capture = AsyncMock(return_value=b"applied\n")
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", capture)
    node = SimpleNamespace(status="started")
    await ConfigurationService(node, engine).apply(
        ApplyOptions(device_type="cisco_ios", content="hostname live\n", running=True)
    )
    assert capture.await_args.kwargs["content"] == "hostname live\n"
    assert capture.await_args.kwargs["wait_ready"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("driver,engine", [("vpcs", Engine.vpcs), ("linux_interfaces", Engine.docker)])
async def test_live_apply_rejects_non_live_formats(monkeypatch, driver, engine):
    capture = AsyncMock()
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", capture)
    with pytest.raises(ConfigurationError, match="configuration_apply_unsupported"):
        await ConfigurationService(SimpleNamespace(status="started"), engine).apply(
            ApplyOptions(device_type=driver, content="config", running=True)
        )
    capture.assert_not_awaited()


@pytest.mark.asyncio
async def test_viptela_live_and_startup_apply_are_refused_without_console_access(monkeypatch):
    capture = AsyncMock()
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", capture)
    service = ConfigurationService(SimpleNamespace(status="started"), Engine.qemu)
    for options in (
        ApplyOptions(device_type="cisco_viptela", content="system\n host-name live\n!\n", running=True),
        ApplyOptions(device_type="cisco_viptela", content="system\n host-name live\n!\n", wait_ready=True),
    ):
        with pytest.raises(ConfigurationError, match="configuration_apply_unsupported"):
            await service.apply(options)
    capture.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", [Source.save_then_capture, Source.running])
async def test_only_save_then_capture_saves_the_guest_state(tmp_path, monkeypatch, source):
    from tests.support.configurations import export_node

    capture = AsyncMock(return_value=b"hostname R1\n")
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", capture)
    service = ConfigurationService(export_node(tmp_path), Engine.qemu)
    result = await service.export(ExportOptions(source=source, device_type="cisco_ios"))
    assert result.source == source
    if source == Source.save_then_capture:
        assert capture.await_args.kwargs["save"] is True
        assert capture.await_args.kwargs.get("backup", False) is False
    else:
        assert "save" not in capture.await_args.kwargs


@pytest.mark.asyncio
async def test_console_apply_failure_is_logged_with_node_phase_and_masked_command(monkeypatch, caplog):
    from gns3server.services.configurations.shared.errors import ConfigurationError

    context = {
        "phase": "replay",
        "command_index": 12,
        "command_total": 101,
        "command": "aaa user admin password $6$salt$SECRETHASH",
        "device_error": "syntax error: 'SECRETHASH'",
    }
    capture = AsyncMock(side_effect=ConfigurationError("configuration_apply_failed", context=context))
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", capture)
    monkeypatch.setattr("gns3server.compute.configurations.wait_for_console_ready", AsyncMock())
    node = SimpleNamespace(name="vSmart-1", status="started", _process=object())
    service = ConfigurationService(node, Engine.qemu)
    with caplog.at_level("WARNING"), pytest.raises(ConfigurationError, match="configuration_apply_failed"):
        await service.apply(ApplyOptions(device_type="cisco_nxos", content="hostname live\n", wait_ready=True))
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "vSmart-1" in messages
    assert (
        "phase=replay command=12/101 sent='aaa user admin password <masked>' device='syntax error: <masked>'"
        in messages
    )
    assert "SECRETHASH" not in messages


def console_service(**attrs):
    node = SimpleNamespace(name="vsmart", _process=object(), _configuration_console_proxy=object(), status="started")
    node.__dict__.update(attrs)
    return node, ConfigurationService(node, Engine.qemu)


def apply_options(**kw):
    return ApplyOptions(device_type="cisco_ios", content="hostname R1\n", wait_ready=True, **kw)


@pytest.mark.asyncio
async def test_console_busy_retries_are_bounded_by_total_deadline(monkeypatch, caplog):
    node, svc = console_service()
    now = [1000.0]
    calls = []

    async def capture(*args, **kwargs):
        calls.append(1)
        raise ConfigurationError("console_busy")

    async def fake_sleep(seconds):
        now[0] += 100  # each retry "takes" 100 s on the fake clock

    monkeypatch.setattr(module, "clock", lambda: now[0])
    monkeypatch.setattr(module, "run_console_session", capture)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    with caplog.at_level("INFO"):
        with pytest.raises(ConfigurationError) as error:
            await svc._apply_console(apply_options())
    assert error.value.code == "configuration_apply_timeout"
    assert len(calls) == 9  # 900 s budget / 100 s per retry, far below 600 attempts
    assert "waiting (console_busy)" in caplog.text
    assert error.value.context == {"phase": "console-wait", "device_error": "last retry: console_busy"}
    assert "last retry reason: console_busy" in caplog.text


@pytest.mark.asyncio
async def test_a_startup_replay_does_not_wait_for_a_live_apply_slot(monkeypatch):
    session = AsyncMock()
    monkeypatch.setattr(module, "run_console_session", session)
    node = SimpleNamespace(status="started", id="n")
    options = SimpleNamespace(
        wait_ready=True, running=False, credentials=None, device_type="cisco_ios_telnet", content="hostname a\n"
    )
    slots = loop_limit("apply")
    for _ in range(4):
        await slots.acquire()
    try:
        async with asyncio.timeout(2):
            await ConfigurationService(node, Engine.qemu)._apply_console(options)
    finally:
        for _ in range(4):
            slots.release()
    session.assert_awaited_once()


VPCS_PREPARED_CONFIG = ApplyOptions(device_type="vpcs", content="set pcname Prepared\n")


def clean_vpcs_node(root: Path):
    node = SimpleNamespace(id=str(uuid4()), working_dir=str(root), status="stopped")
    mark_wiped(node)
    return node


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", [None, "set pcname Template\n"])
async def test_withdrawing_puts_back_what_the_preparation_replaced(tmp_path, previous):
    node = clean_vpcs_node(tmp_path)
    saved = tmp_path / "startup.vpc"
    if previous:
        saved.write_text(previous)
    service = ConfigurationService(node, Engine.vpcs)
    await service.apply(VPCS_PREPARED_CONFIG)
    # Preparing again must not make the first preparation count as the node's own file.
    await service.apply(ApplyOptions(device_type="vpcs", content="set pcname Again\n"))
    await service.withdraw()
    assert (saved.read_text() if saved.exists() else None) == previous
    assert runtime(node)["state"] == "clean"


@pytest.mark.parametrize("edited_before_rename", [False, True])
def test_a_rename_keeps_a_prepared_file_the_preparations_unless_the_user_changed_it(tmp_path, edited_before_rename):
    """The server rewrites the hostname in the file when the node is renamed."""
    node = clean_vpcs_node(tmp_path)
    saved = tmp_path / "startup-config.cfg"
    before = preparation.snapshot(node, [saved.name])
    saved.write_text("hostname R1\n")
    preparation.record(node, before)
    if edited_before_rename:
        saved.write_text("hostname Mine\n")
    with preparation.keeping_ownership(node):
        saved.write_text("hostname Renamed\n")
    preparation.withdraw(node)
    assert saved.exists() is edited_before_rename


@pytest.mark.asyncio
@pytest.mark.parametrize("what", ["launched", "edited", "wiped"])
async def test_withdrawing_leaves_what_is_no_longer_the_preparation(tmp_path, what):
    node = clean_vpcs_node(tmp_path)
    saved = tmp_path / "startup.vpc"
    saved.write_text("set pcname Template\n")
    service = ConfigurationService(node, Engine.vpcs)
    await service.apply(VPCS_PREPARED_CONFIG)
    if what == "launched":
        mark_started(node)
    elif what == "edited":
        saved.write_text("set pcname Mine\n")
    else:
        mark_wiped(node)
        saved.write_text(VPCS_PREPARED_CONFIG.content)
    expected = saved.read_text()
    await service.withdraw()
    assert saved.read_text() == expected


@pytest.mark.asyncio
async def test_a_dynamips_settings_update_keeps_the_pending_preparation(tmp_path):
    (tmp_path / "configs").mkdir()
    saved = tmp_path / "configs" / "i1_startup-config.cfg"
    node = SimpleNamespace(
        id=str(uuid4()),
        working_dir=str(tmp_path),
        status="stopped",
        dynamips_id=1,
        startup_config_path=str(saved),
        manager=SimpleNamespace(_create_config=lambda node, path, text: Path(path).write_text(text)),
    )
    mark_wiped(node)
    service = ConfigurationService(node, Engine.dynamips)
    await service.apply(ApplyOptions(device_type="cisco_ios_telnet", content="hostname Prepared\n"))
    await service.import_native({"ram": 256, "name": "R1"})
    await service.withdraw()
    assert not saved.exists()


def test_docker_network_restore_is_bounded_to_managed_file_and_stopped_node(tmp_path):
    from gns3server.compute.configurations import restore_network_file

    node = SimpleNamespace(working_dir=str(tmp_path), status="stopped", extra_configs=[])
    content = "auto eth0\niface eth0 inet dhcp\n"
    restore_network_file(node, content)
    target = tmp_path / "etc/network/interfaces"
    assert target.read_text() == content
    assert not list(target.parent.glob(".interfaces-*"))
    node.status = "started"
    with pytest.raises(ConfigurationError, match="stop_required"):
        restore_network_file(node, "replacement")
    assert target.read_text() == content
    node.status = "stopped"
    node._gns3_init = False
    with pytest.raises(ConfigurationError, match="configuration_apply_unsupported"):
        restore_network_file(node, content)
    node._gns3_init = True
    target.unlink()
    outside = tmp_path / "outside"
    outside.write_text("unchanged")
    target.symlink_to(outside)
    with pytest.raises(ConfigurationError):
        restore_network_file(node, content)
    assert outside.read_text() == "unchanged"
