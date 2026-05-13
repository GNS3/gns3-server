#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
import uuid
import shutil
import tempfile
import aiofiles
import zipfile
import time
from datetime import datetime, timezone

from .controller_error import ControllerError
from ..utils.asyncio import wait_run_in_executor
from ..utils.asyncio import aiozipstream
from .export_project import export_project
from .import_project import import_project

import logging

log = logging.getLogger(__name__)


# Used to extract the date and time from the filename
FILENAME_DATETIME_FORMAT = "%d%m%y_%H%M%S"

# Used to create a description of the snapshot with a human-readable date and time
DESCRIPTION_DATETIME_FORMAT = "%Y-%m-%d at %H:%M:%S"

class Snapshot:
    """
    A snapshot object
    """

    def __init__(self, project, snapshot_id=None, name=None, filename=None, created_at=None, description=None):

        assert filename or name, "You need to pass a name or a filename"

        if snapshot_id:
            self._id = snapshot_id
        else:
            self._id = str(uuid.uuid4())

        self._project = project
        if name:
            self._name = name

            if created_at:
                self._created_at = created_at
            else:
                self._created_at = int(datetime.now(timezone.utc).timestamp())
            if not filename:
                filename = self._name + ".gns3snapshot"
        else:
            self._name = filename.rsplit("_", 2)[0]
            datestring = filename.replace(self._name + "_", "").split(".")[0]
            self._created_at = int(datetime.strptime(datestring, FILENAME_DATETIME_FORMAT).replace(tzinfo=timezone.utc).timestamp())

        if not description:
            date = datetime.fromtimestamp(self._created_at, tz=timezone.utc).replace(tzinfo=None).strftime(DESCRIPTION_DATETIME_FORMAT)
            description = "Snapshot '{}' taken on {}".format(self._name, date)

        self._description = description
        self._filename = filename
        self._path = os.path.join(project.path, "snapshots", filename)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    @property
    def path(self):
        return self._path

    @property
    def created_at(self):
        return self._created_at

    async def create(self):
        """
        Create the snapshot
        """

        if os.path.exists(self.path):
            raise ControllerError(f"The snapshot file '{self.name}' already exists")

        snapshot_directory = os.path.join(self._project.path, "snapshots")
        try:
            os.makedirs(snapshot_directory, exist_ok=True)
        except OSError as e:
            raise ControllerError(f"Could not create the snapshot directory '{snapshot_directory}': {e}")

        try:
            begin = time.time()
            with tempfile.TemporaryDirectory(dir=snapshot_directory) as tmpdir:
                # Do not compress the snapshots
                with aiozipstream.ZipFile(compression=zipfile.ZIP_STORED) as zstream:
                    await export_project(zstream, self._project, tmpdir, keep_compute_ids=True, allow_all_nodes=True)
                    async with aiofiles.open(self.path, "wb") as f:
                        async for chunk in zstream:
                            await f.write(chunk)
            log.info(f"Snapshot '{self.name}' created in {time.time() - begin:.4f} seconds")
        except (ValueError, OSError, RuntimeError) as e:
            raise ControllerError(f"Could not create snapshot file '{self.path}': {e}")

    async def restore(self):
        """
        Restore the snapshot
        """

        await self._project.delete_on_computes()
        # We don't send close notification to clients because the close / open dance is purely internal
        await self._project.close(ignore_notification=True)

        try:
            begin = time.time()
            # delete the current project files
            project_files_path = os.path.join(self._project.path, "project-files")
            if os.path.exists(project_files_path):
                await wait_run_in_executor(shutil.rmtree, project_files_path, ignore_errors=True)
            with open(self._path, "rb") as f:
                project = await import_project(
                    self._project.controller,
                    self._project.id,
                    f,
                    location=self._project.path,
                    auto_start=self._project.auto_start,
                    auto_open=self._project.auto_open,
                    auto_close=self._project.auto_close
                )
            log.info("Snapshot '{}' restored in {:.4f} seconds".format(self.name, time.time() - begin))
        except (OSError, PermissionError) as e:
            raise ControllerError(str(e))
        await project.open()
        self._project.emit_notification("snapshot.restored", self.asdict())
        return self._project

    def asdict(self):
        return {
            "snapshot_id": self._id,
            "name": self._name,
            "created_at": self._created_at,
            "description": self._description,
            "filename": self._filename,
            "project_id": self._project.id
        }
