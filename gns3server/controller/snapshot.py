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


class Snapshot:
    """
    A snapshot object
    """

    def __init__(self, project, name=None, filename=None):

        assert filename or name, "You need to pass a name or a filename"

        self._id = str(
            uuid.uuid4()
        )  # We don't need to keep id between project loading because they are use only as key for operation like delete, update.. but have no impact on disk
        self._project = project
        if name:
            self._name = name
            self._created_at = datetime.now(timezone.utc).timestamp()
            filename = (
                self._name
                + "_"
                + datetime.fromtimestamp(self._created_at, tz=timezone.utc).replace(tzinfo=None).strftime("%d%m%y_%H%M%S")
                + ".gns3project"
            )
        else:
            self._name = filename.split("_")[0]
            datestring = filename.replace(self._name + "_", "").split(".")[0]
            try:
                self._created_at = (
                    datetime.strptime(datestring, "%d%m%y_%H%M%S").replace(tzinfo=timezone.utc).timestamp()
                )
            except ValueError:
                self._created_at = datetime.now(timezone.utc)
        self._path = os.path.join(project.path, "snapshots", filename)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def path(self):
        return self._path

    @property
    def created_at(self):
        return int(self._created_at)

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
                    await export_project(zstream, self._project, tmpdir, keep_compute_id=True, allow_all_nodes=True)
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
            # delete the current project files
            project_files_path = os.path.join(self._project.path, "project-files")
            if os.path.exists(project_files_path):
                await wait_run_in_executor(shutil.rmtree, project_files_path)
            with open(self._path, "rb") as f:
                project = await import_project(self._project.controller, self._project.id, f, location=self._project.path,
                                               auto_start=self._project.auto_start, auto_open=self._project.auto_open,
                                               auto_close=self._project.auto_close)
        except (OSError, PermissionError) as e:
            raise ControllerError(str(e))
        await project.open()
        self._project.emit_notification("snapshot.restored", self.asdict())
        return self._project

    def asdict(self):
        return {
            "snapshot_id": self._id,
            "name": self._name,
            "created_at": int(self._created_at),
            "project_id": self._project.id,
        }
