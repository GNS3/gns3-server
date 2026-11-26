"""Arista vEOS: ``startup-config`` written into the flash partition of the node's own disk.

A stock vEOS image (Aboot and one ext4 flash partition on a single disk) has no startup-config on its flash, so it
starts ZeroTouch Provisioning; it reads no config drive. The node's startup entry is therefore written into the
flash partition of a private copy of its disk, offline: the base image is converted to raw, its flash partition
is copied into a file of its own, ``/startup-config`` is written there with ``debugfs`` (no mount, no root), and only
the blocks that changed go into a small qcow2 overlay of the base image. EOS finds its startup-config at the first
boot and keeps the node's own saves across restarts.

The flash is the Linux partition that holds ``boot-config``: the first one, or the second behind the Aboot
partition, as in the stock images. When it is the second, ``zerotouch-config`` is written too (``DISABLE=True``).
"""

import os
import shutil
import struct
from pathlib import Path

from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.safe_io import run_file_io

from ..iso_builder import run_tool
from ..media_profile import BootMediaProfile, cli_text

TARGET = "startup-config"
BLOCK = 64 * 1024
MAX_RANGES = 512  # More changed ranges than this: copy the whole edited disk instead.
MIN_FLASH_BYTES = 1024 * 1024
# Each external tool (converting a multi-GB image, e2fsck) may take longer than the 60 s of a media build; stay below
# the profile's ``stage_seconds``.
TOOL_SECONDS = 150
QCOW2_MAGIC = b"QFI\xfb"
ZEROTOUCH = "zerotouch-config"
ZEROTOUCH_OFF = b"DISABLE=True\n"


def render(content, context):
    text = cli_text(content)
    return {TARGET: (text if text.endswith("\n") else text + "\n").encode("utf-8")}


async def tool(arguments, workdir, **options):
    await run_tool(arguments, workdir, seconds=TOOL_SECONDS, **options)


def check_flash_disk(node):
    """What the node needs before its disk can be prepared; raises a stable error code otherwise."""
    if shutil.which("debugfs") is None or shutil.which("e2fsck") is None or not hasattr(os, "SEEK_DATA"):
        raise ConfigurationError("boot_media_tool_missing")
    base = Path(node._hda_disk_image)
    # One self-booting disk with the flash partition on it, run as a linked clone (the Aboot ISO with the EOS
    # disk on a second drive keeps its flash elsewhere).
    if not node.linked_clone or node._hdb_disk_image or not base.is_file() or base.suffix.lower() == ".iso":
        raise ConfigurationError("configuration_topology_unsupported")
    # The overlay and the conversion below assume a qcow2 base image, as the stock vEOS-lab images are.
    with base.open("rb") as stream:
        if stream.read(4) != QCOW2_MAGIC:
            raise ConfigurationError("configuration_topology_unsupported")


def linux_partitions(raw):
    """The (index, offset, length) of every ext partition of the raw disk's MBR, in table order."""
    size = raw.stat().st_size
    found = []
    with raw.open("rb") as stream:
        header = stream.read(512)
        if len(header) < 512 or header[510:512] != b"\x55\xaa":
            raise ConfigurationError("configuration_topology_unsupported")
        for index in range(4):
            entry = header[446 + 16 * index : 462 + 16 * index]
            start, sectors = struct.unpack_from("<II", entry, 8)
            offset, length = start * 512, sectors * 512
            if entry[4] != 0x83 or offset < 512 or length < MIN_FLASH_BYTES or offset + length > size:
                continue
            stream.seek(offset + 1024 + 56)
            if stream.read(2) == b"\x53\xef":
                found.append((index, offset, length))
    return found


async def flash_partition(workdir, raw):
    """(index, offset, length) of the partition that holds ``boot-config``; refuse a disk that has none."""
    if "?" in str(raw):
        raise ConfigurationError("boot_media_build_failed")  # debugfs reads "?" as the start of its options.
    for index, offset, length in await run_file_io(linux_partitions, raw):
        probe = workdir / "boot-config-probe"
        probe.unlink(missing_ok=True)
        await debugfs(workdir, f"{raw}?offset={offset}", f"dump /boot-config {probe.name}")
        if probe.is_file():
            return index, offset, length
    raise ConfigurationError("configuration_topology_unsupported")  # Not the flash of an EOS image.


def data_extents(descriptor, start, end):
    """The (position, end) extents holding data between two offsets of a sparse file."""
    position = start
    while position < end:
        try:
            position = os.lseek(descriptor, position, os.SEEK_DATA)
            extent_end = min(os.lseek(descriptor, position, os.SEEK_HOLE), end)
        except OSError:
            return  # No data left.
        if position >= end:
            return
        yield position, extent_end
        position = extent_end


def sparse_copy(source, destination, offset, length):
    """Copy a byte range of a raw disk into a new private file of that size, keeping its holes."""
    with source.open("rb") as origin, destination.open("xb") as target:
        target.truncate(length)
        for position, end in data_extents(origin.fileno(), offset, offset + length):
            origin.seek(position)
            target.seek(position - offset)
            while position < end:
                block = origin.read(min(end - position, 8 * 1024 * 1024))
                if not block:
                    raise ConfigurationError("configuration_image_changed")
                target.write(block)
                position += len(block)


def changed_ranges(original, flash, offset):
    """The (offset, length) ranges of the full disk, merged, where the flash partition file differs from the original."""
    ranges = []
    with original.open("rb") as before, flash.open("rb") as after:
        for position, end in data_extents(after.fileno(), 0, os.fstat(after.fileno()).st_size):
            while position < end:
                length = min(BLOCK, end - position)
                if os.pread(before.fileno(), length, position + offset) != os.pread(after.fileno(), length, position):
                    if ranges and ranges[-1][0] + ranges[-1][1] == position + offset:
                        ranges[-1][1] += length
                    else:
                        ranges.append([position + offset, length])
                position += length
    return ranges


async def debugfs(workdir, disk, request, *, write=False):
    await tool([shutil.which("debugfs"), *(["-w"] if write else []), "-R", request, disk], workdir)


def merge_flash(original, flash, offset):
    """Write the flash partition file back into the raw disk, for a whole-disk conversion."""
    with original.open("r+b") as target, flash.open("rb") as source:
        for position, end in data_extents(source.fileno(), 0, os.fstat(source.fileno()).st_size):
            source.seek(position)
            target.seek(position + offset)
            while position < end:
                block = source.read(min(end - position, 8 * 1024 * 1024))
                target.write(block)
                position += len(block)


async def write_overlay(qemu_img, base, original, flash, offset, destination, workdir):
    """A qcow2 overlay of the base image that holds the edited flash, writing only the blocks that changed."""
    ranges = await run_file_io(changed_ranges, original, flash, offset)
    # From here ``original`` is the edited disk: the whole-disk conversion and the final comparison need it.
    await run_file_io(merge_flash, original, flash, offset)
    # qemu-io sits next to qemu-img; without it the whole edited disk is converted instead.
    qemu_io = shutil.which("qemu-io", path=str(Path(qemu_img).parent)) or shutil.which("qemu-io")
    if not ranges or len(ranges) > MAX_RANGES or qemu_io is None:
        arguments = [
            "convert",
            "-f",
            "raw",
            "-O",
            "qcow2",
            "-B",
            str(base),
            "-F",
            "qcow2",
            str(original),
            str(destination),
        ]
        await tool([qemu_img, *arguments], workdir)
    else:
        await tool([qemu_img, "create", "-q", "-f", "qcow2", "-b", str(base), "-F", "qcow2", str(destination)], workdir)
        commands = []
        with flash.open("rb") as stream:
            for index, (position, length) in enumerate(ranges):
                chunk = workdir / f"range-{index}.bin"
                chunk.write_bytes(os.pread(stream.fileno(), length, position - offset))
                commands += ["-c", f"write -s {chunk} {position} {length}"]
        await tool([qemu_io, "-f", "qcow2", *commands, str(destination)], workdir)
    # Not every qemu-io build exits non-zero for a write that failed: compare the result with the edited disk.
    await tool([qemu_img, "compare", "-f", "raw", "-F", "qcow2", str(original), str(destination)], workdir)


async def flash_disk(node, files, workdir):
    """The node's disk with the entry written as ``/startup-config`` on its flash, as a private qcow2 overlay."""
    check_flash_disk(node)
    base = Path(node._hda_disk_image).absolute()
    qemu_img = node._get_qemu_img()
    original, flash, overlay = workdir / "base.raw", workdir / "flash.img", workdir / "prepared.qcow2"
    try:
        await tool([qemu_img, "convert", "-f", "qcow2", "-O", "raw", str(base), str(original)], workdir)
        index, offset, length = await flash_partition(workdir, original)
        # The partition alone, as its own file: e2fsck and debugfs work on it directly, without an offset.
        await run_file_io(sparse_copy, original, flash, offset, length)
        disk = str(flash)
        # Replay a pending journal of the private copy first, so the guest cannot replay stale metadata over the edit.
        await tool([shutil.which("e2fsck"), "-p", "-f", disk], workdir, success_codes=(0, 1))
        content = files[TARGET]
        (workdir / "startup.cfg").write_bytes(content)
        await debugfs(workdir, disk, f"rm /{TARGET}", write=True)
        await debugfs(workdir, disk, f"write startup.cfg /{TARGET}", write=True)
        await debugfs(workdir, disk, f"dump /{TARGET} readback.cfg")
        if (workdir / "readback.cfg").read_bytes() != content:
            raise ConfigurationError("boot_media_build_failed")
        if index > 0:
            # The flash behind the Aboot partition: ZeroTouch is switched off by its own file as well.
            (workdir / ZEROTOUCH).write_bytes(ZEROTOUCH_OFF)
            await debugfs(workdir, disk, f"rm /{ZEROTOUCH}", write=True)
            await debugfs(workdir, disk, f"write {ZEROTOUCH} /{ZEROTOUCH}", write=True)
            await debugfs(workdir, disk, f"dump /{ZEROTOUCH} zerotouch.readback")
            if (workdir / "zerotouch.readback").read_bytes() != ZEROTOUCH_OFF:
                raise ConfigurationError("boot_media_build_failed")
        await write_overlay(qemu_img, base, original, flash, offset, overlay, workdir)
    except OSError:
        raise ConfigurationError("boot_media_build_failed") from None
    os.chmod(overlay, 0o600)
    return overlay


PROFILE = BootMediaProfile(
    id="arista-veos",
    title="Arista vEOS",
    description="Writes the startup entry as startup-config into the flash of the node's disk before its first boot.",
    device_types=("arista_eos",),
    volume_label="VEOS",
    render=render,
    media="none",
    prepare_disk=flash_disk,
    check_disk=check_flash_disk,
    stage_seconds=180,
)
