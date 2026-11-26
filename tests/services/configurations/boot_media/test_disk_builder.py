"""FAT disk building: layout, content, determinism and failure modes."""

import asyncio
import shutil
import subprocess

import pytest

from gns3server.services.configurations.boot_media import disk_builder as disk
from gns3server.services.configurations.shared.errors import ConfigurationError

FILES = {"ios_config.txt": b"hostname R1\n ip address 1.2.3.4\n", "ios_config_checksum": b"abc\n"}
needs_mtools = pytest.mark.skipif(not (shutil.which("mformat") and shutil.which("mcopy")), reason="no mtools")


@needs_mtools
@pytest.mark.skipif(not shutil.which("mlabel"), reason="no mlabel for FAT label readback")
@pytest.mark.asyncio
async def test_the_disk_has_an_mbr_partition_and_holds_the_files(tmp_path):
    image = await disk.build_disk(FILES, "IOSCFG")
    target = tmp_path / "media.img"
    target.write_bytes(image)
    assert len(image) == 1024 * 1024
    # One active FAT12 partition starting at sector 63, like the disk the vendor ships.
    assert image[510:512] == b"\x55\xaa" and image[446] == 0x80 and image[450] == 0x01
    assert int.from_bytes(image[454:458], "little") == 63
    partition = f"{target}@@{63 * 512}"
    mcopy, mlabel = shutil.which("mcopy"), shutil.which("mlabel")

    async def run(*arguments):
        return await asyncio.to_thread(subprocess.run, arguments, capture_output=True, check=True)

    for name, data in FILES.items():
        assert (await run(mcopy, "-i", partition, f"::{name}", "-")).stdout == data
    assert b"IOSCFG" in (await run(mlabel, "-i", partition, "-s", "::")).stdout


@needs_mtools
@pytest.mark.asyncio
async def test_the_same_files_always_give_the_same_disk():
    assert await disk.build_disk(FILES, "IOSCFG") == await disk.build_disk(dict(reversed(FILES.items())), "IOSCFG")


@pytest.mark.asyncio
async def test_input_over_the_limit_is_refused():
    with pytest.raises(ConfigurationError, match="boot_media_too_large"):
        await disk.build_disk({"ios_config.txt": b"x" * (disk.MAX_INPUT_BYTES + 1)}, "IOSCFG")


@pytest.mark.asyncio
async def test_building_without_mtools_fails_before_touching_anything(monkeypatch):
    monkeypatch.setattr(disk.shutil, "which", lambda name: None)
    with pytest.raises(ConfigurationError, match="boot_media_tool_missing"):
        await disk.build_disk(FILES, "IOSCFG")


@pytest.mark.asyncio
async def test_a_flat_disk_refuses_paths_and_directories():
    for files in ({"config/ios_config.txt": b"x"}, {"config/": b""}):
        with pytest.raises(ConfigurationError, match="boot_media_build_failed"):
            await disk.build_disk(files, "IOSCFG")
