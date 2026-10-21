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

import pytest
from fastapi import FastAPI

pytestmark = pytest.mark.asyncio

STREAM_AND_BINARY_RESPONSES = [
    ("/v3/notifications", "get", "200", "application/x-ndjson"),
    ("/v3/projects/{project_id}/notifications", "get", "200", "application/x-ndjson"),
    ("/v3/projects/{project_id}/export", "get", "200", "application/zip"),
    ("/v3/projects/{project_id}/gns3file", "get", "200", "application/json"),
    ("/v3/projects/{project_id}/files/{file_path}", "get", "200", "application/octet-stream"),
    ("/v3/projects/{project_id}/nodes/{node_id}/files/{file_path}", "get", "200", "application/octet-stream"),
    ("/v3/projects/{project_id}/nodes/{node_id}/files/{file_path}", "post", "201", "application/json"),
    ("/v3/projects/{project_id}/links/{link_id}/capture/stream", "get", "200", "application/vnd.tcpdump.pcap"),
    ("/v3/symbols/{symbol_id}/raw", "get", "200", "application/octet-stream"),
]

RAW_BODY_REQUESTS = [
    ("/v3/images/upload/{image_path}", "application/octet-stream"),
    ("/v3/symbols/{symbol_id}/raw", "application/octet-stream"),
    ("/v3/projects/{project_id}/files/{file_path}", "application/octet-stream"),
    ("/v3/projects/{project_id}/nodes/{node_id}/files/{file_path}", "application/octet-stream"),
    ("/v3/projects/{project_id}/import", "application/zip"),
]


class TestOpenAPIBinaryRoutes:
    @pytest.mark.parametrize("path, method, status_code, media_type", STREAM_AND_BINARY_RESPONSES)
    async def test_response_content(
        self, app: FastAPI, path: str, method: str, status_code: str, media_type: str
    ) -> None:

        content = app.openapi()["paths"][path][method]["responses"][status_code]["content"]
        assert media_type in content
        assert content[media_type]["schema"] != {}
        if media_type != "application/json":
            assert "application/json" not in content

    @pytest.mark.parametrize("path, media_type", RAW_BODY_REQUESTS)
    async def test_request_body(self, app: FastAPI, path: str, media_type: str) -> None:

        request_body = app.openapi()["paths"][path]["post"]["requestBody"]
        assert request_body["required"] is True
        assert request_body["content"][media_type]["schema"] == {"type": "string", "format": "binary"}

    async def test_binary_responses_use_binary_schema(self, app: FastAPI) -> None:

        paths = app.openapi()["paths"]
        for path, method, status_code, media_type in STREAM_AND_BINARY_RESPONSES:
            if media_type in ("application/octet-stream", "application/zip", "application/vnd.tcpdump.pcap"):
                schema = paths[path][method]["responses"][status_code]["content"][media_type]["schema"]
                assert schema == {"type": "string", "format": "binary"}
