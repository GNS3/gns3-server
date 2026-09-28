"""Recoverable controller image inventory, shared by manual and automatic sync."""

import asyncio
import logging
import os
import stat
import threading
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from gns3server.config import Config
from gns3server.db.models import Image, ImageSyncJob
from gns3server.db.repositories.images import ImagesRepository
from gns3server.utils.image_inventory import (
    ImageLock,
    ImageLockBusy,
    contained_path,
    fingerprint,
    image_lock,
    normalized_path,
)
from gns3server.utils.images import inspect_image_file, InvalidImageError, ImageChangedError

log = logging.getLogger(__name__)
COUNTERS = (
    "scanned",
    "added",
    "updated",
    "unchanged",
    "missing",
    "unavailable",
    "invalid",
    "deferred",
    "out_of_scope",
    "errors",
    "bytes_hashed",
)
RAW_EXTENSIONS = {".raw", ".img", ".iso", ".fd", ".vhd", ".vdi", ".bin"}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ignored(name):
    return name.startswith(".") or name.endswith((".tmp", ".md5sum"))


def configured_roots():
    settings = Config.instance().settings.Server
    roots = sorted({normalized_path(p) for p in [settings.images_path, *settings.additional_images_paths]})
    # Keep parent roots only, avoiding duplicate scans and conflicting absence passes.
    return [root for root in roots if not any(root != other and contained_path(root, other) for other in roots)]


def root_identity(root):
    info = os.stat(root)
    # Opening the directory tests readability, not just existence.
    with os.scandir(root):
        pass
    return info.st_dev, info.st_ino, os.path.realpath(root)


def enumerate_root(root):
    """Observe a root without creating directories or silently dropping failures."""
    files, errors = {}, []
    try:
        root_stat = os.stat(root)
        if not stat.S_ISDIR(root_stat.st_mode):
            raise NotADirectoryError(root)
        for directory, dirs, names in os.walk(
            root,
            onerror=lambda e: errors.append({"path": str(e.filename or root), "reason": str(e)}),
            followlinks=False,
        ):
            dirs[:] = [
                name
                for name in dirs
                if not ignored(name)
                and name not in ("lib", "lib64")
                and not os.path.islink(os.path.join(directory, name))
            ]
            for name in names:
                if ignored(name):
                    continue
                path = normalized_path(os.path.join(directory, name))
                try:
                    files[path] = fingerprint(path)
                except OSError as e:
                    errors.append({"path": path, "reason": str(e)})
        # A mount/root replacement during traversal makes the absence pass unsafe.
        after = os.stat(root)
        if (root_stat.st_dev, root_stat.st_ino) != (after.st_dev, after.st_ino):
            errors.append({"path": root, "reason": "Image root changed during scan"})
    except OSError as e:
        errors.append({"path": root, "reason": str(e)})
    return files, errors


class InventoryEvents(FileSystemEventHandler):
    def __init__(self, loop, dirty):
        self.loop, self.dirty = loop, dirty
        self._pending = False
        self._lock = threading.Lock()

    def _mark_dirty(self):
        with self._lock:
            self._pending = False
        self.dirty.set()

    def on_any_event(self, event):
        if event.event_type not in ("created", "modified", "closed", "deleted", "moved"):
            return
        paths = [event.src_path, getattr(event, "dest_path", "")]
        if any(path and not ignored(os.path.basename(path)) for path in paths):
            # A single dirty bit coalesces events with bounded memory, including
            # directory renames and bursts. The next scan observes current state.
            with self._lock:
                if self._pending:
                    return
                self._pending = True
            self.loop.call_soon_threadsafe(self._mark_dirty)


class ImageReconciliationService:
    def __init__(self, engine, settle_seconds=1.0):
        self.engine = engine
        self.settle_seconds = settle_seconds
        self.task = None
        self.scheduler = None
        self.observer = None
        self.dirty = asyncio.Event()
        self.stopping = threading.Event()
        self._watched_roots = None
        self._catalog_paths = {}
        self._ambiguous_paths = set()

    async def start(self, dry_run=False, force_checksum=False):
        if self.stopping.is_set():
            raise ImageLockBusy("Image synchronization is shutting down")
        lock = ImageLock("image-inventory", wait=False)
        await lock.__aenter__()
        try:
            async with AsyncSession(self.engine, expire_on_commit=False) as session:
                # The OS lock proves no previous worker using this catalog is
                # active. Recover jobs abandoned by a crash before admitting one.
                await session.execute(
                    update(ImageSyncJob)
                    .where(ImageSyncJob.status.in_(["queued", "running"]))
                    .values(status="interrupted", finished_at=utcnow())
                )
                job = ImageSyncJob(
                    job_id=str(uuid.uuid4()),
                    status="queued",
                    dry_run=dry_run,
                    force_checksum=force_checksum,
                    counts=dict.fromkeys(COUNTERS, 0),
                    errors=[],
                )
                session.add(job)
                # Bound history; active jobs are never removed.
                old_jobs = (
                    select(ImageSyncJob.job_id)
                    .where(ImageSyncJob.status.notin_(["queued", "running"]))
                    .order_by(ImageSyncJob.created_at.desc())
                    .offset(99)
                )
                await session.execute(delete(ImageSyncJob).where(ImageSyncJob.job_id.in_(old_jobs)))
                await session.commit()
                await session.refresh(job)
                result = job.asdict()
            self.task = asyncio.create_task(self._run(result, lock), name="image-inventory-sync")
            self.task.add_done_callback(self._finished)
            return result
        except BaseException:
            await lock.__aexit__()
            raise

    @staticmethod
    def _finished(task):
        if not task.cancelled() and task.exception() is not None:
            log.error("Could not persist image synchronization outcome: %s", task.exception())

    async def get_job(self, job_id, offset=0, limit=100):
        # A client can resume polling after a restart even with automatic scans
        # disabled. Do not leave an abandoned job looking permanently active.
        try:
            async with ImageLock("image-inventory", wait=False):
                async with AsyncSession(self.engine) as session:
                    await session.execute(
                        update(ImageSyncJob)
                        .where(ImageSyncJob.status.in_(["queued", "running"]))
                        .values(status="interrupted", finished_at=utcnow())
                    )
                    await session.commit()
        except ImageLockBusy:
            pass
        async with AsyncSession(self.engine) as session:
            job = await session.get(ImageSyncJob, job_id)
            if job is None:
                return None
            result = job.asdict()
            result["errors"] = result["errors"][offset : offset + limit]
            return result

    async def _persist(self, job):
        async with AsyncSession(self.engine) as session:
            await session.execute(
                update(ImageSyncJob)
                .where(ImageSyncJob.job_id == job["job_id"])
                .values(
                    status=job["status"],
                    counts=dict(job["counts"]),
                    errors=list(job["errors"]),
                    finished_at=job.get("finished_at"),
                )
            )
            await session.commit()

    def _error(self, job, path, reason):
        job["counts"]["errors"] += 1
        # The total count remains accurate even when detailed errors are capped.
        if len(job["errors"]) < 1000:
            job["errors"].append({"path": path, "reason": str(reason)})

    async def _inspect(self, path, expected, allow_raw):
        worker = asyncio.create_task(asyncio.to_thread(inspect_image_file, path, expected, allow_raw, self.stopping))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            self.stopping.set()
            try:
                await worker
            except (OSError, InvalidImageError):
                pass
            raise

    async def _state(self, row, availability, reason, dry_run):
        if row is None or dry_run:
            return
        async with AsyncSession(self.engine) as session:
            # Revision guard for legacy writers not yet taking the path lock.
            await session.execute(
                update(Image)
                .where(
                    Image.image_id == row["image_id"],
                    Image.path == row["path"],
                    Image.file_fingerprint == row["file_fingerprint"],
                    Image.checksum == row["checksum"],
                )
                .values(availability=availability, last_error=str(reason))
            )
            await session.commit()

    async def _row(self, path):
        async with AsyncSession(self.engine) as session:
            stored = self._catalog_paths.get(normalized_path(path), path)
            row = (await session.execute(select(Image).where(Image.path.in_([stored, path])))).scalar_one_or_none()
            return row.asdict() if row else None

    async def _file(self, path, observed, job, root):  # noqa: C901 - keep per-file outcomes under one path lock
        if path in self._ambiguous_paths:
            job["counts"]["deferred"] += 1
            return
        async with image_lock(path):
            row = await self._row(path)
            counts = job["counts"]
            counts["scanned"] += 1
            try:
                if not contained_path(os.path.realpath(path), root):
                    raise OSError("Image path resolves outside its configured root")
                current = await asyncio.to_thread(fingerprint, path)
                if current != observed:
                    raise ImageChangedError("File changed during settling interval")
                if (
                    row
                    and row["availability"] == "available"
                    and row["file_fingerprint"] == current
                    and not job["force_checksum"]
                ):
                    counts["unchanged"] += 1
                    return
                expected = row["image_type"] if row else None
                main_root = normalized_path(Config.instance().settings.Server.images_path)
                if not expected and contained_path(path, main_root):
                    component = os.path.relpath(path, main_root).split(os.sep)[0]
                    expected = {"QEMU": "qemu", "IOS": "ios", "IOU": "iou"}.get(component)
                allow_raw = Config.instance().settings.Server.allow_raw_images and (
                    expected == "qemu"
                    or (expected in (None, "qemu") and os.path.splitext(path)[1].lower() in RAW_EXTENSIONS)
                )
                info = await self._inspect(path, expected, allow_raw)
                if row:
                    # Preserve legacy path spelling as well as image identity.
                    info["path"] = row["path"]
                counts["bytes_hashed"] += info["image_size"]
                if self.stopping.is_set():
                    raise asyncio.CancelledError
                if await asyncio.to_thread(fingerprint, path) != info["file_fingerprint"]:
                    raise ImageChangedError("File changed before catalog update")
                if not job["dry_run"]:
                    # Do not leave stale sidecars for legacy compute consumers.
                    try:
                        os.unlink(path + ".md5sum")
                    except FileNotFoundError:
                        pass
                    except OSError as e:
                        self._error(job, path + ".md5sum", e)
                    async with AsyncSession(self.engine, expire_on_commit=False) as session:
                        await ImagesRepository(session).save_verified_image(info)
                counts["updated" if row else "added"] += 1
            except ImageChangedError as e:
                counts["deferred"] += 1
                await self._state(row, "unavailable", e, job["dry_run"])
            except InvalidImageError as e:
                counts["invalid"] += 1
                await self._state(row, "invalid", e, job["dry_run"])
                self._error(job, path, e)
            except OSError as e:
                if self.stopping.is_set():
                    raise asyncio.CancelledError from e
                counts["unavailable"] += 1
                await self._state(row, "unavailable", e, job["dry_run"])
                self._error(job, path, e)

    async def _run(self, job, lock):  # noqa: C901 - one job owns root health, progress and lock lifetime
        job["status"] = "running"
        try:
            await self._persist(job)
            async with AsyncSession(self.engine) as session:
                paths = (await session.execute(select(Image.path))).scalars().all()
            self._catalog_paths = {}
            self._ambiguous_paths = set()
            roots = configured_roots()
            for path in paths:
                normalized = normalized_path(path)
                if not any(contained_path(path, root) for root in roots):
                    job["counts"]["out_of_scope"] += 1
                    self._error(job, path, "Catalog path is outside the configured image directories; record retained")
                if normalized in self._catalog_paths:
                    self._ambiguous_paths.add(normalized)
                    self._error(job, path, "Multiple catalog paths resolve to the same image; manual review required")
                self._catalog_paths[normalized] = path
            for root in roots:
                if self.stopping.is_set():
                    raise asyncio.CancelledError
                resolved_root = os.path.realpath(root)
                try:
                    identity = await asyncio.to_thread(root_identity, root)
                except OSError:
                    identity = None
                files, errors = await asyncio.to_thread(enumerate_root, root)
                if resolved_root != os.path.realpath(root):
                    errors.append({"path": root, "reason": "Image root target changed during scan"})
                for error in errors:
                    self._error(job, error["path"], error["reason"])
                # One settling wait per root, not one per large image collection.
                if files and self.settle_seconds:
                    await asyncio.sleep(self.settle_seconds)
                for path, observed in files.items():
                    if self.stopping.is_set():
                        raise asyncio.CancelledError
                    try:
                        await self._file(path, observed, job, resolved_root)
                    except Exception as e:
                        self._error(job, path, e)
                        log.warning("Could not reconcile image %s: %s", path, e)
                    if job["counts"]["scanned"] % 25 == 0:
                        await self._persist(job)
                try:
                    if identity != await asyncio.to_thread(root_identity, root):
                        raise OSError("Image root changed during reconciliation")
                except OSError as e:
                    errors.append({"path": root, "reason": str(e)})
                    self._error(job, root, e)
                async with AsyncSession(self.engine) as session:
                    rows = [image.asdict() for image in (await session.execute(select(Image))).scalars()]
                for row in rows:
                    if self.stopping.is_set():
                        raise asyncio.CancelledError
                    path = row["path"]
                    if (
                        not contained_path(path, root)
                        or normalized_path(path) in files
                        or normalized_path(path) in self._ambiguous_paths
                    ):
                        continue
                    async with image_lock(path):
                        row = await self._row(path)
                        if row is None:
                            continue
                        if errors:
                            job["counts"]["unavailable"] += 1
                            await self._state(
                                row, "unavailable", "Image root was not completely scanned", job["dry_run"]
                            )
                            continue
                        try:
                            if not contained_path(os.path.realpath(path), resolved_root):
                                raise OSError("Image path resolves outside its configured root")
                            await asyncio.to_thread(fingerprint, path)
                        except FileNotFoundError:
                            try:
                                if identity != await asyncio.to_thread(root_identity, root):
                                    raise OSError("Image root changed during reconciliation")
                            except OSError as e:
                                job["counts"]["unavailable"] += 1
                                await self._state(row, "unavailable", e, job["dry_run"])
                                self._error(job, root, e)
                            else:
                                job["counts"]["missing"] += 1
                                await self._state(row, "missing", "Image file is missing", job["dry_run"])
                        except OSError as e:
                            job["counts"]["unavailable"] += 1
                            await self._state(row, "unavailable", e, job["dry_run"])
                            self._error(job, path, e)
            if self.stopping.is_set():
                raise asyncio.CancelledError
            job["status"] = "partial" if job["counts"]["errors"] or job["counts"]["deferred"] else "completed"
        except asyncio.CancelledError:
            job["status"] = "cancelled"
        except Exception as e:
            job["status"] = "failed"
            self._error(job, "", e)
            log.exception("Image reconciliation failed")
        finally:
            job["finished_at"] = utcnow()
            try:
                await self._persist(job)
            finally:
                await lock.__aexit__()

    async def _watch(self):
        roots = configured_roots() if Config.instance().settings.Server.auto_discover_images else []
        # Include availability in the signature so newly mounted roots get watched.
        roots = [root for root in roots if os.path.isdir(root)]
        if roots == self._watched_roots:
            return
        if self.observer:
            self.observer.stop()
            await asyncio.to_thread(self.observer.join)
            self.observer = None
        self._watched_roots = roots
        if roots:
            observer = Observer()
            handler = InventoryEvents(asyncio.get_running_loop(), self.dirty)
            try:
                for root in roots:
                    observer.schedule(handler, root, recursive=True)
                observer.start()
                self.observer = observer
            except OSError:
                observer.stop()
                if observer.is_alive():
                    await asyncio.to_thread(observer.join)
                self._watched_roots = None
                log.warning("Image watcher unavailable; periodic scanning remains active", exc_info=True)

    async def _automatic(self):
        await asyncio.sleep(5)
        while not self.stopping.is_set():
            try:
                await self._watch()
                self.dirty.clear()
                if Config.instance().settings.Server.auto_discover_images:
                    try:
                        await self.start()
                        await asyncio.shield(self.task)
                    except ImageLockBusy:
                        pass
                try:
                    await asyncio.wait_for(self.dirty.wait(), Config.instance().settings.Server.image_sync_interval)
                    await asyncio.sleep(1)  # debounce bursts of file/directory events
                except asyncio.TimeoutError:
                    pass
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("Automatic image synchronization failed; will retry")
                await asyncio.sleep(10)

    def start_background(self):
        self.scheduler = asyncio.create_task(self._automatic(), name="image-inventory-scheduler")

    async def close(self):
        self.stopping.set()
        if self.scheduler:
            self.scheduler.cancel()
            await asyncio.gather(self.scheduler, return_exceptions=True)
        if self.observer:
            self.observer.stop()
            await asyncio.to_thread(self.observer.join)
            self.observer = None
        if self.task and not self.task.done():
            # Cooperative cancellation also covers a task not yet entered; its
            # finally block must run to release the already-acquired job lock.
            await asyncio.gather(self.task, return_exceptions=True)


def get_image_reconciliation_service(app):
    service = getattr(app.state, "image_reconciliation", None)
    if service is None:
        service = ImageReconciliationService(app.state._db_engine)
        app.state.image_reconciliation = service
    return service
