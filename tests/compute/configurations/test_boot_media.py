"""Compute-side boot media: staging by journal state, QEMU attachment and wipe."""

from dataclasses import replace
from typing import NamedTuple
from unittest.mock import AsyncMock

import pytest

from gns3server.compute.qemu.qemu_error import QemuError
from gns3server.services.configurations.boot_media import BootMediaProfile, staging
from gns3server.services.configurations.boot_media.profiles import PROFILES
from gns3server.services.configurations.boot_media.qemu_attachment import (
    DISK_MEDIA_FILENAME,
    ISO_MEDIA_FILENAME,
    ide_slot,
    media_options,
    virtio_slot,
)
from gns3server.services.configurations.boot_media.staging import (
    fresh_runtime,
    preflight_media,
    reconcile_staged,
    stage_media,
)
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.startup_journal import (
    VERSION,
    forget_new_runtime,
    journal_path,
    mark_new_runtime,
    mark_started,
    runtime,
    set_runtime_state,
)
from tests.support.configurations import media_node

PROFILE = "cisco-c8000v-autonomous"
DISK_PROFILE = "cisco-iosv"


@pytest.fixture
def image_builders(monkeypatch):
    monkeypatch.setattr(staging, "build_iso", AsyncMock(side_effect=lambda files, _: b"iso:" + repr(files).encode()))
    monkeypatch.setattr(staging, "build_disk", AsyncMock(side_effect=lambda files, _: b"fat:" + repr(files).encode()))


class MediaCase(NamedTuple):
    profile: str
    filename: str
    other_filename: str
    prefix: bytes
    drive_options: str


@pytest.fixture(
    params=[
        pytest.param(
            MediaCase(
                PROFILE,
                ISO_MEDIA_FILENAME,
                DISK_MEDIA_FILENAME,
                b"iso:",
                "if=ide,index=2,media=cdrom,format=raw,readonly=on",
            ),
            id="iso",
        ),
        pytest.param(
            MediaCase(
                DISK_PROFILE,
                DISK_MEDIA_FILENAME,
                ISO_MEDIA_FILENAME,
                b"fat:",
                "if=virtio,index=1,media=disk,format=raw,id=startup-media",
            ),
            id="fat",
        ),
    ]
)
def media_case(request, image_builders):
    return request.param


@pytest.mark.asyncio
async def test_media_preflight_checks_slots_without_touching_the_running_guest(tmp_path, monkeypatch):
    node = media_node(tmp_path / "n", status="started", cdrom_image="one.iso", cdrom2_image="two.iso")
    build = AsyncMock(return_value=b"temporary image")
    monkeypatch.setattr(staging, "build_iso", build)
    with pytest.raises(ConfigurationError, match="configuration_media_slot_unavailable"):
        await preflight_media(node, PROFILE, "hostname R1\n")
    build.assert_not_awaited()
    node.cdrom2_image = ""
    await preflight_media(node, PROFILE, "hostname R1\n")
    build.assert_awaited_once()
    assert not list((tmp_path / "n").iterdir())


@pytest.mark.asyncio
async def test_asav_preflight_reports_missing_recovery_tool_without_preparing_a_disk(tmp_path, monkeypatch):
    from gns3server.services.configurations.boot_media.profiles import cisco_asav

    def missing_qemu_img():
        raise QemuError("missing qemu-img")

    monkeypatch.setattr(cisco_asav.os, "access", lambda *_: True)
    node = media_node(
        tmp_path / "n",
        profile="cisco-asav",
        status="started",
        ram=2048,
        _hda_disk_interface="virtio",
        _get_qemu_img=missing_qemu_img,
    )
    with pytest.raises(ConfigurationError, match="configuration_factory_reset_failed"):
        await preflight_media(node, "cisco-asav", "hostname ASA1\n")
    assert not list((tmp_path / "n").iterdir())


@pytest.mark.asyncio
async def test_a_fresh_node_is_staged_and_the_journal_records_it(tmp_path, media_case):
    root = tmp_path / "n"
    node = media_node(root, media_case.profile)
    assert fresh_runtime(node)
    assert await stage_media(node, media_case.profile, "hostname R1\n") is True
    image = (root / media_case.filename).read_bytes()
    assert image.startswith(media_case.prefix)
    assert b"hostname R1" in image
    assert not (root / media_case.other_filename).exists()
    assert runtime(node) == {
        "version": VERSION,
        "state": "prepared",
        "generation": 0,
        "profile": media_case.profile,
        "disk": False,
    }


@pytest.mark.asyncio
async def test_staging_again_before_the_first_boot_replaces_the_media(tmp_path, media_case):
    node = media_node(tmp_path / "n", media_case.profile)
    await stage_media(node, media_case.profile, "hostname first\n")
    path = tmp_path / "n" / media_case.filename
    assert b"hostname first" in path.read_bytes()
    assert await stage_media(node, media_case.profile, "hostname second\n") is True
    image = path.read_bytes()
    assert b"hostname second" in image and b"hostname first" not in image
    assert runtime(node)["state"] == "prepared"


@pytest.mark.asyncio
async def test_withdrawing_removes_the_media_and_returns_to_clean(tmp_path, media_case):
    root = tmp_path / "n"
    node = media_node(root, media_case.profile)
    await stage_media(node, media_case.profile, "hostname R1\n")
    (root / media_case.other_filename).write_bytes(b"leftover")
    assert await stage_media(node, media_case.profile, None) is False
    assert not (root / media_case.filename).exists() and not (root / media_case.other_filename).exists()
    assert runtime(node)["state"] == "clean"
    assert media_options(node) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["initialized", "legacy_existing"])
async def test_a_runtime_that_already_booted_is_left_alone(tmp_path, state):
    node = media_node(tmp_path / "n")
    (tmp_path / "n" / "hda_disk.qcow2").write_bytes(b"overlay")
    set_runtime_state(node, state)
    assert await stage_media(node, PROFILE, "hostname R1\n") is False
    assert not (tmp_path / "n" / ISO_MEDIA_FILENAME).exists() and runtime(node)["state"] == state


@pytest.mark.asyncio
async def test_an_unjournaled_node_with_an_overlay_is_existing_not_fresh(tmp_path):
    node = media_node(tmp_path / "n")
    (tmp_path / "n" / "hda_disk.qcow2").write_bytes(b"overlay")
    assert not fresh_runtime(node)
    assert await stage_media(node, PROFILE, "hostname R1\n") is False
    assert not journal_path(node).exists()


@pytest.mark.parametrize("profile_now", [None, "cisco-c8000v-autonomous"])
def test_what_was_staged_for_another_profile_is_dropped_before_a_boot(tmp_path, profile_now):
    node = media_node(tmp_path / "n", profile=profile_now)
    root = tmp_path / "n"
    for name in ("hda_disk.qcow2", ISO_MEDIA_FILENAME):
        (root / name).write_bytes(b"prepared for vEOS")
    set_runtime_state(node, "prepared", profile="arista-veos", disk=True)
    reconcile_staged(node)
    assert not (root / "hda_disk.qcow2").exists() and not (root / ISO_MEDIA_FILENAME).exists()
    assert runtime(node)["state"] == "clean"


@pytest.mark.parametrize("state,owner", [("prepared", PROFILE), ("initialized", "arista-veos"), ("prepared", None)])
def test_reconciling_keeps_a_disk_that_belongs_to_the_node(tmp_path, state, owner):
    node = media_node(tmp_path / "n")
    (tmp_path / "n" / "hda_disk.qcow2").write_bytes(b"the node's disk")
    set_runtime_state(node, state, **({"profile": owner, "disk": True} if owner else {}))
    reconcile_staged(node)
    assert (tmp_path / "n" / "hda_disk.qcow2").exists() and runtime(node)["state"] == state


def test_a_full_clone_is_new_only_while_its_creation_marker_exists(tmp_path):
    node = media_node(tmp_path / "n", linked_clone=False)
    assert not fresh_runtime(node)
    mark_new_runtime(node)
    assert fresh_runtime(node)
    forget_new_runtime(node)
    assert not fresh_runtime(node)


@pytest.mark.asyncio
@pytest.mark.parametrize("recovery", ["profile_removed", "startup_off", "start_again"])
async def test_a_prepared_disk_stays_owned_when_the_journal_cannot_be_completed(tmp_path, monkeypatch, recovery):
    async def prepare(node, files, workdir):
        disk = workdir / "disk.qcow2"
        disk.write_bytes(b"carries the configuration")
        return disk

    profile = BootMediaProfile(
        "disk-writer", "T", "d", ("x",), "L", lambda content, context: {"f": b"x"}, media="none", prepare_disk=prepare
    )
    monkeypatch.setattr(staging, "get_profile", lambda identifier: profile)
    node = media_node(tmp_path / "n", profile="disk-writer")
    set_runtime_state(node, "clean")
    overlay = tmp_path / "n" / "hda_disk.qcow2"
    complete = staging.set_runtime_state

    def fail(node, state, **details):
        if state == "prepared":
            raise OSError("disk full")
        complete(node, state, **details)

    monkeypatch.setattr(staging, "set_runtime_state", fail)
    with pytest.raises(OSError):
        await stage_media(node, "disk-writer", "text")
    monkeypatch.setattr(staging, "set_runtime_state", complete)
    assert overlay.exists() and runtime(node)["state"] == "preparing"
    if recovery == "profile_removed":
        node.startup_media_profile = None
        reconcile_staged(node)
        assert not overlay.exists() and runtime(node)["state"] == "clean"
    elif recovery == "startup_off":
        assert await stage_media(node, "disk-writer", None) is False
        assert not overlay.exists() and runtime(node)["state"] == "clean"
    else:
        assert await stage_media(node, "disk-writer", "text") is True
        assert runtime(node)["state"] == "prepared"


@pytest.mark.asyncio
async def test_staging_needs_a_stopped_node_and_the_nodes_own_profile(tmp_path):
    node = media_node(tmp_path / "n", status="started")
    with pytest.raises(ConfigurationError, match="stop_required"):
        await stage_media(node, PROFILE, "hostname R1\n")
    node.status = "stopped"
    with pytest.raises(ConfigurationError, match="configuration_profile_mismatch"):
        await stage_media(node, "cisco-viptela", "system\n host-name x\n")
    with pytest.raises(ConfigurationError, match="startup_media_profile_unknown"):
        await stage_media(node, "nope", "x")
    assert not (tmp_path / "n" / ISO_MEDIA_FILENAME).exists()


@pytest.mark.asyncio
async def test_invalid_content_stages_nothing(tmp_path):
    node = media_node(tmp_path / "n")
    with pytest.raises(ConfigurationError, match="configuration_invalid_content"):
        await stage_media(node, PROFILE, "  \n")
    assert not (tmp_path / "n" / ISO_MEDIA_FILENAME).exists() and not journal_path(node).exists()


@pytest.mark.asyncio
async def test_the_media_is_attached_to_the_first_boot_only(tmp_path, media_case):
    node = media_node(tmp_path / "n", media_case.profile, _hda_disk_interface="virtio")
    assert media_options(node) == []
    await stage_media(node, media_case.profile, "hostname R1\n")
    path = tmp_path / "n" / media_case.filename
    assert media_options(node) == ["-drive", f"file={path},{media_case.drive_options}"]
    mark_started(node)
    assert runtime(node)["state"] == "initialized"
    assert media_options(node) == []


@pytest.mark.asyncio
async def test_a_missing_staged_file_fails_the_launch_instead_of_booting_without_it(tmp_path, media_case):
    node = media_node(tmp_path / "n", media_case.profile)
    await stage_media(node, media_case.profile, "hostname R1\n")
    (tmp_path / "n" / media_case.filename).unlink()
    with pytest.raises(QemuError, match="media is missing"):
        media_options(node)


@pytest.mark.parametrize(
    "settings,index",
    [
        ({}, 2),
        ({"cdrom_image": "/i.iso"}, 3),
        ({"cdrom_image": "/i.iso", "cdrom_interface": "sata"}, 2),
        ({"_hdc_disk_image": "/c.img", "_hdc_disk_interface": "ide"}, 3),
        ({"cdrom_image": "/i.iso", "cdrom2_image": "/j.iso", "cdrom2_interface": "sata"}, 3),
        # The config disk inherits the HDA interface when HDD has none (index 3 on IDE).
        ({"cdrom_image": "/i.iso", "create_config_disk": True, "_hda_disk_interface": "virtio"}, 3),
        ({"create_config_disk": True, "_hda_disk_interface": "ide"}, 2),
    ],
)
def test_the_first_free_ide_slot_is_used(tmp_path, settings, index):
    assert ide_slot(media_node(tmp_path / "n", **settings)) == index


@pytest.mark.parametrize(
    "settings",
    [
        {"cdrom_image": "/i.iso", "cdrom2_image": "/j.iso"},
        {"cdrom_image": "/i.iso", "create_config_disk": True, "_hda_disk_interface": "ide"},
    ],
)
def test_no_free_slot_is_reported_clearly(tmp_path, settings):
    node = media_node(tmp_path / "n", **settings)
    with pytest.raises(QemuError, match="No free IDE CD-ROM slot"):
        ide_slot(node)


@pytest.mark.usefixtures("image_builders")
@pytest.mark.asyncio
async def test_a_profile_with_a_prepared_disk_boots_from_it(tmp_path, monkeypatch):
    erased = tmp_path / "erased.qcow2"
    erased.write_bytes(b"erased overlay")
    prepare = AsyncMock(return_value=erased)
    profile = replace(staging.get_profile(PROFILE), prepare_disk=prepare)
    monkeypatch.setattr(staging, "get_profile", lambda _: profile)
    node = media_node(tmp_path / "n")
    assert await stage_media(node, PROFILE, "hostname R1\n") is True
    (called_node, files, workdir), _ = prepare.await_args
    assert called_node is node and files == {"iosxe_config.txt": b"hostname R1\n"}
    assert workdir.parent == tmp_path / "n" and not workdir.exists()  # A scratch directory, removed afterwards.
    assert (tmp_path / "n" / "hda_disk.qcow2").read_bytes() == b"erased overlay"
    assert media_options(node)


@pytest.mark.usefixtures("image_builders")
@pytest.mark.asyncio
async def test_a_failed_disk_preparation_stages_nothing(tmp_path, monkeypatch):
    profile = replace(
        staging.get_profile(PROFILE),
        prepare_disk=AsyncMock(side_effect=ConfigurationError("configuration_factory_reset_failed")),
    )
    monkeypatch.setattr(staging, "get_profile", lambda _: profile)
    node = media_node(tmp_path / "n")
    with pytest.raises(ConfigurationError, match="configuration_factory_reset_failed"):
        await stage_media(node, PROFILE, "hostname R1\n")
    assert not (tmp_path / "n" / "hda_disk.qcow2").exists() and not media_options(node)


@pytest.mark.usefixtures("image_builders")
@pytest.mark.asyncio
async def test_a_profile_of_another_kind_replaces_the_media_staged_before(tmp_path):
    node = media_node(tmp_path / "n", DISK_PROFILE)
    (tmp_path / "n" / ISO_MEDIA_FILENAME).write_bytes(b"old cd-rom media")
    set_runtime_state(node, "clean")
    await stage_media(node, DISK_PROFILE, "hostname R1\n")
    assert (tmp_path / "n" / DISK_MEDIA_FILENAME).is_file() and not (tmp_path / "n" / ISO_MEDIA_FILENAME).exists()


@pytest.mark.parametrize(
    "settings,index",
    [
        ({}, 1),
        ({"_hda_disk_interface": "virtio"}, 1),
        ({"_hdb_disk_image": "/b.img", "_hdb_disk_interface": "virtio"}, 2),
        ({"_hdb_disk_image": "/b.img", "_hdb_disk_interface": "ide"}, 1),
        (
            {
                "_hdb_disk_image": "/b.img",
                "_hdb_disk_interface": "virtio",
                "_hdc_disk_image": "/c.img",
                "_hdc_disk_interface": "virtio",
            },
            3,
        ),
        # The config disk takes index 3 on the HDA interface when HDD has none.
        (
            {
                "_hdb_disk_image": "/b.img",
                "_hdb_disk_interface": "virtio",
                "_hdc_disk_image": "/c.img",
                "_hdc_disk_interface": "virtio",
                "create_config_disk": True,
                "_hda_disk_interface": "virtio",
            },
            None,
        ),
    ],
)
def test_the_first_free_virtio_disk_slot_is_used(tmp_path, settings, index):
    node = media_node(tmp_path / "n", DISK_PROFILE, **settings)
    if index is None:
        with pytest.raises(QemuError, match="No free virtio disk slot"):
            virtio_slot(node)
    else:
        assert virtio_slot(node) == index


@pytest.mark.asyncio
async def test_media_of_the_other_kind_stays_until_the_new_media_is_written(tmp_path, monkeypatch):
    node = media_node(tmp_path / "n", DISK_PROFILE)
    (tmp_path / "n" / ISO_MEDIA_FILENAME).write_bytes(b"old cd-rom media")
    set_runtime_state(node, "clean")

    async def failing(files, label):
        raise ConfigurationError("boot_media_build_failed")

    monkeypatch.setattr(staging, "build_disk", failing)
    with pytest.raises(ConfigurationError, match="boot_media_build_failed"):
        await stage_media(node, DISK_PROFILE, "hostname R1\n")
    assert (tmp_path / "n" / ISO_MEDIA_FILENAME).read_bytes() == b"old cd-rom media"
    assert runtime(node)["state"] == "clean"


def no_media_profile(prepare):
    return replace(PROFILES[PROFILE], media="none", prepare_disk=prepare)


@pytest.mark.asyncio
async def test_a_profile_without_media_only_prepares_the_nodes_disk(tmp_path, monkeypatch):
    prepared = tmp_path / "prepared.qcow2"
    prepared.write_bytes(b"prepared overlay")
    profile = no_media_profile(AsyncMock(return_value=prepared))
    monkeypatch.setitem(PROFILES, PROFILE, profile)
    node = media_node(tmp_path / "n")
    (tmp_path / "n" / ISO_MEDIA_FILENAME).write_bytes(b"media of an earlier profile")
    assert await stage_media(node, PROFILE, "hostname R1\n") is True
    assert (tmp_path / "n" / "hda_disk.qcow2").read_bytes() == b"prepared overlay"
    assert not (tmp_path / "n" / ISO_MEDIA_FILENAME).exists() and not (tmp_path / "n" / DISK_MEDIA_FILENAME).exists()
    assert runtime(node)["state"] == "prepared" and media_options(node) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("state,media", [("prepared", "none"), ("clean", "none"), ("prepared", "cdrom")])
async def test_withdrawing_removes_only_the_prepared_disk(tmp_path, monkeypatch, state, media):
    profile = replace(no_media_profile(AsyncMock()), media=media)
    monkeypatch.setitem(PROFILES, PROFILE, profile)
    node = media_node(tmp_path / "n")
    if media == "cdrom":
        set_runtime_state(node, state, profile=PROFILE, disk=True)
    else:
        set_runtime_state(node, state)
    (tmp_path / "n" / "hda_disk.qcow2").write_bytes(b"overlay")
    assert await stage_media(node, PROFILE, None) is False
    assert (tmp_path / "n" / "hda_disk.qcow2").exists() is (state == "clean")
    assert runtime(node)["state"] == "clean"


@pytest.mark.asyncio
async def test_a_profile_without_media_still_checks_its_prerequisites_first(tmp_path, monkeypatch):
    profile = replace(
        no_media_profile(AsyncMock()),
        check_disk=lambda node: (_ for _ in ()).throw(ConfigurationError("boot_media_tool_missing")),
    )
    monkeypatch.setitem(PROFILES, PROFILE, profile)
    node = media_node(tmp_path / "n")
    with pytest.raises(ConfigurationError, match="boot_media_tool_missing"):
        await stage_media(node, PROFILE, "hostname R1\n")
    with pytest.raises(ConfigurationError, match="boot_media_tool_missing"):
        await preflight_media(node, PROFILE, "hostname R1\n")
    profile.prepare_disk.assert_not_awaited()
    assert not (tmp_path / "n" / "hda_disk.qcow2").exists()


@pytest.mark.asyncio
async def test_scratch_directories_of_a_killed_staging_are_removed_at_the_next_one(tmp_path, monkeypatch):
    prepared = tmp_path / "prepared.qcow2"
    prepared.write_bytes(b"prepared overlay")
    monkeypatch.setitem(PROFILES, PROFILE, no_media_profile(AsyncMock(return_value=prepared)))
    node = media_node(tmp_path / "n")
    stale = tmp_path / "n" / ".prepare-killed"
    stale.mkdir()
    (stale / "base.raw").write_bytes(b"x" * 1024)
    keep = tmp_path / "n" / "other-directory"
    keep.mkdir()
    link_target = tmp_path / "outside"
    link_target.mkdir()
    (tmp_path / "n" / ".prepare-link").symlink_to(link_target)
    assert await stage_media(node, PROFILE, "hostname R1\n") is True
    assert not stale.exists() and keep.exists() and link_target.exists()
