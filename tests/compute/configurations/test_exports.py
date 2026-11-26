import asyncio
import base64
import logging
from importlib import resources
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from gns3server.compute.configurations import ConfigurationService, decode_nvram, dynamips_query
from gns3server.compute.docker.iol_docker_vm import IOLDockerVM
from gns3server.compute.iou.utils.iou_export import nvram_export
from gns3server.schemas.configurations import ConsoleCredentials, Engine, ExportFile, ExportOptions, Source
from gns3server.services.configurations.shared.errors import ConfigurationError
from tests.support.configurations import export_node, native_node, write_nvram


@pytest.fixture
def native_hypervisor_fixture(monkeypatch):
    async def query(node, operation):
        if operation == "get_status":
            state = await node.get_status()
            return ["0" if state == "inactive" else "2"]
        startup, private = await node.extract_config()
        startup = (startup or b"").decode("ascii")
        private = (private or b"").decode("ascii")
        return [f"R1 '{startup}' '{private}'"]

    monkeypatch.setattr("gns3server.compute.configurations.dynamips_query", query)


@pytest.mark.asyncio
@pytest.mark.parametrize("engine", (Engine.dynamips, Engine.iou))
async def test_native_collectors_preserve_bytes_and_never_export_the_private_configuration(
    tmp_path, engine, native_hypervisor_fixture
):
    node = export_node(tmp_path)
    path = write_nvram(node)
    before = path.read_bytes()
    captured = await ConfigurationService(node, engine).export(ExportOptions())
    expected = bytes(nvram_export(before)[0]) if engine == Engine.iou else b"hostname R1\r\nend\r\n"
    assert captured.files[0].content == expected
    assert [file.filename for file in captured.files] == ["startup-config.cfg"]
    assert path.read_bytes() == before
    assert not (tmp_path / "startup-config.cfg").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("engine", (Engine.dynamips, Engine.iou))
async def test_started_and_suspended_nodes_are_rejected_without_capture(tmp_path, engine):
    for status in ("started", "suspended"):
        node = export_node(tmp_path, status=status)
        with pytest.raises(ConfigurationError, match="stop_required"):
            await ConfigurationService(node, engine).export(ExportOptions())
        node.extract_config.assert_not_called()


@pytest.mark.asyncio
async def test_dynamips_missing_hypervisor_never_falls_back_to_cached_files(tmp_path):
    node = export_node(tmp_path, _hypervisor=None)
    (tmp_path / "startup-config.cfg").write_bytes(b"stale")
    with pytest.raises(ConfigurationError, match="hypervisor_unavailable"):
        await ConfigurationService(node, Engine.dynamips).export(ExportOptions())


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["R1", "Réseau"])
async def test_dedicated_native_connection_preserves_bytes_without_logging_private_config(tmp_path, caplog, name):
    startup = base64.b64encode(b"hostname R1\r\nend\r\n")
    private = base64.b64encode(b"private-secret-never-log")
    commands = []

    async def respond(reader, writer):
        command = await reader.readline()
        commands.append(command)
        if b"get_status" in command:
            payload = b"100 0\r\n100-OK\r\n"
        else:
            payload = ("100 " + name + " '").encode() + startup + b"' '" + private + b"'\r\n100-OK\r\n"
        for index in range(0, len(payload), 7):
            writer.write(payload[index : index + 7])
            await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    async with server:
        node = export_node(
            tmp_path, name=name, _hypervisor=SimpleNamespace(host="127.0.0.1", port=server.sockets[0].getsockname()[1])
        )
        caplog.set_level(logging.DEBUG)
        result = await ConfigurationService(node, Engine.dynamips).export(ExportOptions())
    assert result.files[0].content == base64.b64decode(startup)
    assert [file.filename for file in result.files] == ["startup-config.cfg"]
    node.extract_config.assert_not_called()
    node.get_status.assert_not_called()
    assert private.decode() not in caplog.text and startup.decode() not in caplog.text
    assert set(commands) == {f'vm get_status "{name}"\n'.encode(), f'vm extract_config "{name}"\n'.encode()}


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", (False, True))
async def test_timeout_or_cancel_closes_only_the_capture_connection(tmp_path, monkeypatch, cancel):
    received, closed = asyncio.Event(), asyncio.Event()

    async def hang(reader, writer):
        try:
            await reader.readline()
            received.set()
            assert await reader.read() == b""
            closed.set()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(hang, "127.0.0.1", 0)
    async with server:
        hypervisor = SimpleNamespace(host="127.0.0.1", port=server.sockets[0].getsockname()[1])
        node = export_node(tmp_path, _hypervisor=hypervisor)
        timeout = asyncio.timeout
        if not cancel:
            monkeypatch.setattr("gns3server.compute.configurations.asyncio.timeout", lambda seconds: timeout(0.05))
        task = asyncio.create_task(dynamips_query(node, "get_status"))
        await asyncio.wait_for(received.wait(), timeout=1)
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
            await task
        await asyncio.wait_for(closed.wait(), timeout=1)
        assert node._hypervisor is hypervisor


@pytest.mark.asyncio
async def test_native_reply_limits_and_operation_allowlist(tmp_path, monkeypatch):
    async def oversized(reader, writer):
        await reader.readline()
        writer.write(b"x" * 2048 + b"\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(oversized, "127.0.0.1", 0)
    async with server:
        node = export_node(
            tmp_path, _hypervisor=SimpleNamespace(host="127.0.0.1", port=server.sockets[0].getsockname()[1])
        )
        monkeypatch.setattr("gns3server.compute.configurations.MAX_FILE_BYTES", 2)
        with pytest.raises(ConfigurationError, match="configuration_too_large"):
            await dynamips_query(node, "extract_config")
        with pytest.raises(ConfigurationError, match="unsupported_hypervisor_operation"):
            await dynamips_query(node, "start")


@pytest.mark.asyncio
async def test_missing_corrupt_and_linked_iou_nvram_fail_without_cache_fallback(tmp_path):
    node = export_node(tmp_path)
    (tmp_path / "startup-config.cfg").write_bytes(b"stale")
    for mode, error in (
        ("missing", "configuration_not_saved"),
        ("corrupt", "invalid_nvram"),
        ("link", "unsafe_configuration_path"),
    ):
        path = tmp_path / "nvram_00042"
        if mode == "corrupt":
            path.write_bytes(b"not nvram")
        elif mode == "link":
            path.unlink()
            path.symlink_to(tmp_path / "startup-config.cfg")
        with pytest.raises(ConfigurationError, match=error):
            await ConfigurationService(node, Engine.iou).export(ExportOptions())


@pytest.mark.asyncio
async def test_iol_docker_uses_application_id_and_native_codec(tmp_path):
    node = MagicMock(spec=IOLDockerVM)
    node.id = str(uuid4())
    node.project.id = str(uuid4())
    node.working_dir = str(tmp_path)
    node.application_id = 772
    node.status = "stopped"
    node._cid = None
    path = write_nvram(node, docker=True)
    before = path.read_bytes()
    result = await ConfigurationService(node, Engine.docker).export(ExportOptions())
    assert result.source == Source.saved_startup
    assert result.files[0].content == bytes(nvram_export(before)[0])
    assert path.read_bytes() == before
    node.is_running.assert_not_called()


@pytest.mark.asyncio
async def test_generic_docker_only_reads_declared_bind_files(tmp_path):
    target = "/etc/frr/frr.conf"
    node = export_node(tmp_path, status="started", extra_configs=[{"target": target, "content": "template default"}])
    actual = tmp_path / "configs/etc/frr/frr.conf"
    actual.parent.mkdir(parents=True)
    actual.write_bytes(b"hostname actual\r\n")
    result = await ConfigurationService(node, Engine.docker).export(ExportOptions(source=Source.saved_files))
    assert result.files[0].content == b"hostname actual\r\n"
    assert result.files[0].filename == target[1:]
    assert result.source == Source.saved_files
    node.is_running.assert_not_called()
    node.extra_volumes = ["/etc/frr"]
    with pytest.raises(ConfigurationError, match="configuration_mount_shadowed"):
        await ConfigurationService(node, Engine.docker).export(ExportOptions(source=Source.saved_files))


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["started", "stopped"])
async def test_generic_linux_docker_exports_existing_saved_network_configuration(tmp_path, status):
    node = export_node(tmp_path, status=status)
    saved = tmp_path / "etc/network/interfaces"
    saved.parent.mkdir(parents=True)
    content = b"auto eth0\niface eth0 inet static\n address 192.0.2.1/24\n"
    saved.write_bytes(content)
    before = set(tmp_path.rglob("*"))
    result = await ConfigurationService(node, Engine.docker).export()
    assert result.source == Source.saved_files
    assert result.files == (ExportFile(filename="etc/network/interfaces", content=content),)
    assert saved.read_bytes() == content
    assert set(tmp_path.rglob("*")) == before
    node.is_running.assert_not_called()


@pytest.mark.asyncio
async def test_docker_network_export_never_synthesizes_defaults_or_reads_linked_files(tmp_path):
    node = export_node(tmp_path)
    with pytest.raises(ConfigurationError, match="configuration_not_saved"):
        await ConfigurationService(node, Engine.docker).export()
    assert not (tmp_path / "etc").exists()
    saved = tmp_path / "etc/network/interfaces"
    saved.parent.mkdir(parents=True)
    (tmp_path / "unrelated").write_bytes(b"not a network configuration")
    saved.symlink_to(tmp_path / "unrelated")
    with pytest.raises(ConfigurationError, match="unsafe_configuration_path"):
        await ConfigurationService(node, Engine.docker).export()


@pytest.mark.asyncio
async def test_qemu_requires_device_type_and_never_exports_config_disk(tmp_path):
    node = export_node(tmp_path)
    node._export_config = AsyncMock()
    (tmp_path / "config.zip").write_bytes(b"stale disk data")
    runner = ConfigurationService(node, Engine.qemu)
    with pytest.raises(ConfigurationError, match="device_type_required"):
        await runner.export(ExportOptions(source=Source.running))
    node._export_config.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("driver", ["cisco_ios_telnet", "cisco_nxos", "cisco_asa", "cisco_xr"])
async def test_qemu_export_uses_shared_console_reader(tmp_path, monkeypatch, driver):
    node = export_node(tmp_path, status="started")
    reader = AsyncMock(return_value=b"version 15.9\nhostname live\nend\n")
    monkeypatch.setattr("gns3server.compute.configurations.run_console_session", reader)
    options = ExportOptions(device_type=driver)
    result = await ConfigurationService(node, Engine.qemu).export(options)
    assert result.source == Source.running
    assert result.files[0].filename == "running-config.cfg"
    assert result.files[0].content == reader.return_value
    reader.assert_awaited_once_with(node, ConsoleCredentials(), device_type=driver)


def test_export_options_canonicalize_a_console_driver_alias():
    assert ExportOptions(device_type="cisco_ios").device_type == "cisco_ios_telnet"


@pytest.mark.parametrize("driver", ["linux", "cisco_ios;reload", "", {"command": "reload"}])
def test_unknown_console_drivers_are_rejected(driver):
    with pytest.raises(ValueError):
        ExportOptions(device_type=driver)


@pytest.mark.parametrize("name", ["../file", "/etc/file", "etc/../../file", "a\\b", "file\r\ninjection"])
def test_export_filenames_cannot_escape_a_download_archive(name):
    with pytest.raises(ValueError):
        ExportFile(filename=name, content=b"configuration")


def test_existing_iou_nvram_fixture_preserves_legacy_reader_bytes():
    data = resources.files("tests").joinpath("resources/nvram_iou").read_bytes()
    result = decode_nvram(data)
    assert result == nvram_export(data)
    assert len(result[0]) == 1392 and len(result[1]) == 0


@pytest.mark.asyncio
async def test_vpcs_export_before_the_startup_script_is_written_is_not_saved_yet(tmp_path):
    # VPCS writes startup.vpc asynchronously after `save`.
    node = export_node(tmp_path)
    with pytest.raises(ConfigurationError, match="configuration_not_saved"):
        await ConfigurationService(node, Engine.vpcs).export(ExportOptions())
    (tmp_path / "startup.vpc").write_bytes(b"ip 10.0.0.1/24\n")
    result = await ConfigurationService(node, Engine.vpcs).export(ExportOptions())
    assert result.files[0].content == b"ip 10.0.0.1/24\n"


@pytest.mark.asyncio
async def test_iou_export_preserves_control_characters_and_leaves_the_private_configuration_in_nvram(tmp_path):
    node = native_node(tmp_path, "iou")
    node.application_id = 42
    write_nvram(node, startup=b"hostname Binary\nbanner motd \x03hello\x03\nend\n", private=b"private-secret\r\n")
    result = await ConfigurationService(node, Engine.iou).export(ExportOptions())
    assert [file.filename for file in result.files] == ["startup-config.cfg"]
    assert result.files[0].content.startswith(b"hostname Binary\nbanner motd \x03hello\x03\nend\n")
    assert b"private-secret" not in result.files[0].content
    assert decode_nvram((tmp_path / "nvram_00042").read_bytes())[1] == b"private-secret\r\n"
