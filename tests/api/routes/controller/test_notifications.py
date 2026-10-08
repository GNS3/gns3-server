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

import json
import uuid

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from gns3server import schemas
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
