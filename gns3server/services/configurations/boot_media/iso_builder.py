"""Build an ISO9660 image from in-memory files with the host's mastering tool.

No guest filesystem is mounted and no shell is involved: the tool is run with a
fixed argument list inside a private temporary directory.
"""

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path

from gns3server.services.configurations.shared.errors import ConfigurationError

log = logging.getLogger(__name__)

# First available wins. All three understand the mkisofs options below.
TOOLS = ("xorrisofs", "genisoimage", "mkisofs")
BUILD_SECONDS = 60
MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 16 * 1024 * 1024
# Fixed timestamp so the same files always produce the same image.
EPOCH = 315532800


def find_tool():
    for name in TOOLS:
        path = shutil.which(name)
        if path:
            return path
    raise ConfigurationError("boot_media_tool_missing")


def _mastering_command(tool, label, source, target):
    """The mastering command line (Rock Ridge + Joliet + full-length ISO names)."""
    return [tool, "-quiet", "-V", label, "-iso-level", "2", "-l", "-J", "-r", "-o", str(target), str(source)]


async def build_iso(files, volume_label):
    """Return the bytes of an ISO holding ``files`` ({path: bytes}); a path ending in ``/`` is an empty directory."""
    if sum(len(data) for data in files.values()) > MAX_INPUT_BYTES:
        raise ConfigurationError("boot_media_too_large")
    tool = find_tool()
    with tempfile.TemporaryDirectory(prefix="gns3-boot-media-") as directory:
        root = Path(directory)
        source = root / "content"
        source.mkdir(mode=0o700)
        for name, data in files.items():
            path = source / name
            if name.endswith("/"):
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        for path in (source, *source.rglob("*")):
            os.utime(path, (EPOCH, EPOCH))
        target = root / "media.iso"
        await run_tool(_mastering_command(tool, volume_label, source, target), root)
        try:
            if target.stat().st_size > MAX_IMAGE_BYTES:
                raise ConfigurationError("boot_media_too_large")
            return target.read_bytes()
        except OSError:
            raise ConfigurationError("boot_media_build_failed") from None


async def run_tool(arguments, cwd, success_codes=(0,), seconds=None):
    process = None
    diagnostics = Path(cwd) / "tool.log"
    try:
        async with asyncio.timeout(seconds or BUILD_SECONDS):
            with diagnostics.open("wb") as errors:
                process = await asyncio.create_subprocess_exec(
                    *arguments,
                    cwd=cwd,
                    env={**os.environ, "SOURCE_DATE_EPOCH": str(EPOCH), "LC_ALL": "C"},
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=errors,
                )
                await process.wait()
    except (OSError, TimeoutError):
        raise ConfigurationError("boot_media_build_failed") from None
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
    if process.returncode not in success_codes:
        # Tool diagnostics name files and options only, never file contents.
        log.warning(
            "%s failed (%s): %s",
            arguments[0],
            process.returncode,
            diagnostics.read_bytes()[:500].decode(errors="replace"),
        )
        raise ConfigurationError("boot_media_build_failed")
