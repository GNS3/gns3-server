"""Cisco ASAv: Day-0 ``day0-config`` on an erased copy of the image.

The guest copies ``day0-config`` from the CD-ROM to its startup-config at its first boot, but only
while that startup-config is empty. A distributed image may already hold startup state in an encrypted
store, so the node first boots an erased copy of it: the vendor's recovery boot
(``with no configuration load``) runs in a disposable VM to ``write erase`` on a private overlay of the
image. That erased overlay is cached once per image, for every node, and becomes the node's disk; the
shared base image is only ever a read-only backing file. The guest's boot script finds the CD-ROM only on
the ``pc`` machine type (on ``q35`` the drive is not visible to it), which is also the machine the erase VM
runs on.
"""

import asyncio
import hashlib
import json
import os
import re
import secrets
import shlex
import tempfile
from pathlib import Path

from gns3server.config import Config
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.safe_io import (
    atomic_bytes,
    copy_private_disk,
    safe_directory,
    write_json,
)

from ..media_profile import BootMediaProfile, checked_text, plain_password

CACHE_DIRECTORY = "startup-media-cache"
ERASE_SECONDS = 360  # The recovery VM boots, erases and shuts down inside this budget.
TERMINATE_SECONDS = 10  # Grace before the recovery VM is killed.


def node_identifier(node):
    options = shlex.split(node.options or "")
    return options[options.index("-uuid") + 1] if "-uuid" in options else str(node.id)


def temporary_password():
    while True:
        value = "Q7!mR2@vN9#sL5$p" + secrets.token_hex(8)
        if not any(
            ord(b) - ord(a) == ord(c) - ord(b) in (-1, 0, 1)
            for a, b, c in zip(value, value[1:], value[2:], strict=False)
        ):
            return value.encode()


class RecoveryConsole:
    def __init__(self, process):
        self.process = process
        self.data = bytearray()
        self.changed = asyncio.Event()
        self.phase = "boot_menu"
        self.reader = asyncio.create_task(self.collect())

    async def collect(self):
        while chunk := await self.process.stdout.read(8192):
            self.data.extend(chunk)
            self.changed.set()
            if len(self.data) > 2 * 1024 * 1024:
                raise ConfigurationError("configuration_factory_reset_failed")
        self.changed.set()

    async def send(self, data):
        self.process.stdin.write(data)
        await self.process.stdin.drain()

    async def expect(self, pattern, start=0, seconds=180):
        async with asyncio.timeout(seconds):
            while True:
                self.changed.clear()
                match = re.search(pattern, self.data[start:], re.I)
                if match:
                    return start + match.end(), match.group()
                if self.reader.done():
                    await self.reader
                    raise ConfigurationError("configuration_factory_reset_failed")
                await self.changed.wait()

    async def boot_without_configuration(self):
        position, _ = await self.expect(rb"GNU GRUB")
        # A clone may reboot once after discovering its new VM identity.
        while True:
            self.phase = "boot_menu"
            position, _ = await self.expect(
                rb"The highlighted entry will be booted automatically in \d+ seconds?\.", position, seconds=15
            )
            # GRUB prints the menu entries before its input loop is ready. Do
            # not send Enter together with Down: wait for the selected entry's
            # redraw, then verify the actual boot line before using the CLI.
            await asyncio.sleep(0.1)
            position = len(self.data)
            await self.send(b"\x1b[B")
            position, _ = await self.expect(rb"with no configuration load", position, seconds=5)
            self.phase = "recovery_boot"
            await self.send(b"\r")
            position, boot = await self.expect(rb"Booting ['\"][^\r\n]+['\"]", position, seconds=15)
            if b"with no configuration load" not in boot.lower():
                raise ConfigurationError("configuration_factory_reset_failed")
            self.phase = "recovery_prompt"
            position, match = await self.expect(rb"GNU GRUB|(?:^|[\r\n])ciscoasa>\s*$|Press (?:ENTER|RETURN)", position)
            while b"Press" in match:
                await self.send(b"\r")
                position, match = await self.expect(rb"GNU GRUB|(?:^|[\r\n])ciscoasa>\s*$", position)
            if b"ciscoasa>" in match:
                return position

    async def erase(self):
        position = await self.boot_without_configuration()
        self.phase = "enable_setup"
        await self.send(b"enable\r")
        position, match = await self.expect(rb"(?:Enter\s+Password:|Password:|ciscoasa#)\s*$", position)
        if b"Enter" in match:
            # ASA 9.19 requires setting a temporary enable password even in
            # recovery mode. It is never saved or sent to a connected network.
            password = temporary_password()
            await self.send(password + b"\r")
            position, response = await self.expect(rb"Repeat Password:\s*$|ERROR:[^\r\n]*", position)
            if b"repeat password:" not in response.lower():
                raise ConfigurationError("configuration_factory_reset_failed")
            await self.send(password + b"\r")
        elif b"Password:" in match:
            await self.send(b"\r")  # Empty enable password in older recovery boots.
        if b"ciscoasa#" not in match:
            position, response = await self.expect(
                rb"ciscoasa#\s*$|Invalid password|Access denied|ERROR:[^\r\n]*", position
            )
            if b"ciscoasa#" not in response.lower():
                raise ConfigurationError("configuration_factory_reset_failed")
        self.phase = "erase_confirmation"
        await self.send(b"write erase\r")
        position, _ = await self.expect(rb"Erase configuration in flash memory\?\s*\[confirm\]", position)
        await self.send(b"\r")
        position, _ = await self.expect(rb"\[OK\][\s\S]*ciscoasa#\s*$", position)
        self.phase = "reload"
        await self.send(b"reload\r")
        position, match = await self.expect(rb"Save\?\s*\[Y\]es/\[N\]o:|\[confirm\]", position)
        if b"Save?" in match:
            await self.send(b"n\r")
            position, _ = await self.expect(rb"\[confirm\]", position)
        await self.send(b"\r")
        # Wait through native filesystem shutdown, not just the CLI's reload
        # acknowledgement, before stopping the disposable VM.
        self.phase = "filesystem_shutdown"
        await self.expect(rb"GNU GRUB", position, seconds=120)
        self.phase = "complete"


async def erase_clone(node, disk):
    identifier = node_identifier(node)
    disk_filename = str(disk).replace(",", ",,")
    arguments = [
        node.qemu_path,
        "-enable-kvm",
        "-cpu",
        "host",
        "-m",
        str(node.ram),
        "-smp",
        str(node.cpus),
        "-nographic",
        "-monitor",
        "none",
        "-serial",
        "stdio",
        "-uuid",
        identifier,
        "-nic",
        "none",
        "-boot",
        "order=c",
        "-drive",
        f"file={disk_filename},if=virtio,format=qcow2",
    ]
    for index in range(10):
        arguments.extend(
            [
                "-netdev",
                f"hubport,id=n{index},hubid={index}",
                "-device",
                f"virtio-net-pci,netdev=n{index}",
            ]
        )
    process = console = None
    try:
        async with asyncio.timeout(ERASE_SECONDS):
            process = await asyncio.create_subprocess_exec(
                *arguments,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            console = RecoveryConsole(process)
            await console.erase()
    except (OSError, TimeoutError, ConnectionError, ConfigurationError):
        # Keep diagnostics private and bounded. The public error must never
        # contain terminal output, passwords or configuration data.
        try:
            root = safe_directory(Path(node.working_dir) / ".asav-recovery")
            if console is not None:
                atomic_bytes(root / "asav-recovery.log", bytes(console.data[: 2 * 1024 * 1024]))
            write_json(
                root / "asav-recovery-status.json",
                {
                    "status": "failed",
                    "phase": console.phase if console is not None else "launch",
                },
            )
        except (OSError, ConfigurationError):
            pass
        raise ConfigurationError("configuration_factory_reset_failed") from None
    finally:
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), TERMINATE_SECONDS)
            except TimeoutError:
                process.kill()
                await process.wait()
        if console is not None:
            await asyncio.gather(console.reader, return_exceptions=True)


ERASE_LOCK = asyncio.Lock()


def check_recovery_disk(node):
    from gns3server.compute.qemu.qemu_error import QemuError

    if not os.access("/dev/kvm", os.R_OK | os.W_OK) or node.ram < 2048 or node._hda_disk_interface != "virtio":
        raise ConfigurationError("configuration_topology_unsupported")
    if not node.linked_clone or not Path(node._hda_disk_image).is_file():
        raise ConfigurationError("configuration_topology_unsupported")
    try:
        node._get_qemu_img()
    except QemuError:
        raise ConfigurationError("configuration_factory_reset_failed") from None


async def erased_disk(node, files=None, workdir=None):
    """The erased qcow2 overlay of the node's base image, built by the recovery VM on first use and cached for all nodes."""
    check_recovery_disk(node)
    base = Path(node._hda_disk_image).absolute()
    base_stat = base.stat()
    # The erased state does not depend on the VM identity: one overlay serves every node of this image.
    key = hashlib.sha256(json.dumps([1, str(base), base_stat.st_size, base_stat.st_mtime_ns]).encode()).hexdigest()
    async with ERASE_LOCK:
        root = safe_directory(Path(Config.instance().config_dir) / CACHE_DIRECTORY)
        target = root / f"{key}.asav.qcow2"
        if target.is_file():
            return target
        node.check_available_ram(node.ram)
        with tempfile.TemporaryDirectory(prefix="asav-erase-", dir=root) as temporary:
            disk = Path(temporary) / "erased.qcow2"
            await create_overlay(node, base, disk)
            await erase_clone(node, disk)
            await copy_private_disk(disk, target)
        return target


async def create_overlay(node, base, disk):
    process = await asyncio.create_subprocess_exec(
        node._get_qemu_img(),
        *("create", "-q", "-f", "qcow2", "-F", "qcow2", "-b", str(base), str(disk)),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    if await process.wait() != 0:
        raise ConfigurationError("configuration_factory_reset_failed")


ENABLE_PASSWORD = re.compile(r"^enable password (\S+).*\n?", re.M)


def render(content, context):
    """The text, with the node's saved password as the enable password when the text has no usable one.

    A listing pasted from ``show running-config`` prints its secrets as ``*****``; such a line cannot be
    loaded and leaves the ASAv asking for an enable password at the first ``enable``.
    """
    text = checked_text(content)
    usable = any("*****" not in match[1] for match in ENABLE_PASSWORD.finditer(text))
    password = plain_password(context)
    if not usable and password:
        text = f"enable password {password}\n" + ENABLE_PASSWORD.sub("", text)
    return {"day0-config": text.encode("utf-8")}


PROFILE = BootMediaProfile(
    id="cisco-asav",
    title="Cisco ASAv",
    description="Delivers the startup entry as day0-config on a CD-ROM read at the first boot.",
    device_types=("cisco_asa",),
    volume_label="cidata",
    render=render,
    uses_admin_password=True,
    prepare_disk=erased_disk,
    check_disk=check_recovery_disk,
    stage_seconds=420,
    machine="pc",
)
