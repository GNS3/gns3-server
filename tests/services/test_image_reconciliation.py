import asyncio
import hashlib
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import event, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from watchdog.events import FileDeletedEvent, FileModifiedEvent, FileMovedEvent

from gns3server.db.models import Base, Image, ImageSyncJob, Template
from gns3server.db.models.images import image_template_map
from gns3server.db.repositories.images import ImagesRepository
from gns3server.services.image_reconciliation import ImageReconciliationService, InventoryEvents, enumerate_root
from gns3server.utils.image_inventory import ImageLockBusy, fingerprint, image_lock
from gns3server.utils.images import InvalidImageError, inspect_image_file, md5sum, write_image

pytestmark = pytest.mark.asyncio
QCOW = b"QFI\xfb\x00\x00\x00"


@pytest_asyncio.fixture
async def inventory(tmp_path, config):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'catalog.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.connect() as conn:
        with patch("gns3server.services.authentication.AuthService.hash_password", return_value="test"):
            await conn.run_sync(Base.metadata.create_all)
        await conn.commit()
    service = ImageReconciliationService(engine, settle_seconds=0)
    try:
        yield service
    finally:
        await service.close()
        await engine.dispose()


def image_file(config, name="QEMU/image.qcow2", data=QCOW):
    path = Path(config.settings.Server.images_path) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


async def scan(service, **kwargs):
    job = await service.start(**kwargs)
    await service.task
    return await service.get_job(job["job_id"])


async def rows(service):
    async with AsyncSession(service.engine) as session:
        return [image.asdict() for image in (await session.execute(select(Image))).scalars()]


async def test_add_change_missing_restore_preserves_identity_and_template(inventory, config):
    path = image_file(config)
    assert (await scan(inventory))["counts"]["added"] == 1
    original = (await rows(inventory))[0]
    async with AsyncSession(inventory.engine) as session:
        image = await session.get(Image, original["image_id"])
        session.add(Template(name="Keep this reference", images=[image]))
        await session.commit()
    path.write_bytes(QCOW + b"changed")
    assert (await scan(inventory))["counts"]["updated"] == 1
    changed = (await rows(inventory))[0]
    assert changed["image_id"] == original["image_id"]
    assert changed["image_size"] == len(QCOW + b"changed")
    assert changed["checksum"] == hashlib.md5(QCOW + b"changed", usedforsecurity=False).hexdigest()
    path.unlink()
    assert (await scan(inventory))["counts"]["missing"] == 1
    assert (await rows(inventory))[0]["availability"] == "missing"
    path.write_bytes(QCOW)
    await scan(inventory)
    restored = (await rows(inventory))[0]
    assert restored["image_id"] == original["image_id"]
    assert restored["availability"] == "available"
    async with AsyncSession(inventory.engine) as session:
        assert len((await session.execute(select(image_template_map))).all()) == 1


async def test_fingerprints_skip_hashing_and_force_bypasses_sidecars(inventory, config):
    path = image_file(config)
    await scan(inventory)
    with patch(
        "gns3server.services.image_reconciliation.inspect_image_file", side_effect=AssertionError("unnecessary hash")
    ):
        result = await scan(inventory)
    assert result["status"] == "completed"
    assert result["counts"]["unchanged"] == 1
    assert result["counts"]["bytes_hashed"] == 0
    path.write_bytes(QCOW[:-1] + b"x")  # same-size modification
    sidecar = Path(str(path) + ".md5sum")
    sidecar.write_text("0" * 32)
    assert md5sum(str(path), cache_to_md5file=False) == "0" * 32
    assert (
        md5sum(str(path), cache_to_md5file=False, use_cache=False)
        == hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
    )
    result = await scan(inventory, force_checksum=True)
    assert result["counts"]["bytes_hashed"] == len(QCOW)
    assert (await rows(inventory))[0]["checksum"] == hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
    assert not sidecar.exists()


async def test_dry_run_does_not_write_catalog_or_sidecar(inventory, config):
    path = image_file(config)
    sidecar = Path(str(path) + ".md5sum")
    sidecar.write_text("0" * 32)
    result = await scan(inventory, dry_run=True, force_checksum=True)
    assert result["counts"]["added"] == 1
    assert await rows(inventory) == []
    assert sidecar.read_text() == "0" * 32
    await scan(inventory)
    before = await rows(inventory)
    path.unlink()
    assert (await scan(inventory, dry_run=True))["counts"]["missing"] == 1
    assert await rows(inventory) == before


@pytest.mark.parametrize("failure", ["missing_root", "partial_walk", "unreadable_file"])
async def test_failed_scopes_do_not_remove_rows(inventory, config, failure):
    path = image_file(config)
    await scan(inventory)
    root = str(config.settings.Server.images_path)
    if failure == "missing_root":
        os.rename(root, root + "-offline")
        result = await scan(inventory)
    elif failure == "partial_walk":
        with patch(
            "gns3server.services.image_reconciliation.enumerate_root",
            return_value=({}, [{"path": root, "reason": "Permission denied"}]),
        ):
            result = await scan(inventory)
    else:
        with patch(
            "gns3server.services.image_reconciliation.inspect_image_file", side_effect=PermissionError("denied")
        ):
            result = await scan(inventory, force_checksum=True)
    assert result["status"] == "partial"
    assert result["counts"]["missing"] == 0
    assert len(await rows(inventory)) == 1
    assert (await rows(inventory))[0]["availability"] == "unavailable"


async def test_extra_nested_and_overlapping_roots(inventory, config, tmp_path):
    extra = tmp_path / "extra"
    extra.mkdir()
    (extra / "image.qcow2").write_bytes(QCOW)
    image_file(config, "QEMU/nested/image.qcow2")
    image_file(config, "legacy.qcow2")
    config.settings.Server.additional_images_paths = [str(extra), str(extra), config.settings.Server.images_path]
    result = await scan(inventory)
    assert result["counts"]["added"] == 3
    assert len(await rows(inventory)) == 3


async def test_rename_retains_old_reference(inventory, config):
    path = image_file(config)
    await scan(inventory)
    old = (await rows(inventory))[0]
    path.rename(path.with_name("renamed.qcow2"))
    result = await scan(inventory)
    assert result["counts"]["added"] == result["counts"]["missing"] == 1
    assert next(row for row in await rows(inventory) if row["image_id"] == old["image_id"])["availability"] == "missing"


async def test_symlink_images_are_imported_and_target_changes_detected(inventory, config):
    target = image_file(config, ".storage/target.qcow2")
    path = image_file(config)
    path.unlink()
    path.symlink_to(target)
    assert fingerprint(path) == fingerprint(target)
    result = await scan(inventory)
    assert result["status"] == "completed", result
    assert result["counts"]["added"] == 1
    original = (await rows(inventory))[0]
    assert original["path"] == str(path)
    assert original["checksum"] == hashlib.md5(QCOW).hexdigest()
    target.write_bytes(QCOW + b"changed")
    result = await scan(inventory)
    assert result["counts"]["updated"] == 1
    updated = (await rows(inventory))[0]
    assert updated["image_id"] == original["image_id"]
    assert updated["checksum"] == hashlib.md5(target.read_bytes()).hexdigest()
    assert path.is_symlink()


@pytest.mark.parametrize("target_kind", ["directory", "missing"])
async def test_fingerprint_rejects_symlinks_without_regular_file_targets(tmp_path, target_kind):
    target = tmp_path / "target"
    if target_kind == "directory":
        target.mkdir()
    link = tmp_path / "image.qcow2"
    link.symlink_to(target, target_is_directory=target_kind == "directory")
    with pytest.raises(OSError):
        fingerprint(link)


async def test_external_symlinks_hidden_files_and_libraries_are_not_imported(inventory, config, tmp_path):
    outside = tmp_path / "outside.qcow2"
    outside.write_bytes(QCOW)
    path = image_file(config)
    path.unlink()
    path.symlink_to(outside)
    image_file(config, ".hidden/hidden.qcow2")
    image_file(config, "IOU/lib/library.so")
    image_file(config, "QEMU/upload.tmp")
    result = await scan(inventory)
    assert result["counts"]["added"] == 0
    assert outside.read_bytes() == QCOW


@pytest.mark.parametrize(
    "name,data,expected",
    [
        ("QEMU/disk.raw", b"raw image bytes", "qemu"),
        ("IOS/ios.bin", b"\x7fELF\x01\x02\x01", "ios"),
        ("IOU/iou.bin", b"\x7fELF\x02\x01\x01", "iou"),
    ],
)
async def test_image_types_and_raw_policy(inventory, config, name, data, expected):
    image_file(config, name, data)
    result = await scan(inventory)
    assert result["counts"]["added"] == 1
    assert (await rows(inventory))[0]["image_type"] == expected


async def test_invalid_replacement_not_usable(inventory, config):
    path = image_file(config)
    await scan(inventory)
    path.write_bytes(b"bad")
    assert (await scan(inventory))["counts"]["invalid"] == 1
    async with AsyncSession(inventory.engine) as session:
        repo = ImagesRepository(session)
        assert await repo.get_image_by_checksum(hashlib.md5(QCOW, usedforsecurity=False).hexdigest()) is None
    assert (await rows(inventory))[0]["checksum"] == hashlib.md5(QCOW, usedforsecurity=False).hexdigest()


async def test_changed_during_inspection_is_deferred(inventory, config):
    path = image_file(config)
    original = inspect_image_file

    def replace_after_hash(*args):
        info = original(*args)
        path.write_bytes(QCOW + b"still copying")
        return info

    with patch("gns3server.services.image_reconciliation.inspect_image_file", side_effect=replace_after_hash):
        result = await scan(inventory)
    assert result["counts"]["deferred"] == 1
    assert await rows(inventory) == []
    assert (await scan(inventory))["counts"]["added"] == 1


async def test_per_file_database_failure_does_not_poison_next_file(inventory, config):
    image_file(config, "QEMU/first.qcow2")
    image_file(config, "QEMU/second.qcow2")
    original = ImagesRepository.save_verified_image
    calls = 0

    async def fail_first(repo, info):
        nonlocal calls
        calls += 1
        if calls == 1:
            # Real failed SQL statement in the file's session.
            await repo._db_session.execute(text("INSERT INTO nonexistent_image_table VALUES (1)"))
        return await original(repo, info)

    with patch.object(ImagesRepository, "save_verified_image", fail_first):
        result = await scan(inventory)
    assert result["status"] == "partial"
    assert result["counts"]["added"] == 1
    assert (await scan(inventory))["counts"]["added"] == 1
    assert len(await rows(inventory)) == 2


async def test_overlapping_jobs_rejected_and_interrupted_job_recovers(inventory, config):
    path = image_file(config)
    async with image_lock(str(path)):
        job = await inventory.start()
        other = ImageReconciliationService(inventory.engine, settle_seconds=0)
        with pytest.raises(ImageLockBusy):
            await other.start()
    await inventory.task
    async with AsyncSession(inventory.engine) as session:
        stale = await session.get(ImageSyncJob, job["job_id"])
        stale.status = "running"
        await session.commit()
    await scan(inventory)
    assert (await inventory.get_job(job["job_id"]))["status"] == "interrupted"


async def test_close_immediately_releases_lock_and_finishes_job(inventory, config):
    image_file(config)
    job = await inventory.start()
    await inventory.close()
    assert (await inventory.get_job(job["job_id"]))["status"] == "cancelled"
    other = ImageReconciliationService(inventory.engine, settle_seconds=0)
    try:
        assert (await scan(other))["status"] == "completed"
    finally:
        await other.close()


async def test_watcher_coalesces_move_delete_modify_events():
    dirty = asyncio.Event()
    handler = InventoryEvents(asyncio.get_running_loop(), dirty)
    for fs_event in [
        FileMovedEvent("/images/upload.tmp", "/images/new.qcow2"),
        FileDeletedEvent("/images/deleted.qcow2"),
        FileModifiedEvent("/images/changed.qcow2"),
    ]:
        dirty.clear()
        handler.dispatch(fs_event)
        await asyncio.sleep(0)
        assert dirty.is_set()
    dirty.clear()
    handler.dispatch(FileModifiedEvent("/images/new.qcow2.md5sum"))
    await asyncio.sleep(0)
    assert not dirty.is_set()


async def stream(data, chunk_size=1):
    for offset in range(0, len(data), chunk_size):
        yield data[offset : offset + chunk_size]


async def test_upload_fragmented_header_and_missing_row_reuse(inventory, config):
    path = image_file(config)
    await scan(inventory)
    old_id = (await rows(inventory))[0]["image_id"]
    path.unlink()
    await scan(inventory)
    async with AsyncSession(inventory.engine, expire_on_commit=False) as session:
        image = await write_image("QEMU/image.qcow2", str(path), stream(QCOW), ImagesRepository(session))
        assert image.image_id == old_id
        assert image.availability == "available"
    assert path.read_bytes() == QCOW
    assert not list(path.parent.glob("*.tmp"))


async def test_upload_db_failure_is_recovered_by_scan(inventory, config):
    path = Path(config.settings.Server.images_path) / "QEMU/orphan.qcow2"
    async with AsyncSession(inventory.engine, expire_on_commit=False) as session:
        repo = ImagesRepository(session)
        with patch.object(repo, "save_verified_image", side_effect=SQLAlchemyError("commit failed")):
            with pytest.raises(SQLAlchemyError):
                await write_image("QEMU/orphan.qcow2", str(path), stream(QCOW), repo)
    assert path.read_bytes() == QCOW
    assert (await scan(inventory))["counts"]["added"] == 1


async def test_concurrent_uploads_never_overwrite(inventory, config):
    path = Path(config.settings.Server.images_path) / "QEMU/same.qcow2"

    async def upload(data):
        async with AsyncSession(inventory.engine, expire_on_commit=False) as session:
            return await write_image("QEMU/same.qcow2", str(path), stream(data), ImagesRepository(session))

    result = await asyncio.gather(upload(QCOW), upload(QCOW + b"different"), return_exceptions=True)
    assert sum(isinstance(item, InvalidImageError) for item in result) == 1
    assert len(await rows(inventory)) == 1
    assert (await rows(inventory))[0]["checksum"] == hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()


async def test_checksum_lookup_ignores_missing_duplicate(inventory, config):
    first = image_file(config, "QEMU/first.qcow2")
    second = image_file(config, "QEMU/second.qcow2")
    await scan(inventory)
    first.unlink()
    # No sync is needed to reject a stale candidate at the point of use.
    async with AsyncSession(inventory.engine) as session:
        image = await ImagesRepository(session).get_image_by_checksum(
            hashlib.md5(QCOW, usedforsecurity=False).hexdigest(), str(second.parent)
        )
        assert image.path == str(second)


async def test_path_matching_does_not_interpret_sql_wildcards(inventory, config):
    path = image_file(config, "QEMU/name_%/disk.qcow2")
    image_file(config, "QEMU/name_AB/disk.qcow2")
    await scan(inventory)
    async with AsyncSession(inventory.engine) as session:
        repo = ImagesRepository(session)
        assert (await repo.get_image("name_%/disk.qcow2")).path == str(path)
        assert await repo.get_image("me_%/disk.qcow2") is None


async def test_migration_roundtrip_preserves_rows_and_relationships(inventory, config):
    from alembic import command
    from alembic.config import Config

    image_file(config)
    await scan(inventory)
    original = (await rows(inventory))[0]
    async with AsyncSession(inventory.engine) as session:
        image = await session.get(Image, original["image_id"])
        session.add(Template(name="Migration reference", images=[image]))
        await session.commit()

    def migrate(connection):
        cfg = Config()
        cfg.set_main_option("script_location", "gns3server:db_migrations")
        cfg.attributes["connection"] = connection
        command.stamp(cfg, "d9e8a2b7c401")
        command.downgrade(cfg, "c7e4a9f1d2b6")
        assert connection.execute(text("SELECT count(*) FROM image_template_map")).scalar_one() == 1
        assert connection.execute(text("SELECT image_id FROM images")).scalar_one() == original["image_id"]
        command.upgrade(cfg, "head")
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []

    async with inventory.engine.connect() as connection:
        await connection.run_sync(migrate)
        await connection.commit()
    migrated = (await rows(inventory))[0]
    assert migrated["availability"] == "unknown"
    assert migrated["file_fingerprint"] is None
    assert migrated["image_id"] == original["image_id"]
    await scan(inventory)
    assert (await rows(inventory))[0]["availability"] == "available"


@pytest.mark.skipif(sys.platform != "linux", reason="Native Linux watcher integration")
async def test_native_watcher_covers_extra_roots_and_stops(inventory, config, tmp_path):
    extra = tmp_path / "extra-watch"
    extra.mkdir()
    config.settings.Server.additional_images_paths = [str(extra)]
    config.settings.Server.auto_discover_images = True
    await inventory._watch()
    observer = inventory.observer
    assert observer.is_alive()
    inventory.dirty.clear()
    temporary = extra / "incoming.tmp"
    temporary.write_bytes(QCOW)
    temporary.rename(extra / "finished.qcow2")
    await asyncio.wait_for(inventory.dirty.wait(), 5)
    assert (await scan(inventory))["counts"]["added"] == 1
    inventory.dirty.clear()
    (extra / "finished.qcow2").unlink()
    await asyncio.wait_for(inventory.dirty.wait(), 5)
    assert (await scan(inventory))["counts"]["missing"] == 1
    await inventory.close()
    assert not observer.is_alive()


@pytest.mark.skipif(os.name == "nt", reason="POSIX lock integration")
async def test_image_lock_excludes_another_process(config, tmp_path):
    path = str(tmp_path / "image.qcow2")
    code = "import fcntl, sys; f = open(sys.argv[1], 'a+b'); fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)"
    async with image_lock(path) as lock:
        lock_path = lock._file.name
        result = await asyncio.to_thread(subprocess.run, [sys.executable, "-c", code, lock_path], capture_output=True)
        assert result.returncode != 0
        assert b"BlockingIOError" in result.stderr
    result = await asyncio.to_thread(subprocess.run, [sys.executable, "-c", code, lock_path], capture_output=True)
    assert result.returncode == 0


async def test_shutdown_during_hash_waits_for_worker_before_releasing_lock(inventory, config):
    image_file(config)
    entered = threading.Event()
    exited = threading.Event()

    def slow_hash(path, expected, raw, stopped):
        entered.set()
        stopped.wait(5)
        exited.set()
        raise InterruptedError("stopped")

    with patch("gns3server.services.image_reconciliation.inspect_image_file", side_effect=slow_hash):
        job = await inventory.start()
        assert await asyncio.to_thread(entered.wait, 5)
        await inventory.close()
    assert exited.is_set()
    assert (await inventory.get_job(job["job_id"]))["status"] == "cancelled"
    assert await rows(inventory) == []


async def test_appliance_fallback_repairs_existing_row_and_rejects_wrong_content(inventory, config):
    from gns3server.controller.appliance_manager import ApplianceManager
    from gns3server.controller.controller_error import ControllerError

    path = image_file(config)
    await scan(inventory)
    old_id = (await rows(inventory))[0]["image_id"]
    data = QCOW + b"replacement"
    path.write_bytes(data)
    appliance = SimpleNamespace(
        images=[{"filename": path.name, "md5sum": hashlib.md5(data, usedforsecurity=False).hexdigest()}]
    )
    async with AsyncSession(inventory.engine, expire_on_commit=False) as session:
        await ApplianceManager()._find_appliance_version_images(
            appliance, {"images": {"hda_disk_image": path.name}}, ImagesRepository(session), str(path.parent)
        )
    assert (await rows(inventory))[0]["image_id"] == old_id
    appliance.images[0]["md5sum"] = "0" * 32
    async with AsyncSession(inventory.engine, expire_on_commit=False) as session:
        with pytest.raises(ControllerError, match="checksum"):
            await ApplianceManager()._find_appliance_version_images(
                appliance, {"images": {"hda_disk_image": path.name}}, ImagesRepository(session), str(path.parent)
            )


async def test_legacy_path_spelling_preserves_identity(inventory, config):
    path = image_file(config)
    legacy_path = str(path.parent) + os.sep + "." + os.sep + path.name
    async with AsyncSession(inventory.engine, expire_on_commit=False) as session:
        original = await ImagesRepository(session).add_image(path.name, "qemu", len(QCOW), legacy_path, "0" * 32, "md5")
        original_id = original.image_id
    await scan(inventory)
    images = await rows(inventory)
    assert len(images) == 1
    assert images[0]["image_id"] == original_id
    assert images[0]["path"] == legacy_path
    assert images[0]["checksum"] == hashlib.md5(QCOW, usedforsecurity=False).hexdigest()


async def test_root_disappearing_during_scan_does_not_mark_images_missing(inventory, config):
    first = image_file(config, "QEMU/first.qcow2")
    image_file(config, "QEMU/second.qcow2")
    await scan(inventory)
    first.unlink()
    root = config.settings.Server.images_path
    original = inventory._file

    async def disconnect_root(*args):
        await original(*args)
        os.rename(root, root + "-disconnected")

    with patch.object(inventory, "_file", side_effect=disconnect_root):
        result = await scan(inventory)
    assert result["status"] == "partial"
    assert result["counts"]["missing"] == 0
    images = await rows(inventory)
    assert next(image for image in images if image["path"] == str(first))["availability"] == "unavailable"


async def test_polling_recovers_crashed_job_without_starting_a_scan(inventory, config):
    image_file(config)
    job = await scan(inventory)
    async with AsyncSession(inventory.engine) as session:
        row = await session.get(ImageSyncJob, job["job_id"])
        row.status = "running"
        await session.commit()
    assert not config.settings.Server.auto_discover_images
    assert (await inventory.get_job(job["job_id"]))["status"] == "interrupted"


async def test_periodic_scan_recovers_without_watcher_events(inventory, config):
    config.settings.Server.auto_discover_images = True
    image_file(config)
    # Use a short interval and initial wait in the service, leaving asyncio's
    # event-loop scheduling and database operations intact.
    real_sleep = asyncio.sleep

    async def short_sleep(seconds):
        await real_sleep(0.01)

    scans = []
    original_start = inventory.start

    async def observed_start(*args, **kwargs):
        job = await original_start(*args, **kwargs)
        scans.append(job["job_id"])
        return job

    async def missed_event(*args, **kwargs):
        # Consume/close the unused Event.wait coroutine, then simulate a timeout.
        args[0].close()
        await real_sleep(0.01)
        raise asyncio.TimeoutError

    with (
        patch.object(inventory, "_watch", new=AsyncMock()),
        patch.object(inventory, "start", side_effect=observed_start),
        patch("gns3server.services.image_reconciliation.asyncio.sleep", side_effect=short_sleep),
        patch("gns3server.services.image_reconciliation.asyncio.wait_for", side_effect=missed_event),
    ):
        inventory.start_background()
        for _ in range(500):
            if len(scans) >= 2:
                break
            await real_sleep(0.01)
        await inventory.close()
    assert len(scans) >= 2
    assert len(await rows(inventory)) == 1


async def test_unchanged_collection_avoids_hashing_and_keeps_loop_responsive(inventory, config):
    import time

    for index in range(200):
        image_file(config, f"QEMU/bulk/{index}.qcow2", QCOW + b"x" * 65536)
    samples = []
    done = asyncio.Event()

    async def heartbeat():
        previous = time.monotonic()
        while not done.is_set():
            await asyncio.sleep(0.01)
            current = time.monotonic()
            samples.append(current - previous)
            previous = current

    pulse = asyncio.create_task(heartbeat())
    try:
        first = await scan(inventory)
        second = await scan(inventory)
    finally:
        done.set()
        await pulse
    assert first["counts"]["added"] == 200
    assert second["counts"]["unchanged"] == 200
    assert second["counts"]["bytes_hashed"] == 0
    assert len(samples) > 2
    # Generous stall threshold; this checks responsiveness rather than host speed.
    assert max(samples) < 2


async def test_startup_upgrades_unversioned_existing_catalog(inventory, config, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from fastapi import FastAPI

    from gns3server.db.tasks import connect_to_db, disconnect_from_db

    image_file(config)
    await scan(inventory)
    original_id = (await rows(inventory))[0]["image_id"]

    def remove_inventory_schema(connection):
        cfg = Config()
        cfg.set_main_option("script_location", "gns3server:db_migrations")
        cfg.attributes["connection"] = connection
        command.stamp(cfg, "d9e8a2b7c401")
        command.downgrade(cfg, "c7e4a9f1d2b6")
        connection.execute(text("DROP TABLE alembic_version"))

    async with inventory.engine.connect() as connection:
        await connection.run_sync(remove_inventory_schema)
        await connection.commit()
    monkeypatch.setenv("GNS3_DATABASE_URI", str(inventory.engine.url))
    app = FastAPI()
    await connect_to_db(app)
    try:
        restored = (await rows(inventory))[0]
        assert restored["image_id"] == original_id
        assert restored["availability"] == "unknown"
    finally:
        await disconnect_from_db(app)


@pytest.mark.parametrize("operation", ["delete", "prune"])
@pytest.mark.parametrize("reuse_id", [False, True])
async def test_delete_preserves_replacement_created_while_waiting_for_lock(inventory, config, operation, reuse_id):
    from contextlib import asynccontextmanager

    from sqlalchemy import delete

    from gns3server.api.routes.controller.images import delete_image
    from gns3server.controller.controller_error import ControllerError

    path = image_file(config)
    await scan(inventory)
    original = (await rows(inventory))[0]
    replacement = QCOW + b"replacement uploaded by another request"
    replacement_id = original["image_id"] if reuse_id else original["image_id"] + 100

    @asynccontextmanager
    async def concurrent_replacement(locked_path):
        assert locked_path == str(path)
        async with AsyncSession(inventory.engine) as writer:
            await writer.execute(delete(Image).where(Image.image_id == original["image_id"]))
            path.write_bytes(replacement)
            info = inspect_image_file(str(path))
            info["filename"] = info.pop("image_name")
            writer.add(Image(image_id=replacement_id, **info))
            await writer.commit()
        yield

    module = "gns3server.api.routes.controller.images" if operation == "delete" else "gns3server.db.repositories.images"
    with (
        patch(module + ".image_lock", concurrent_replacement),
        patch(
            "gns3server.api.routes.controller.images.Controller.instance",
            return_value=SimpleNamespace(find_projects_using_image=lambda filename: []),
        ),
    ):
        async with AsyncSession(inventory.engine, expire_on_commit=False) as session:
            repository = ImagesRepository(session)
            if operation == "delete":
                with pytest.raises(ControllerError, match="changed"):
                    await delete_image(str(path), repository)
            else:
                assert await repository.prune_images() == 0
    assert path.read_bytes() == replacement
    assert (await rows(inventory))[0]["image_id"] == replacement_id
