#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

import json
import os
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller import Controller
from gns3server.controller.project import Project
from gns3server.controller.snapshot import Snapshot

pytestmark = pytest.mark.asyncio


class TestSnapshotRoutes:
    @pytest_asyncio.fixture
    async def project(self, app: FastAPI, client: AsyncClient, controller: Controller) -> Project:

        u = str(uuid.uuid4())
        params = {"name": "test", "project_id": u}
        await client.post(app.url_path_for("create_project"), json=params)
        controller_project = controller.get_project(u)
        return controller_project

    @pytest_asyncio.fixture
    async def snapshot(self, project: Project):

        controller_snapshot = await project.snapshot("test")
        return controller_snapshot

    async def test_list_snapshots(
        self, app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot
    ) -> None:

        assert snapshot.name == "test"
        response = await client.get(app.url_path_for("get_snapshots", project_id=project.id))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1
        data = response.json()[0]
        assert isinstance(data["created_at"], int)
        assert datetime.fromisoformat(data["created"]) == datetime.fromtimestamp(data["created_at"], tz=UTC)

    async def test_delete_snapshot(
        self, app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot
    ) -> None:

        response = await client.delete(
            app.url_path_for("delete_snapshot", project_id=project.id, snapshot_id=snapshot.id)
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not os.path.exists(snapshot.path)

    async def test_deleting_the_last_snapshot_empties_the_config(
        self, app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot
    ) -> None:
        """
        A config left with a deleted snapshot keeps warning about a missing
        file on every load: the config must be emptied with the last snapshot.
        """

        response = await client.delete(
            app.url_path_for("delete_snapshot", project_id=project.id, snapshot_id=snapshot.id)
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        with open(project._snapshot_conf_path, encoding="utf-8") as f:
            assert json.load(f) == []

        # the ghost entry is gone for good: a reload stays silent and empty
        project._load_snapshot_config()
        assert list(project._snapshots.values()) == []

    async def test_ghost_snapshot_entry_is_dropped_from_the_config(
        self, app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot
    ) -> None:
        """
        An entry whose snapshot file was removed outside the API is skipped
        on load, and the config is rewritten without it.
        """

        os.remove(snapshot.path)
        # reset() clears the in-memory snapshots before reloading, like an open
        project._snapshots = {}
        project._load_snapshot_config()
        assert list(project._snapshots.values()) == []

        with open(project._snapshot_conf_path, encoding="utf-8") as f:
            assert json.load(f) == []

    async def test_restore_snapshot(
        self, app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot
    ) -> None:

        response = await client.post(
            app.url_path_for("restore_snapshot", project_id=project.id, snapshot_id=snapshot.id)
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == project.name

    async def test_create_snapshot(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        response = await client.post(app.url_path_for("create_snapshot", project_id=project.id), json={"name": "snap1"})
        assert response.status_code == status.HTTP_201_CREATED
        assert len(os.listdir(os.path.join(project.path, "snapshots"))) == 2
        data = response.json()
        assert isinstance(data["created_at"], int)
        assert datetime.fromisoformat(data["created"]) == datetime.fromtimestamp(data["created_at"], tz=UTC)

    async def test_create_snapshot_with_description(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        response = await client.post(
            app.url_path_for("create_snapshot", project_id=project.id),
            json={"name": "snap1", "description": "before adding the second node"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["description"] == "before adding the second node"

        # the description must survive a reload of the snapshot config file
        project._load_snapshot_config()
        assert project.get_snapshot(data["snapshot_id"]).description == "before adding the second node"

    async def test_update_snapshot(
        self, app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot
    ) -> None:

        response = await client.put(
            app.url_path_for("update_snapshot", project_id=project.id, snapshot_id=snapshot.id),
            json={"description": "before adding the second node"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["description"] == "before adding the second node"

        # the new description must be saved in the snapshot config file
        project._load_snapshot_config()
        assert project.get_snapshot(snapshot.id).description == "before adding the second node"

    async def test_update_snapshot_reset_description(
        self, app: FastAPI, client: AsyncClient, project: Project, snapshot: Snapshot
    ) -> None:

        response = await client.put(
            app.url_path_for("update_snapshot", project_id=project.id, snapshot_id=snapshot.id),
            json={"description": ""},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["description"].startswith("Snapshot 'test' taken on ")

    async def test_update_snapshot_not_found(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        response = await client.put(
            app.url_path_for("update_snapshot", project_id=project.id, snapshot_id=str(uuid.uuid4())),
            json={"description": "test"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_snapshot_schema_timestamps(self, app: FastAPI) -> None:

        schemas = app.openapi()["components"]["schemas"]
        assert schemas["Snapshot"]["properties"]["created"]["format"] == "date-time"
        assert schemas["Snapshot"]["properties"]["created_at"]["type"] == "integer"
        assert schemas["Snapshot"]["properties"]["created_at"]["deprecated"] is True
        for field in ("created_at", "modified_at"):
            assert {"type": "string", "format": "date-time"} in schemas["NodeFile"]["properties"][field]["anyOf"]
