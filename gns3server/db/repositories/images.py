#!/usr/bin/env python
#
# Copyright (C) 2021 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import asyncio
from datetime import datetime, timezone

from typing import Optional, List, Callable, cast
from sqlalchemy import select, delete, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from gns3server.utils.image_inventory import fingerprint, image_lock, normalized_path

from .base import BaseRepository

import gns3server.db.models as models

import logging

log = logging.getLogger(__name__)


class ImagesRepository(BaseRepository):
    def __init__(self, db_session: AsyncSession) -> None:

        super().__init__(db_session)

    async def get_image(self, image_path: str, *, refresh: bool = False) -> Optional[models.Image]:
        """
        Get an image by its path.
        """

        image_dir, image_name = os.path.split(image_path)
        if os.path.isabs(image_path):
            query = select(models.Image).where(models.Image.path == image_path)
        elif image_dir:
            query = select(models.Image).where(
                models.Image.filename == image_name, models.Image.path.endswith(os.sep + image_path, autoescape=True)
            )
        else:
            query = select(models.Image).where(models.Image.filename == image_name)
        result = await self._db_session.execute(query.execution_options(populate_existing=refresh))
        return result.scalars().one_or_none()

    async def get_image_by_checksum(self, checksum: str, image_dir: Optional[str] = None) -> Optional[models.Image]:
        """
        Get an image by its checksum.
        """

        query = select(models.Image).where(models.Image.checksum == checksum).order_by(models.Image.image_id)
        result = await self._db_session.execute(query)
        for image in result.scalars().all():
            if image_dir and normalized_path(os.path.dirname(image.path)) != normalized_path(image_dir):
                continue
            if await self.is_usable(image):
                return image
        return None

    async def is_usable(self, image: models.Image) -> bool:
        """Validate a checksum candidate without trusting stale catalog/sidecar data."""
        from gns3server.utils.images import inspect_image_file, InvalidImageError

        try:
            current = await asyncio.to_thread(fingerprint, image.path)
            if image.availability == "available" and image.file_fingerprint == current:
                return True
            info = await asyncio.to_thread(inspect_image_file, image.path, image.image_type, True)
            return info["checksum"] == image.checksum and info["image_size"] == image.image_size
        except (OSError, InvalidImageError):
            return False

    async def get_images(self, image_type=None, availability=None) -> List[models.Image]:
        """
        Get all images.
        """

        if image_type:
            query = select(models.Image).where(models.Image.image_type == image_type)
        else:
            query = select(models.Image)
        if availability:
            query = query.where(models.Image.availability == availability)
        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def get_image_templates(self, image_id: int) -> List[models.Template]:
        """
        Get all templates that an image belongs to.
        """

        query = select(models.Template).join(models.Template.images).filter(models.Image.image_id == image_id)

        result = await self._db_session.execute(query)
        return list(result.scalars().all())

    async def add_image(
        self, image_name, image_type, image_size, path, checksum, checksum_algorithm, file_fingerprint=None
    ) -> models.Image:
        """
        Create a new image.
        """

        db_image = models.Image(
            image_id=None,
            filename=image_name,
            image_type=image_type,
            image_size=image_size,
            path=path,
            checksum=checksum,
            checksum_algorithm=checksum_algorithm,
            file_fingerprint=file_fingerprint,
            availability="available" if file_fingerprint else "unknown",
        )

        self._db_session.add(db_image)
        try:
            await self._db_session.commit()
        except Exception:
            await self._db_session.rollback()
            raise
        await self._db_session.refresh(db_image)
        return db_image

    async def update_image(self, image_path: str, checksum: str, checksum_algorithm: str) -> Optional[models.Image]:
        """
        Update an image.
        """

        query = (
            update(models.Image)
            .where(models.Image.path == image_path)
            .values(checksum=checksum, checksum_algorithm=checksum_algorithm)
        )

        await self._db_session.execute(query)
        await self._db_session.commit()
        image_db = await self.get_image(image_path)
        if image_db:
            await self._db_session.refresh(image_db)  # force refresh of updated_at value
        return image_db

    async def save_verified_image(self, info: dict) -> Optional[models.Image]:
        """Upsert an exact path, preserving template associations and the image ID.

        Callers coordinate publication/inspection with image_lock(). Each commit
        is short, and a concurrent insert from a legacy caller is retried safely.
        """
        values = dict(info)
        values["filename"] = values.pop("image_name")
        values.update(
            availability="available",
            last_error=None,
            last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None),
            last_verified_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        for attempt in range(2):
            try:
                image = (
                    await self._db_session.execute(
                        select(models.Image)
                        .where(models.Image.path == info["path"])
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one_or_none()
                if image is None:
                    # A legacy spelling (e.g. /images/QEMU/./disk.qcow2) can
                    # refer to the same destination restored by an API upload.
                    candidates = (
                        (
                            await self._db_session.execute(
                                select(models.Image).where(models.Image.filename == values["filename"])
                            )
                        )
                        .scalars()
                        .all()
                    )
                    aliases = [
                        candidate
                        for candidate in candidates
                        if normalized_path(candidate.path) == normalized_path(info["path"])
                    ]
                    if len(aliases) > 1:
                        from sqlalchemy.exc import MultipleResultsFound

                        raise MultipleResultsFound("Ambiguous image path aliases; manual review required")
                    if aliases:
                        image = aliases[0]
                        values["path"] = image.path
                if image is None:
                    image = models.Image(**values)
                    self._db_session.add(image)
                else:
                    for key, value in values.items():
                        setattr(image, key, value)
                await self._db_session.commit()
                await self._db_session.refresh(image)
                return image
            except IntegrityError:
                await self._db_session.rollback()
                if attempt:
                    raise
            except Exception:
                await self._db_session.rollback()
                raise
        return None

    async def delete_image_exact(self, image_id: int) -> bool:
        result = await self._db_session.execute(delete(models.Image).where(models.Image.image_id == image_id))
        await self._db_session.commit()
        return cast(CursorResult, result).rowcount > 0

    async def delete_image(self, image_path: str) -> bool:
        """
        Delete an image.
        """

        image_dir, image_name = os.path.split(image_path)
        if os.path.isabs(image_path):
            query = delete(models.Image).where(models.Image.path == image_path)
        elif image_dir:
            query = (
                delete(models.Image)
                .where(
                    models.Image.filename == image_name,
                    models.Image.path.endswith(os.sep + image_path, autoescape=True),
                )
                .execution_options(synchronize_session=False)
            )
        else:
            query = delete(models.Image).where(models.Image.filename == image_name)
        result = await self._db_session.execute(query)
        await self._db_session.commit()
        return cast(CursorResult, result).rowcount > 0

    async def prune_images(self, skip_images: Optional[list[str]] = None, is_in_use: Optional[Callable] = None) -> int:
        """
        Prune images not attached to any template.
        """

        query = select(models.Image).filter(~models.Image.templates.any())
        result = await self._db_session.execute(query)
        # Snapshot scalar values; commits can expire ORM instances.
        images = [
            (image.image_id, image.filename, image.path, image.checksum, image.file_fingerprint)
            for image in result.scalars().all()
        ]
        images_deleted = 0
        errors = []
        for image_id, filename, path, checksum, file_fingerprint in images:
            if skip_images and filename in skip_images:
                continue
            async with image_lock(path):
                current = await self.get_image(path, refresh=True)
                if current is None or (current.image_id, current.checksum, current.file_fingerprint) != (
                    image_id,
                    checksum,
                    file_fingerprint,
                ):
                    continue  # A concurrent request removed or replaced this image.
                if await self.get_image_templates(image_id) or (is_in_use and is_in_use(filename)):
                    continue
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                except OSError as e:
                    errors.append(f"{path}: {e}")
                    continue
                if await self.delete_image_exact(image_id):
                    images_deleted += 1
        log.info(f"{images_deleted} image(s) have been deleted")
        if errors:
            from gns3server.controller.controller_error import ControllerError

            raise ControllerError("Could not delete image files: " + "; ".join(errors))
        return images_deleted
