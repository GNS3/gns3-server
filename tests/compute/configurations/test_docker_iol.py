"""Docker IOL contracts with real NVRAM codecs and an isolated daemon model."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from gns3server.compute.configurations import ConfigurationService, decode_nvram
from gns3server.compute.docker.docker_error import DockerError
from gns3server.compute.docker.iol_wipe import DockerIOLWipe
from gns3server.compute.iou.utils.iou_import import nvram_import
from gns3server.schemas.configurations import ApplyOptions, Engine
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.node_lease import node_lease
from gns3server.services.configurations.shared.safe_io import write_json
from gns3server.services.configurations.shared.startup_journal import journal_path, mark_started, runtime


@pytest.mark.asyncio
async def test_reset_recreates_only_the_writable_layer_and_owned_runtime_files(iol):
    wipe = DockerIOLWipe(iol)
    root = Path(iol.working_dir)
    original_id = iol.application_id
    for filename in ("nvram_00700", "nvram_00699", "vlan.dat", "vlan.dat-00700"):
        (root / "tmp/run" / filename).write_bytes(b"stale")
    keep = root / "tmp/run/unrelated-data"
    keep.write_bytes(b"application data")
    (root / "tmp/run/vlan.database-notes").write_bytes(b"unrelated")
    (root / "tmp/run/nvram_readme").write_bytes(b"unrelated")
    config = root / "config/iol-config.json"
    config.write_bytes(b"runner configuration")
    iol.startup_config_content = "hostname StaleTemplate\n"
    await wipe.reset_runtime()
    iol.manager.query.assert_awaited_once_with("DELETE", "containers/e90e34656842", params={"force": 0, "v": 0})
    assert runtime(iol)["state"] == "clean" and runtime(iol)["generation"] == 1
    assert not Path(iol._iol_nvram_file()).exists()
    assert not (root / "tmp/run/nvram_00699").exists()
    assert not (root / "tmp/run/vlan.dat").exists()
    assert not (root / "tmp/run/vlan.dat-00700").exists()
    assert (root / "tmp/run/vlan.database-notes").read_bytes() == b"unrelated"
    assert (root / "tmp/run/nvram_readme").read_bytes() == b"unrelated"
    assert keep.read_bytes() == b"application data"
    assert config.read_bytes() == b"runner configuration"
    assert iol.application_id == original_id
    assert iol._startup_config_content is None and not iol._startup_config_dirty
    assert iol._startup_restore_image is None
    mark_started(iol)
    iol.create.assert_awaited_once()
    assert runtime(iol)["state"] == "initialized"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["running", "daemon", "image", "external", "extra_config"],
)
async def test_unsafe_preflight_never_removes_container_or_configuration(iol, failure):
    original = Path(iol._iol_nvram_file())
    original.write_bytes(b"original")
    if failure == "running":
        iol._test_info["State"]["Running"] = True
    elif failure == "daemon":
        iol.manager.http_query.side_effect = DockerError("sensitive daemon details")
    elif failure == "image":
        iol._get_image_information.return_value["Id"] = "sha256:" + "b" * 64
    elif failure == "external":
        iol._test_info["Mounts"].append({"Type": "volume", "Name": "external", "Destination": "/data", "RW": True})
    elif failure == "extra_config":
        iol.extra_configs = [{"target": "/tmp/run/startup-config", "content": "stale"}]
    with pytest.raises(ConfigurationError):
        await DockerIOLWipe(iol).reset_runtime()
    assert original.read_bytes() == b"original"
    assert not journal_path(iol).exists()
    iol.manager.query.assert_not_awaited()
    iol.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_recreation_blocks_start_until_a_new_wipe_completes(iol):
    iol.create.side_effect = DockerError("private failure details")
    with pytest.raises(ConfigurationError, match="configuration_operation_failed"):
        await DockerIOLWipe(iol).reset_runtime()
    assert runtime(iol)["state"] == "resetting"
    with pytest.raises(ConfigurationError, match="configuration_outcome_unknown"):
        await iol._prepare_iol_runtime()
    iol.create.assert_awaited_once()
    iol.create.side_effect = None
    await DockerIOLWipe(iol).reset_runtime()
    assert runtime(iol)["state"] == "clean"


@pytest.mark.asyncio
@pytest.mark.parametrize("failed", ["delete", "create"])
async def test_a_new_wipe_finishes_an_interrupted_reset(iol, failed):
    """A failed or unanswered reset must not leave the node unstartable and unwipeable."""
    stale = Path(iol._iol_nvram_file())
    stale.write_bytes(b"stale")
    call = iol.manager.query if failed == "delete" else iol.create
    call.side_effect = DockerError("lost reply")
    with pytest.raises(ConfigurationError, match="configuration_operation_failed"):
        await ConfigurationService(iol, Engine.docker).wipe()
    assert runtime(iol)["state"] == "resetting"
    call.side_effect = None
    await ConfigurationService(iol, Engine.docker).wipe()
    assert runtime(iol)["state"] == "clean"
    assert not stale.exists()


@pytest.mark.asyncio
async def test_plain_preparation_of_an_owned_runtime_preserves_saved_nvram(iol, monkeypatch):
    saved = bytes(nvram_import(None, b"hostname Saved\n", b"private\n", 256))
    path = Path(iol._iol_nvram_file())
    path.write_bytes(saved)
    iol.startup_config_content = "hostname Stale\n"
    # A runtime that has already booted owns its NVRAM.
    write_json(journal_path(iol), {"version": 1, "generation": 0, "state": "initialized"})
    monkeypatch.setattr(iol, "_get_container_state", AsyncMock(return_value="exited"))
    await iol._prepare_iol_runtime()
    assert path.read_bytes() == saved
    assert not iol._startup_config_dirty
    iol.name = "Renamed"
    startup, private = decode_nvram(path.read_bytes())
    assert b"hostname Renamed" in startup and private == b"private\n"


@pytest.mark.asyncio
async def test_a_prepared_set_stays_pending_until_the_launch_takes_it(iol, monkeypatch):
    """A compute restart before the launch loses the in-memory text: the next Start has to prepare it again."""
    write_json(journal_path(iol), {"version": 1, "generation": 1, "state": "clean"})
    service = ConfigurationService(iol, Engine.docker)
    options = ApplyOptions(device_type="cisco_ios_telnet", content="hostname Set\n")
    await service.apply(options)
    assert runtime(iol)["state"] == "prepared"
    iol._startup_config_content, iol._startup_config_dirty = None, False
    await service.apply(options)
    monkeypatch.setattr(iol, "_get_container_state", AsyncMock(return_value="exited"))
    await iol._prepare_iol_runtime()
    assert b"hostname Set" in decode_nvram(Path(iol._iol_nvram_file()).read_bytes())[0]
    mark_started(iol)
    assert runtime(iol)["state"] == "initialized"


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["clean", "initialized"])
async def test_a_failed_direct_import_leaves_the_journal_alone(iol, monkeypatch, state):
    write_json(journal_path(iol), {"version": 1, "generation": 1, "state": state})

    def fail(self, content):
        raise OSError("disk full")

    monkeypatch.setattr(type(iol), "startup_config_content", property(lambda self: None, fail))
    with pytest.raises(OSError):
        await ConfigurationService(iol, Engine.docker).import_native({"startup_config_content": "hostname New\n"})
    assert runtime(iol)["state"] == state


@pytest.mark.asyncio
async def test_legacy_import_explicitly_reenables_one_time_startup(iol, monkeypatch):
    path = Path(iol._iol_nvram_file())
    path.write_bytes(bytes(nvram_import(None, b"hostname Saved\n", b"private\n", 256)))
    write_json(journal_path(iol), {"version": 1, "generation": 0, "state": "initialized"})
    await ConfigurationService(iol, Engine.docker).import_native({"startup_config_content": "hostname Imported\n"})
    monkeypatch.setattr(iol, "_get_container_state", AsyncMock(return_value="exited"))
    await iol._prepare_iol_runtime()
    startup, private = decode_nvram(path.read_bytes())
    assert b"hostname Imported" in startup and private == b"private\n"


@pytest.mark.asyncio
async def test_iol_start_waits_for_restore_lease_before_runtime_preparation(iol, monkeypatch):
    prepare = AsyncMock(side_effect=DockerError("stop before real Docker start"))
    monkeypatch.setattr(iol, "_prepare_iol_runtime", prepare)
    entered = asyncio.Event()

    async def start():
        entered.set()
        with pytest.raises(DockerError):
            await iol.start()

    async with node_lease(iol):
        # Start from a fresh context, as a separate API request would.
        import contextvars

        task = asyncio.create_task(start(), context=contextvars.Context())
        await entered.wait()
        prepare.assert_not_awaited()
    await task
    prepare.assert_awaited_once()


@pytest.mark.asyncio
async def test_ordinary_wipe_of_supported_iol_uses_native_reset(iol):
    root = Path(iol.working_dir)
    (root / "tmp/run/nvram_00700").write_bytes(b"old state")
    await ConfigurationService(iol, Engine.docker).wipe()
    assert runtime(iol)["state"] == "clean"
    assert not (root / "tmp/run/nvram_00700").exists()


@pytest.mark.parametrize("nvram", [b"", bytes(1024)])
def test_a_startup_config_is_written_over_an_nvram_that_holds_none(iol, nvram):
    path = Path(iol._iol_nvram_file())
    path.write_bytes(nvram)
    iol.startup_config_content = "hostname New\n"
    iol._apply_pending_startup_config()
    assert b"hostname New" in decode_nvram(path.read_bytes())[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("materialized", [False, True], ids=["before_launch", "after_failed_launch"])
async def test_withdrawing_a_docker_iol_set_clears_pending_config_and_nvram(iol, monkeypatch, materialized):
    write_json(journal_path(iol), {"version": 1, "generation": 1, "state": "clean"})
    service = ConfigurationService(iol, Engine.docker)
    await service.apply(ApplyOptions(device_type="cisco_ios_telnet", content="hostname Prepared\n"))
    nvram = Path(iol._iol_nvram_file())
    if materialized:
        monkeypatch.setattr(iol, "_get_container_state", AsyncMock(return_value="exited"))
        await iol._prepare_iol_runtime()
        assert nvram.exists()

    await service.withdraw()

    assert iol._startup_config_content is None and not iol._startup_config_dirty
    assert not nvram.exists()
    assert runtime(iol)["state"] == "clean"


@pytest.mark.asyncio
async def test_a_direct_import_after_a_preparation_is_kept(iol):
    write_json(journal_path(iol), {"version": 1, "generation": 1, "state": "clean"})
    service = ConfigurationService(iol, Engine.docker)
    await service.apply(ApplyOptions(device_type="cisco_ios_telnet", content="hostname Prepared\n"))
    await service.import_native({"startup_config_content": "hostname Imported\n"})
    await service.withdraw()
    assert iol.startup_config_content == "hostname Imported\n" and iol._startup_config_dirty
