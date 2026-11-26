"""ISO building: real tool when available, argument lists and failure modes otherwise."""

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from gns3server.services.configurations.boot_media import iso_builder as iso
from gns3server.services.configurations.shared.errors import ConfigurationError

FILES = {"iosxe_config.txt": b"hostname R1\n ip address 1.2.3.4\n", "meta-data": b"instance-id: x\n"}
XORRISO = shutil.which("xorriso")
needs_mastering_tool = pytest.mark.skipif(not any(shutil.which(name) for name in iso.TOOLS), reason="no mastering tool")


@pytest.mark.skipif(iso.TOOLS and not any(shutil.which(name) for name in iso.TOOLS), reason="no mastering tool")
@pytest.mark.skipif(XORRISO is None, reason="xorriso is needed to read the image back")
@pytest.mark.asyncio
async def test_the_image_holds_the_files_and_the_volume_label(tmp_path):
    image = await iso.build_iso(FILES, "GNS3_BOOT")
    assert image[0x8001:0x8006] == b"CD001"  # ISO 9660 volume descriptor identifier.
    target = tmp_path / "media.iso"
    target.write_bytes(image)
    out = tmp_path / "out"
    listing = await asyncio.to_thread(
        subprocess.run,
        [XORRISO, "-osirrox", "on", "-indev", str(target), "-extract", "/", str(out), "-toc"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "GNS3_BOOT" in listing.stdout + listing.stderr
    assert {path.name: path.read_bytes() for path in Path(out).iterdir()} == FILES


@needs_mastering_tool
@pytest.mark.asyncio
async def test_the_same_files_always_give_the_same_image():
    assert await iso.build_iso(FILES, "cidata") == await iso.build_iso(dict(reversed(FILES.items())), "cidata")


def test_the_first_available_tool_is_used(monkeypatch):
    monkeypatch.setattr(iso.shutil, "which", lambda name: f"/usr/bin/{name}" if name != "xorrisofs" else None)
    assert iso.find_tool() == "/usr/bin/genisoimage"
    monkeypatch.setattr(iso.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "mkisofs" else None)
    assert iso.find_tool() == "/usr/bin/mkisofs"


def test_a_missing_tool_has_its_own_error_code(monkeypatch):
    monkeypatch.setattr(iso.shutil, "which", lambda name: None)
    with pytest.raises(ConfigurationError, match="boot_media_tool_missing"):
        iso.find_tool()


@pytest.mark.asyncio
async def test_building_without_a_tool_fails_before_touching_anything(monkeypatch):
    monkeypatch.setattr(iso.shutil, "which", lambda name: None)
    with pytest.raises(ConfigurationError, match="boot_media_tool_missing"):
        await iso.build_iso(FILES, "cidata")


@pytest.mark.asyncio
async def test_input_over_the_limit_is_refused(monkeypatch):
    monkeypatch.setattr(iso, "MAX_INPUT_BYTES", 10)
    with pytest.raises(ConfigurationError, match="boot_media_too_large"):
        await iso.build_iso({"a": b"x" * 11}, "cidata")


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["false", "true"], ids=["fails", "writes_nothing"])
async def test_a_tool_that_fails_or_writes_nothing_is_a_build_failure(monkeypatch, tool):
    monkeypatch.setattr(iso, "find_tool", lambda: shutil.which(tool))
    with pytest.raises(ConfigurationError, match="boot_media_build_failed"):
        await iso.build_iso(FILES, "cidata")


@pytest.mark.asyncio
async def test_a_hanging_tool_is_stopped_at_the_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(iso, "BUILD_SECONDS", 0.2)
    with pytest.raises(ConfigurationError, match="boot_media_build_failed"):
        await iso.run_tool([shutil.which("sleep"), "30"], tmp_path)


@needs_mastering_tool
@pytest.mark.skipif(XORRISO is None, reason="xorriso is needed to read the image back")
@pytest.mark.asyncio
async def test_nested_files_and_empty_directories_are_built(tmp_path):
    files = {"config/bootstrap.xml": b"<config/>\n", "config/init-cfg.txt": b"type=dhcp-client\n", "license/": b""}
    target = tmp_path / "media.iso"
    target.write_bytes(await iso.build_iso(files, "bootstrap"))
    out = tmp_path / "out"
    await asyncio.to_thread(
        subprocess.run,
        [XORRISO, "-osirrox", "on", "-indev", str(target), "-extract", "/", str(out)],
        capture_output=True,
        check=True,
    )
    assert (out / "config" / "bootstrap.xml").read_bytes() == b"<config/>\n"
    assert (out / "license").is_dir() and not any((out / "license").iterdir())
    assert await iso.build_iso(files, "bootstrap") == await iso.build_iso(dict(reversed(files.items())), "bootstrap")


@pytest.mark.asyncio
async def test_a_tool_gets_its_own_time_limit_when_the_caller_asks_for_one(monkeypatch, tmp_path):
    monkeypatch.setattr(iso, "BUILD_SECONDS", 0.1)
    sleep = shutil.which("sleep")
    with pytest.raises(ConfigurationError, match="boot_media_build_failed"):
        await iso.run_tool([sleep, "2"], tmp_path)  # The module default applies.
    await iso.run_tool([sleep, "0.4"], tmp_path, seconds=5)  # A longer limit lets a slow tool finish.
    with pytest.raises(ConfigurationError, match="boot_media_build_failed"):
        await iso.run_tool([sleep, "2"], tmp_path, seconds=0.1)
