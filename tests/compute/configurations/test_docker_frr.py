"""FRRouting containers: ``/etc/frr/frr.conf`` in the node's persisted volume is the startup configuration."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from gns3server.compute.configurations import ConfigurationService, wipe_configuration
from gns3server.controller.configurations import startup_delivery
from gns3server.schemas.configurations import ApplyOptions, Engine, ExportOptions, Source, compatible_device_type
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.utils.docker_node_type import is_frr_node

STAGED = "etc/frr/.gns3-startup.conf"
CONFIG = "etc/frr/frr.conf"
RUNNING = b"Building configuration...\n\nCurrent configuration:\n!\nfrr version 10.4\nhostname r1\n!\nend\n"


def frr_node(root: Path, **fields):
    (root / "etc/frr").mkdir(parents=True, exist_ok=True)
    (root / "etc/network").mkdir(parents=True, exist_ok=True)
    values = {
        "id": str(uuid4()),
        "project": SimpleNamespace(id=str(uuid4())),
        "working_dir": str(root),
        "status": "stopped",
        "console_type": "telnet",
        "environment": "FRR_PROFILE=full,\nTERM=xterm",
        "_image": "gns3/frr:latest",
        "_volumes": ["/etc/network", "/etc/frr", "/var/lib/frr"],
        "_gns3_init": True,
        "_cid": "abc123",
        "extra_configs": [],
        "netmiko_device_type": None,
    }
    return SimpleNamespace(**{**values, **fields})


@pytest.mark.parametrize(
    "image,environment,expected",
    [
        ("gns3/frr:latest", "", True),
        ("quay.io/frrouting/frr:10.4.5", None, True),
        ("registry.local:5000/lab/frr@sha256:" + "a" * 64, "", True),
        ("my-router:1", "FRR_PROFILE=lite,", True),
        ("alpine:latest", "TERM=xterm", False),
        ("frrouting/frr-exporter:1", "", False),
        (None, None, False),
    ],
)
def test_frr_containers_are_recognized_by_image_or_profile(image, environment, expected):
    assert is_frr_node("telnet", environment, image) is expected


@pytest.mark.parametrize("console_type,environment", [("docker_exec", ""), ("telnet", "GNS3_UNIX_SOCKET_NIO=1")])
def test_vendor_containers_are_never_treated_as_frr(console_type, environment):
    assert not is_frr_node(console_type, environment, "gns3/frr:latest")


@pytest.mark.parametrize(
    "netmiko,driver", [(None, "frr"), ("", "frr"), ("linux", "linux_interfaces"), ("arista_eos", "arista_eos")]
)
def test_the_controller_starts_an_frr_node_from_its_file_unless_a_device_type_says_otherwise(netmiko, driver):
    node = SimpleNamespace(
        node_type="docker",
        netmiko_device_type=netmiko,
        console_type="telnet",
        properties={"image": "gns3/frr:latest", "environment": ""},
    )
    delivery = startup_delivery(node)
    assert delivery.driver == driver
    assert delivery.method == ("native" if driver in ("frr", "linux_interfaces") else "console")
    assert not delivery.native_engine
    assert compatible_device_type("docker", "frr") and not compatible_device_type("qemu", "frr")


@pytest.mark.asyncio
async def test_a_startup_configuration_is_staged_for_the_container_to_install(tmp_path):
    node = frr_node(tmp_path)
    (tmp_path / CONFIG).write_text("hostname saved-by-the-guest\n")
    await ConfigurationService(node, Engine.docker).apply(ApplyOptions(device_type="frr", content="hostname r1\n"))
    assert (tmp_path / STAGED).read_text() == "hostname r1\n"
    # The container installs it itself, after the volume has been seeded from the image.
    assert (tmp_path / CONFIG).read_text() == "hostname saved-by-the-guest\n"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields,code",
    [
        ({"_volumes": ["/etc/network"]}, "configuration_frr_volume_required"),
        ({"status": "started"}, "stop_required"),
        ({"_image": "alpine", "environment": ""}, "configuration_apply_unsupported"),
    ],
)
async def test_a_node_that_cannot_take_the_file_is_refused(tmp_path, fields, code):
    node = frr_node(tmp_path, **fields)
    with pytest.raises(ConfigurationError, match=code):
        await ConfigurationService(node, Engine.docker).apply(ApplyOptions(device_type="frr", content="hostname r\n"))
    assert not (tmp_path / STAGED).exists()


@pytest.mark.asyncio
async def test_a_stopped_node_exports_its_saved_file(tmp_path):
    node = frr_node(tmp_path)
    (tmp_path / CONFIG).write_text("hostname saved\n")
    result = await ConfigurationService(node, Engine.docker).export(ExportOptions())
    assert result.source == Source.saved_files
    assert [(item.filename, item.content) for item in result.files] == [(CONFIG, b"hostname saved\n")]


def vtysh(monkeypatch, output=RUNNING, returncode=0):
    process = MagicMock(returncode=returncode)
    process.stdout.read = AsyncMock(side_effect=[output, b""] if output else [b""])
    process.wait = AsyncMock(return_value=returncode)
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    return spawn


@pytest.mark.asyncio
async def test_a_running_node_exports_its_running_configuration_without_saving_it(tmp_path, monkeypatch):
    spawn = vtysh(monkeypatch)
    node = frr_node(tmp_path, status="started")
    (tmp_path / CONFIG).write_text("hostname old\n")
    result = await ConfigurationService(node, Engine.docker).export(ExportOptions())
    assert result.files[0].content == b"!\nfrr version 10.4\nhostname r1\n!\nend\n"
    assert spawn.await_args.args == ("docker", "exec", "abc123", "vtysh", "-c", "show running-config")
    assert (tmp_path / CONFIG).read_text() == "hostname old\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("output,returncode", [(b"", 1), (b"% failed to connect to any daemons.\n", 0)])
async def test_an_frr_that_is_not_ready_is_not_captured(tmp_path, monkeypatch, output, returncode):
    vtysh(monkeypatch, output, returncode)
    node = frr_node(tmp_path, status="started")
    with pytest.raises(ConfigurationError, match="console_not_ready"):
        await ConfigurationService(node, Engine.docker).export(ExportOptions())


def test_wipe_resets_the_frr_and_network_files_only(tmp_path):
    node = frr_node(tmp_path)
    removed = [CONFIG, STAGED, "etc/frr/frr.conf.sav", "etc/network/interfaces"]
    kept = ["etc/frr/daemons", "etc/frr/vtysh.conf", "etc/frr/.gns3_perms"]
    for name in (*removed, *kept):
        (tmp_path / name).write_text("data")
    wipe_configuration(node, "docker")
    assert not any((tmp_path / name).exists() for name in removed)
    assert all((tmp_path / name).exists() for name in kept)
