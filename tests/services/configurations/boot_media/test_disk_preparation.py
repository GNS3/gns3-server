"""Boot media profiles that change the node's own disk before it boots (``prepare_disk``).

vEOS writes the startup configuration into the flash filesystem; ASAv erases the saved startup through a
temporary guest. Profiles that only produce media files are covered by ``test_profiles.py``.
"""

import asyncio
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from gns3server.services.configurations.boot_media.media_profile import MediaContext
from gns3server.services.configurations.boot_media.profiles import arista_veos as veos
from gns3server.services.configurations.boot_media.profiles import cisco_asav as asav
from gns3server.services.configurations.shared.errors import ConfigurationError

# ----------------------------------------------------------------------------
# vEOS: the flash of a small synthetic image (an MBR and ext4 partitions)
# ----------------------------------------------------------------------------

TOOLS = ("mke2fs", "debugfs", "e2fsck", "qemu-img", "qemu-io")
needs_tools = pytest.mark.skipif(
    not all(shutil.which(tool) for tool in TOOLS), reason="e2fsprogs or qemu tools missing"
)
CONFIG = b"hostname EOS1\n!\ninterface Ethernet1\n   description x\n!\nend\n"
MIB = 1024 * 1024
# Partition slots of the synthetic disk: (offset, length) in bytes, one per table entry.
SLOTS = ((1 * MIB, 6 * MIB), (8 * MIB, 7 * MIB))


def run(*arguments):
    return subprocess.run(arguments, capture_output=True, check=True)  # noqa: S603  (a test fixture's own tools)


def debugfs(disk, offset, request, *, write=False):
    return run("debugfs", *(["-w"] if write else []), "-R", request, f"{disk}?offset={offset}").stdout


def make_base(tmp_path, entries, boot_config_in=None):
    """A qcow2 disk. ``entries`` lists the partition type of each table entry (None: empty); ext4 is made on every
    0x83 one and ``boot-config`` goes into the entry ``boot_config_in``. Returns (base, {entry: offset})."""
    raw = tmp_path / "flash.raw"
    with raw.open("wb") as stream:
        stream.truncate(16 * MIB)
    table = b""
    for slot, kind in zip(SLOTS, entries, strict=False):
        table += struct.pack("<B3sB3sII", 0, b"\0\0\0", kind or 0, b"\0\0\0", slot[0] // 512, slot[1] // 512)
    with raw.open("r+b") as stream:
        stream.seek(446)
        stream.write(table.ljust(64, b"\0") + b"\x55\xaa")
    offsets = {}
    for index, kind in enumerate(entries):
        if kind == 0x83:
            offset, length = SLOTS[index]
            run(
                "mke2fs",
                "-q",
                "-F",
                "-t",
                "ext4",
                "-L",
                "eos_flash",
                "-E",
                f"offset={offset}",
                str(raw),
                f"{length // 1024}k",
            )
            offsets[index] = offset
    if boot_config_in is not None:
        (tmp_path / "boot-config").write_bytes(b"SWI=flash:/vEOS-lab.swi\n")
        debugfs(raw, offsets[boot_config_in], f"write {tmp_path / 'boot-config'} /boot-config", write=True)
    base = tmp_path / "base.qcow2"
    run("qemu-img", "convert", "-f", "raw", "-O", "qcow2", str(raw), str(base))
    return base, offsets


def veos_node(base, **fields):
    values = dict(
        _hda_disk_image=str(base), _hdb_disk_image="", linked_clone=True, _get_qemu_img=lambda: shutil.which("qemu-img")
    )
    return SimpleNamespace(**{**values, **fields})


async def prepare(tmp_path, node, content=CONFIG):
    workdir = Path(tempfile.mkdtemp(dir=tmp_path))  # A fresh scratch directory per call, as staging gives.
    return await veos.flash_disk(node, {veos.TARGET: content}, workdir)


def edited_flash(tmp_path, overlay):
    raw = tmp_path / "check.raw"
    run("qemu-img", "convert", "-f", "qcow2", "-O", "raw", str(overlay), str(raw))
    return raw


def listing(raw, offset):
    return debugfs(raw, offset, "ls /").decode()


def test_the_entry_text_is_stored_with_lf_line_endings_and_a_final_newline():
    files = veos.PROFILE.files("hostname EOS1\r\n!\r\nend", MediaContext(node_id="n"))
    assert files == {"startup-config": b"hostname EOS1\n!\nend\n"}
    assert veos.PROFILE.media == "none" and veos.PROFILE.device_types == ("arista_eos",)


@needs_tools
@pytest.mark.asyncio
async def test_the_startup_config_is_written_into_the_flash_of_a_small_overlay(tmp_path):
    base, offsets = make_base(tmp_path, [0x83], boot_config_in=0)
    before = base.read_bytes()
    overlay = await prepare(tmp_path, veos_node(base))
    assert base.read_bytes() == before  # The shared image is never written.
    info = run("qemu-img", "info", "--output=json", str(overlay)).stdout.decode()
    assert str(base) in info and "qcow2" in info
    assert overlay.stat().st_size < 2 * MIB  # Only the changed blocks, not the whole disk.
    raw = edited_flash(tmp_path, overlay)
    assert debugfs(raw, offsets[0], "cat /startup-config") == CONFIG
    assert b"SWI=flash:/vEOS-lab.swi" in debugfs(raw, offsets[0], "cat /boot-config")
    assert oct(overlay.stat().st_mode & 0o777) == "0o600"
    # The flash is the first partition: ZeroTouch is left to the startup-config.
    assert "zerotouch-config" not in listing(raw, offsets[0])


@needs_tools
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entries", "flash"),
    [
        ([0x17, 0x83], 1),  # The stock image: the Aboot partition first, the flash second.
        ([0x83, 0x83], 1),  # An ext partition without boot-config comes first.
    ],
    ids=["aboot-then-flash", "two-ext"],
)
async def test_the_flash_behind_the_first_partition_is_found_and_zerotouch_is_switched_off(tmp_path, entries, flash):
    base, offsets = make_base(tmp_path, entries, boot_config_in=flash)
    overlay = await prepare(tmp_path, veos_node(base))
    raw = edited_flash(tmp_path, overlay)
    assert debugfs(raw, offsets[flash], "cat /startup-config") == CONFIG
    assert debugfs(raw, offsets[flash], "cat /zerotouch-config") == b"DISABLE=True\n"
    assert b"SWI=" in debugfs(raw, offsets[flash], "cat /boot-config")
    if len(offsets) > 1:
        assert "startup-config" not in listing(raw, offsets[0])  # The other partition is left alone.


@needs_tools
@pytest.mark.asyncio
async def test_too_many_changed_ranges_fall_back_to_converting_the_whole_disk(tmp_path, monkeypatch):
    base, offsets = make_base(tmp_path, [0x83], boot_config_in=0)
    before = base.read_bytes()
    monkeypatch.setattr(veos, "MAX_RANGES", 0)
    overlay = await prepare(tmp_path, veos_node(base))
    assert base.read_bytes() == before
    raw = edited_flash(tmp_path, overlay)
    assert debugfs(raw, offsets[0], "cat /startup-config") == CONFIG and b"SWI=" in debugfs(
        raw, offsets[0], "cat /boot-config"
    )


@needs_tools
@pytest.mark.asyncio
async def test_an_existing_startup_config_and_zerotouch_file_are_replaced(tmp_path):
    base, offsets = make_base(tmp_path, [0x17, 0x83], boot_config_in=1)
    raw = tmp_path / "flash.raw"
    (tmp_path / "old").write_bytes(b"hostname OLD\n")
    for name in ("startup-config", "zerotouch-config"):
        debugfs(raw, offsets[1], f"write {tmp_path / 'old'} /{name}", write=True)
    run("qemu-img", "convert", "-f", "raw", "-O", "qcow2", str(raw), str(base))
    check = edited_flash(tmp_path, await prepare(tmp_path, veos_node(base)))
    assert debugfs(check, offsets[1], "cat /startup-config") == CONFIG
    assert debugfs(check, offsets[1], "cat /zerotouch-config") == b"DISABLE=True\n"


@needs_tools
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entries", "boot_config_in"),
    [([0x83], None), ([0x83, 0x83], None), ([0x17, 0x83], None), ([0x82], None), ([0x17], None)],
    ids=["no-boot-config", "two-ext-no-boot-config", "aboot-and-bare-ext", "no-linux", "no-ext"],
)
async def test_a_disk_that_is_not_an_eos_flash_is_refused(tmp_path, entries, boot_config_in):
    base, _ = make_base(tmp_path, entries, boot_config_in=boot_config_in)
    with pytest.raises(ConfigurationError, match="configuration_topology_unsupported"):
        await prepare(tmp_path, veos_node(base))


@needs_tools
@pytest.mark.asyncio
async def test_a_disk_without_a_partition_table_is_refused(tmp_path):
    base = tmp_path / "plain.qcow2"
    run("qemu-img", "create", "-f", "qcow2", str(base), "16M")
    with pytest.raises(ConfigurationError, match="configuration_topology_unsupported"):
        await prepare(tmp_path, veos_node(base))


def test_the_node_must_be_one_linked_self_booting_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name, **kwargs: f"/usr/bin/{name}")
    disk = tmp_path / "vEOS.qcow2"
    disk.write_bytes(b"QFI\xfb" + bytes(60))
    veos.check_flash_disk(veos_node(disk))
    raw = tmp_path / "vEOS.img"
    raw.write_bytes(bytes(64))  # A raw (or other non-qcow2) base image is refused up front.
    with pytest.raises(ConfigurationError, match="configuration_topology_unsupported"):
        veos.check_flash_disk(veos_node(raw))
    for fields in (
        {"linked_clone": False},
        {"_hdb_disk_image": "eos.qcow2"},
        {"_hda_disk_image": str(tmp_path / "x.iso")},
    ):
        with pytest.raises(ConfigurationError, match="configuration_topology_unsupported"):
            veos.check_flash_disk(veos_node(disk, **fields))
    with pytest.raises(ConfigurationError, match="configuration_topology_unsupported"):
        veos.check_flash_disk(veos_node(tmp_path / "missing.qcow2"))


def test_missing_host_tools_have_their_own_error_code(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name, **kwargs: None)
    with pytest.raises(ConfigurationError, match="boot_media_tool_missing"):
        veos.check_flash_disk(veos_node(tmp_path / "x.qcow2"))


@needs_tools
@pytest.mark.asyncio
async def test_a_write_that_does_not_reach_the_flash_is_caught_by_the_read_back(tmp_path, monkeypatch):
    base, _ = make_base(tmp_path, [0x83], boot_config_in=0)
    real = veos.debugfs

    async def skipping_write(workdir, disk, request, *, write=False):
        if request.startswith("write startup.cfg"):
            return  # debugfs "succeeded" without writing the file
        await real(workdir, disk, request, write=write)

    monkeypatch.setattr(veos, "debugfs", skipping_write)
    with pytest.raises(ConfigurationError, match="boot_media_build_failed"):
        await prepare(tmp_path, veos_node(base))


@needs_tools
@pytest.mark.asyncio
async def test_an_overlay_write_that_silently_failed_is_caught_by_the_final_comparison(tmp_path, monkeypatch):
    base, _ = make_base(tmp_path, [0x83], boot_config_in=0)
    real = veos.tool

    async def silent_qemu_io(arguments, workdir, **options):
        if Path(arguments[0]).name == "qemu-io":
            return  # exits 0 without having written anything
        await real(arguments, workdir, **options)

    monkeypatch.setattr(veos, "tool", silent_qemu_io)
    with pytest.raises(ConfigurationError, match="boot_media_build_failed"):
        await prepare(tmp_path, veos_node(base))


@needs_tools
@pytest.mark.asyncio
async def test_a_working_directory_with_a_question_mark_is_refused_not_misread_by_debugfs(tmp_path):
    base, _ = make_base(tmp_path, [0x83], boot_config_in=0)
    workdir = tmp_path / "what?"
    workdir.mkdir()
    with pytest.raises(ConfigurationError, match="boot_media_build_failed"):
        await veos.flash_disk(veos_node(base), {veos.TARGET: CONFIG}, workdir)


def test_every_tool_runs_with_the_time_limit_of_the_hook_not_the_media_build_default():
    assert veos.TOOL_SECONDS > 60 and veos.TOOL_SECONDS < veos.PROFILE.stage_seconds


# ----------------------------------------------------------------------------
# ASAv: recovery erases the saved startup and never saves recovery state
# ----------------------------------------------------------------------------


class RecoveryGuest:
    def __init__(self, mode="new_password", clone_reboot=False):
        self.stdout = asyncio.StreamReader()
        self.stdin = self
        self.mode, self.clone_reboot = mode, clone_reboot
        self.commands = []
        self.state = "menu"
        self.password = None
        self.returncode = None
        self.terminated = False
        self.feed(self.menu())

    @staticmethod
    def menu():
        return (
            b"GNU GRUB\nwith no configuration load\nThe highlighted entry will be booted automatically in 10 seconds."
        )

    def feed(self, data):
        self.stdout.feed_data(data)

    async def drain(self):
        pass

    def write(self, value):
        self.commands.append(value)
        if self.state == "menu":
            assert value == b"\x1b[B"
            self.state = "selected"
            self.feed(b"Selected: bootflash:/asa.bin with no configuration load")
        elif self.state == "selected":
            assert value == b"\r"
            self.feed(b"Booting 'bootflash:/asa.bin with no configuration load'\n")
            if self.clone_reboot:
                self.clone_reboot = False
                self.state = "menu"
                self.feed(b"clone reboot\n" + self.menu())
            else:
                self.state = "enable"
                self.feed(b"\nciscoasa> ")
        elif self.state == "enable":
            assert value == b"enable\r"
            if self.mode == "privileged":
                self.state = "erase"
                self.feed(b"\nciscoasa# ")
            else:
                self.state = "password"
                self.feed(b"Enter  Password: " if self.mode == "new_password" else b"Password: ")
        elif self.state == "password":
            if self.mode == "new_password":
                self.password = value
                self.state = "repeat"
                self.feed(b"\nRepeat Password: ")
            else:
                assert value == b"\r"
                self.state = "erase"
                self.feed(b"\nciscoasa# ")
        elif self.state == "repeat":
            assert value == self.password
            self.state = "erase"
            self.feed(b"\nciscoasa# ")
        elif self.state == "erase":
            assert value == b"write erase\r"
            self.state = "confirm_erase"
            self.feed(b"Erase configuration in flash memory? [confirm]")
        elif self.state == "confirm_erase":
            assert value == b"\r"
            self.state = "reload"
            self.feed(b"\n[OK]\n\nciscoasa# ")
        elif self.state == "reload":
            assert value == b"reload\r"
            self.state = "save"
            self.feed(b"System config has been modified. Save? [Y]es/[N]o: ")
        elif self.state == "save":
            assert value == b"n\r"
            self.state = "confirm_reload"
            self.feed(b"Proceed with reload? [confirm]")
        elif self.state == "confirm_reload":
            assert value == b"\r"
            self.state = "flushed"
            self.feed(b"Shutting down File system\nRebooting\nGNU GRUB")
        else:
            raise AssertionError("Recovery sent an unexpected command after disk flush")

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self.stdout.feed_eof()

    async def wait(self):
        return self.returncode


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["new_password", "empty_password", "privileged"])
@pytest.mark.parametrize("clone_reboot", [False, True])
async def test_native_recovery_erases_and_declines_saving_temporary_configuration(mode, clone_reboot):
    guest = RecoveryGuest(mode, clone_reboot)
    console = asav.RecoveryConsole(guest)
    try:
        await console.erase()
        assert guest.state == "flushed"
        assert guest.commands.count(b"write erase\r") == 1
        assert b"n\r" in guest.commands
        assert b"write memory\r" not in guest.commands
        if guest.password:
            assert len(guest.password.strip()) >= 16
    finally:
        guest.terminate()
        await console.reader


@pytest.mark.asyncio
async def test_recovery_waits_for_complete_menu_before_sending_any_key():
    guest = RecoveryGuest()
    guest.stdout = asyncio.StreamReader()
    guest.feed(b"GNU GRUB\nwith no configuration load")
    console = asav.RecoveryConsole(guest)
    task = asyncio.create_task(console.erase())
    try:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert guest.commands == []
        guest.feed(b"\nThe highlighted entry will be booted automatically in 10 seconds.")
        await task
        assert guest.state == "flushed"
    finally:
        task.cancel()
        guest.terminate()
        await asyncio.gather(task, console.reader, return_exceptions=True)
