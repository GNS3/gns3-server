#
# Copyright (C) 2026 GNS3 Technologies Inc.
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

import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gns3server import schemas
from gns3server.api.routes.controller.controller import controller_http_notifications, controller_ws_notifications
from gns3server.api.routes.controller.dependencies.rbac import has_privilege_on_websocket
from gns3server.api.routes.controller.projects import (
    project_marker_ws_notifications,
    project_ws_notifications,
)
from gns3server.db.models import User
from gns3server.db.repositories.rbac import RbacRepository
from gns3server.schemas.controller.rbac import ACECreate
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY
from gns3server.utils.notification_queue import NotificationQueue

STREAM_PATHS = ["/v3/notifications", "/v3/projects/{project_id}/notifications"]


class TestNotificationOpenAPI:
    def test_notification_schema_in_spec(self, app: FastAPI) -> None:

        spec = app.openapi()
        schema = spec["components"]["schemas"]["Notification"]
        assert set(schema["required"]) == {"action", "event"}
        assert {"action", "event", "project_id", "compute_id"} <= set(schema["properties"])
        action_schema = spec["components"]["schemas"]["NotificationAction"]
        assert {"ping", "node.created", "node.updated", "link.created", "marker.match"} <= set(action_schema["enum"])

    @pytest.mark.parametrize("path", STREAM_PATHS)
    def test_stream_responses_reference_schema(self, app: FastAPI, path: str) -> None:

        content = app.openapi()["paths"][path]["get"]["responses"]["200"]["content"]
        assert list(content) == ["application/x-ndjson"]
        assert content["application/x-ndjson"]["schema"] == {"$ref": "#/components/schemas/Notification"}


class TestNotificationSchema:
    def test_ping(self) -> None:

        message = {
            "action": "ping",
            "event": {"cpu_usage_percent": 1.5, "memory_usage_percent": 40.0, "disk_usage_percent": 10.0},
        }
        notification = schemas.Notification.model_validate(message)
        assert notification.action == schemas.NotificationAction.ping

    def test_unknown_action(self) -> None:

        with pytest.raises(ValidationError):
            schemas.Notification.model_validate({"action": "unknown.action", "event": {}})

    def test_optional_ids(self) -> None:

        project_id = str(uuid.uuid4())
        notification = schemas.Notification.model_validate(
            {"action": "log.info", "event": {"message": "hello"}, "project_id": project_id, "compute_id": "local"}
        )
        assert str(notification.project_id) == project_id
        assert notification.compute_id == "local"

    def test_generic_event(self) -> None:

        notification = schemas.Notification.model_validate(
            {"action": "template.deleted", "event": {"template_id": str(uuid.uuid4())}}
        )
        assert notification.action == schemas.NotificationAction.template_deleted

    @pytest.mark.asyncio
    async def test_queue_message_matches_schema(self) -> None:

        queue = NotificationQueue()
        queue.put_nowait(("log.warning", {"message": "disk space is low"}, {"compute_id": "local"}))
        await queue.get_json(5)
        message = json.loads(await queue.get_json(5))
        notification = schemas.Notification.model_validate(message)
        assert notification.action == schemas.NotificationAction.log_warning
        assert notification.compute_id == "local"


def _fake_websocket(app: FastAPI, path: str = "/v3/notifications/ws") -> MagicMock:

    websocket = MagicMock()
    websocket.app = app
    websocket.url = SimpleNamespace(path=path)
    websocket.client = SimpleNamespace(host="127.0.0.1", port=1000)
    websocket.send_text = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.close = AsyncMock()
    return websocket


class TestNotificationWebSocketShutdown:
    """Notification WebSockets must stop when the server is shutting down.

    Otherwise uvicorn has to wait for them during graceful shutdown.
    """

    # Do not use monkeypatch.setattr on app.state: Starlette's State keeps
    # attributes in an internal dict, not in the instance __dict__, so pytest
    # 9.2+ cannot read back the old value and its teardown deletes the
    # attribute for the rest of the test session.

    @pytest.mark.asyncio
    async def test_controller_ws_stops_when_app_is_exiting(self, app: FastAPI) -> None:

        app.state.exiting = True
        try:
            websocket = _fake_websocket(app)
            await asyncio.wait_for(controller_ws_notifications(websocket, current_user=MagicMock()), timeout=1)
            websocket.send_text.assert_not_awaited()
        finally:
            app.state.exiting = False

    @pytest.mark.asyncio
    async def test_project_ws_stops_when_app_is_exiting(self, app: FastAPI, project) -> None:

        project.auto_close = False
        app.state.exiting = True
        try:
            websocket = _fake_websocket(app)
            await asyncio.wait_for(project_ws_notifications(project.id, websocket, current_user=MagicMock()), timeout=1)
            websocket.send_text.assert_not_awaited()
        finally:
            app.state.exiting = False

    @pytest.mark.asyncio
    async def test_marker_ws_stops_when_app_is_exiting(self, app: FastAPI, project) -> None:

        app.state.exiting = True
        try:
            websocket = _fake_websocket(app)
            await asyncio.wait_for(
                project_marker_ws_notifications(project.id, websocket, current_user=MagicMock()), timeout=1
            )
            websocket.send_text.assert_not_awaited()
        finally:
            app.state.exiting = False


class TestNotificationStreamPrivilege:
    """
    The global controller notification stream requires Notification.Audit.
    No default ACE carries the privilege, so out of the box only superadmins
    receive the stream; an explicit ACE on /notifications grants it, and a
    stream open when the ACE is removed is closed on the next ping.

    Real WebSocket connections are exercised by the authentication test in
    tests/api/routes/test_routes.py and by the e2e suite: here the privilege
    dependency and the send loop are called directly.
    """

    @staticmethod
    def _token(user: User) -> str:

        return auth_service.create_access_token(user.username, secret_key=DEFAULT_JWT_SECRET_KEY)

    @pytest.mark.asyncio
    async def test_http_stream_denied_without_privilege(
        self, app: FastAPI, client: AsyncClient, test_user: User
    ) -> None:

        response = await client.get(
            app.url_path_for("controller_http_notifications"),
            headers={"Authorization": f"Bearer {self._token(test_user)}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_http_stream_yields_ping_for_superadmin(self, app: FastAPI) -> None:

        # the HTTP transport of the test client buffers the whole response, so
        # an endless NDJSON stream is driven through its body iterator instead
        request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1", port=123))
        superadmin = User(username="admin", is_superadmin=True)
        response = await controller_http_notifications(request, current_user=superadmin)
        line = await response.body_iterator.__anext__()
        # the first message out of the queue is always a ping
        assert json.loads(line.decode())["action"] == "ping"
        await response.body_iterator.aclose()

    @pytest.mark.asyncio
    async def test_ws_dependency_denies_without_privilege(
        self, app: FastAPI, db_session: AsyncSession, test_user: User
    ) -> None:

        websocket = _fake_websocket(app)
        rbac_repo = RbacRepository(db_session)
        dependency = has_privilege_on_websocket("Notification.Audit")

        result = await dependency(websocket, current_user=test_user, rbac_repo=rbac_repo)

        # the socket is already accepted at this point: the denial is reported
        # as a log.error notification and a 1008 close, not an HTTPException
        assert result is None
        message = websocket.send_json.await_args.args[0]
        assert message["action"] == "log.error"
        assert "privilege Notification.Audit is required" in message["event"]["message"]
        websocket.close.assert_awaited_once_with(code=1008)

    @pytest.mark.asyncio
    async def test_ws_dependency_allows_superadmin(self, app: FastAPI) -> None:

        websocket = _fake_websocket(app)
        superadmin = User(username="admin", is_superadmin=True)
        dependency = has_privilege_on_websocket("Notification.Audit")

        result = await dependency(websocket, current_user=superadmin, rbac_repo=MagicMock())

        assert result is superadmin
        websocket.send_json.assert_not_awaited()
        websocket.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ws_dependency_allows_with_explicit_ace(
        self, app: FastAPI, db_session: AsyncSession, test_user: User
    ) -> None:

        rbac_repo = RbacRepository(db_session)
        role = await rbac_repo.get_role_by_name("Administrator")  # holds every privilege
        await rbac_repo.create_ace(
            ACECreate(
                path="/notifications", ace_type="user", propagate=True, user_id=test_user.user_id, role_id=role.role_id
            )
        )

        websocket = _fake_websocket(app)
        dependency = has_privilege_on_websocket("Notification.Audit")
        result = await dependency(websocket, current_user=test_user, rbac_repo=rbac_repo)

        assert result is test_user
        websocket.send_json.assert_not_awaited()
        websocket.close.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ws_closed_after_privilege_revoked(
        self, app: FastAPI, db_session: AsyncSession, db_engine: AsyncEngine
    ) -> None:

        # a dedicated user: the class database is shared, and an ACE left by
        # another test for another user must not keep this stream alive
        db_user = User(username="revoke-user", hashed_password=auth_service.hash_password("password"))
        db_session.add(db_user)
        await db_session.commit()
        await db_session.refresh(db_user)  # the id must be a UUID, not the str default

        rbac_repo = RbacRepository(db_session)
        role = await rbac_repo.get_role_by_name("Administrator")
        ace = await rbac_repo.create_ace(
            ACECreate(
                path="/notifications", ace_type="user", propagate=True, user_id=db_user.user_id, role_id=role.role_id
            )
        )

        async def send_then_revoke(text: str) -> None:
            # revoke right after the first frame went out: the next iteration
            # of the send loop re-checks the privilege and closes the socket
            await rbac_repo.delete_ace(ace.asdict()["ace_id"])

        websocket = _fake_websocket(app)
        websocket.send_text = AsyncMock(side_effect=send_then_revoke)
        # the re-check reloads the snapshot through its own session: point the
        # app at the test engine (no lifespan runs under the test transport)
        app.state._db_engine = db_engine
        app.state.exiting = False
        try:
            await asyncio.wait_for(controller_ws_notifications(websocket, current_user=db_user), timeout=10)
        finally:
            app.state._db_engine = None

        # exactly one frame (the initial ping) was sent before the close
        websocket.send_text.assert_awaited_once()
        assert json.loads(websocket.send_text.await_args.args[0])["action"] == "ping"
        websocket.close.assert_awaited_once_with(code=1008)
