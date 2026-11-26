"""Build a small FAT disk image from in-memory files with mtools.

For guests that read their startup files from a second disk instead of a CD-ROM (Cisco IOSv and
IOSvL2 take ``ios_config.txt`` from a FAT disk). The image is a 1 MiB raw disk with an MBR and one
FAT partition, the same layout as the disk the vendor ships. No guest filesystem is mounted and no
shell is involved: mtools run with a fixed argument list inside a private temporary directory.
"""

import os
import shutil
import struct
import tempfile
from pathlib import Path

from gns3server.services.configurations.shared.errors import ConfigurationError

from .iso_builder import EPOCH, run_tool

SECTOR = 512
DISK_SECTORS = 2048  # 1 MiB
PARTITION_START = 63
PARTITION_SECTORS = 1953
HEADS = 16
SECTORS_PER_TRACK = 63
# What fits next to the FAT structures of the 1 MiB disk (958464 bytes free), with some room left.
MAX_INPUT_BYTES = 900 * 1024
# Fixed volume serial number, so the same files always give the same image.
SERIAL = "47534e33"


def _mbr():
    """Boot sector with one active FAT12 partition at sector 63 (CHS values of a 2 x 16 x 63 disk)."""
    entry = struct.pack("<B3sB3sLL", 0x80, b"\x01\x01\x00", 0x01, b"\x0f\x3f\x01", PARTITION_START, PARTITION_SECTORS)
    return bytes(446) + entry + bytes(48) + b"\x55\xaa"


def _tools():
    tools = {name: shutil.which(name) for name in ("mformat", "mcopy")}
    if not all(tools.values()):
        raise ConfigurationError("boot_media_tool_missing")
    return tools


async def build_disk(files, volume_label):
    """Return the bytes of a FAT disk holding ``files`` ({name: bytes}) in its root directory."""
    if any("/" in name for name in files):
        raise ConfigurationError("boot_media_build_failed")  # A FAT disk of this kind holds a flat set of files.
    if sum(len(data) for data in files.values()) > MAX_INPUT_BYTES:
        raise ConfigurationError("boot_media_too_large")
    tools = _tools()
    with tempfile.TemporaryDirectory(prefix="gns3-boot-media-") as directory:
        root = Path(directory)
        target = root / "media.img"
        target.write_bytes(_mbr() + bytes(DISK_SECTORS * SECTOR - SECTOR))
        partition = f"{target}@@{PARTITION_START * SECTOR}"
        await run_tool(
            [
                tools["mformat"],
                "-i",
                partition,
                "-T",
                str(PARTITION_SECTORS),
                "-h",
                str(HEADS),
                "-s",
                str(SECTORS_PER_TRACK),
                "-N",
                SERIAL,
                "-v",
                volume_label,
                "::",
            ],
            root,
        )
        source = root / "content"
        source.mkdir(mode=0o700)
        copies = []
        for name, data in sorted(files.items()):
            path = source / name
            path.write_bytes(data)
            os.utime(path, (EPOCH, EPOCH))
            copies.append(str(path))
        await run_tool([tools["mcopy"], "-i", partition, "-m", *copies, "::"], root)
        try:
            return target.read_bytes()
        except OSError:
            raise ConfigurationError("boot_media_build_failed") from None
