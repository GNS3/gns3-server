"""Staging and removal of a node's boot media, driven by the runtime journal.

Journal states used: ``clean`` (after a wipe, nothing booted yet) and
``prepared`` (media staged for the next boot). Launching the node records
``initialized`` (``mark_started``), after which the media is no longer
attached. A wipe removes the media and marks the journal clean again.
"""

import shutil
import tempfile
from pathlib import Path

from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.node_lease import require_stopped
from gns3server.services.configurations.shared.safe_io import atomic_bytes, copy_private_disk, validate_owned_paths
from gns3server.services.configurations.shared.startup_journal import (
    is_new_runtime,
    journal_path,
    runtime,
    set_runtime_state,
)

from .disk_builder import build_disk
from .iso_builder import build_iso
from .media_profile import MediaContext
from .profiles import get_profile
from .qemu_attachment import DISK_MEDIA_FILENAME, ISO_MEDIA_FILENAME, ide_slot, media_filename, virtio_slot


def wipe_paths(root):
    """Media files a wipe removes, whatever their kind (absent is fine)."""
    return [root / ISO_MEDIA_FILENAME, root / DISK_MEDIA_FILENAME]


WORKDIR_PREFIX = ".prepare-"


def remove_stale_workdirs(root):
    """Remove scratch directories a killed server left behind (they can hold a multi-GB raw copy of the disk)."""
    for path in root.glob(WORKDIR_PREFIX + "*"):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)


def fresh_runtime(node):
    """A node that never ran: no journal and, for a linked clone, no overlay disks yet.

    A full clone has no overlays either way, so it counts only while its creation marker exists.
    """
    root = Path(node.working_dir)
    if journal_path(node).exists() or any((root / f"hd{drive}_disk.qcow2").exists() for drive in "abcd"):
        return False
    return getattr(node, "linked_clone", True) or is_new_runtime(node)


# Journal states in which a profile's artifacts may be in place: being written, and complete.
STAGED = ("preparing", "prepared")


def reconcile_staged(node):
    """Drop what was staged for a profile the node no longer has, before it can boot it."""
    if not journal_path(node).exists():
        return
    value = runtime(node)
    owner = value.get("profile")
    if value["state"] not in STAGED or owner is None or owner == getattr(node, "startup_media_profile", None):
        return
    root = Path(node.working_dir).resolve(strict=True)
    paths = wipe_paths(root)
    if value.get("disk"):
        # The profile prepared the overlay itself; the next start creates a fresh one.
        paths.append(root / "hda_disk.qcow2")
    validate_owned_paths(root, paths)
    for path in paths:
        path.unlink(missing_ok=True)
    set_runtime_state(node, "clean")


async def stage_media(node, profile_id, content, admin_password=None):
    """Stage media for the next boot; True when the guest will receive it.

    ``content`` None only withdraws previously staged media. Nothing is staged
    for a runtime that already booted: it keeps its own state until a wipe.
    """
    profile = get_profile(profile_id)
    if getattr(node, "startup_media_profile", None) != profile.id:
        raise ConfigurationError("configuration_profile_mismatch")
    # Check the text before any state change: bad content must leave the node untouched.
    files = (
        None
        if content is None
        else profile.files(content, MediaContext(node_id=str(node.id), admin_password=admin_password))
    )
    require_stopped(node)
    reconcile_staged(node)
    value = runtime(node)
    state = value["state"]
    if state == "legacy_existing" and fresh_runtime(node):
        set_runtime_state(node, "clean")
        state = "clean"
    # A staging that was interrupted while it replaced the artifacts is simply done again.
    interrupted = state == "preparing" and "profile" in value
    if state not in ("clean", "prepared") and not interrupted:
        return False
    root = Path(node.working_dir).resolve(strict=True)
    target = root / media_filename(profile)
    overlay = root / "hda_disk.qcow2"
    validate_owned_paths(root, [*wipe_paths(root), overlay])
    if content is None:
        for path in wipe_paths(root):
            path.unlink(missing_ok=True)
        if (profile.media == "none" and state == "prepared") or (state in STAGED and value.get("disk")):
            # The prepared disk carries the withdrawn configuration and has not booted yet: drop it.
            overlay.unlink(missing_ok=True)
        set_runtime_state(node, "clean")
        return False
    image = await _build_for_node(node, profile, files)
    owner = {"profile": profile.id, "disk": profile.prepare_disk is not None}
    if profile.prepare_disk is not None:
        remove_stale_workdirs(root)
        with tempfile.TemporaryDirectory(prefix=WORKDIR_PREFIX, dir=root) as workdir:
            prepared = await profile.prepare_disk(node, files, Path(workdir))
            # Ownership is recorded before the disk is replaced, so that an interruption can be cleaned up.
            set_runtime_state(node, "preparing", **owner)
            await copy_private_disk(prepared, overlay)
    if image is not None:
        set_runtime_state(node, "preparing", **owner)
        atomic_bytes(target, image)
    # Media of another kind (the node's profile changed since it was staged) must not linger.
    for stale in wipe_paths(root):
        if image is None or stale != target:
            stale.unlink(missing_ok=True)
    set_runtime_state(node, "prepared", **owner)
    return True


async def preflight_media(node, profile_id, content, admin_password=None):
    """Build a disposable image to verify the source and compute prerequisites before a wipe."""
    profile = get_profile(profile_id)
    if getattr(node, "startup_media_profile", None) != profile.id:
        raise ConfigurationError("configuration_profile_mismatch")
    files = profile.files(content, MediaContext(node_id=str(node.id), admin_password=admin_password))
    await _build_for_node(node, profile, files)


async def _build_for_node(node, profile, files):
    """Check the prerequisites and build the media image; None for a profile that attaches no media."""
    from gns3server.compute.qemu.qemu_error import QemuError

    if profile.check_disk is not None:
        profile.check_disk(node)
    if profile.media == "none":
        return None
    build, slot = (build_disk, virtio_slot) if profile.media == "disk" else (build_iso, ide_slot)
    try:
        slot(node)
    except QemuError:
        raise ConfigurationError("configuration_media_slot_unavailable") from None
    return await build(files, profile.volume_label)
