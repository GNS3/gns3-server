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
import subprocess
import sys

import pytest
from fastapi import FastAPI

from gns3server.agent import AI_COPILOT_AVAILABLE, MCP_AVAILABLE
from gns3server.version import __api_version__, __version__

pytestmark = pytest.mark.asyncio

AI_PATH_PREFIXES = (
    "/v3/copilot",
    "/v3/mcp",
    "/v3/access/llm",
    "/v3/access/users/{user_id}/llm-model-configs",
    "/v3/access/groups/{group_id}/llm-model-configs",
)

SPEC_SCRIPT = """
import json
import sys

from gns3server.config import Config

Config.instance(files=[sys.argv[1]])

from gns3server.api.server import app

print(json.dumps(app.openapi()))
"""


def _operation_ids(spec: dict) -> list:
    return [
        operation["operationId"]
        for path_item in spec["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]


def _build_spec(tmp_path, include_ai: bool) -> dict:
    config_file = tmp_path / "gns3_server.conf"
    config_file.write_text(f"[Server]\nopenapi_include_ai = {str(include_ai).lower()}\n")
    result = subprocess.run(
        [sys.executable, "-c", SPEC_SCRIPT, str(config_file)],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return json.loads(result.stdout.splitlines()[-1])


class TestOpenAPISpec:
    async def test_controller_version_matches_package(self, app: FastAPI) -> None:

        spec = app.openapi()
        assert spec["info"]["version"] == __api_version__
        assert spec["info"]["version"] == __version__.split("+")[0]
        assert "+" not in spec["info"]["version"]

    async def test_compute_version_matches_package(self, app: FastAPI) -> None:

        compute_app = next(route.app for route in app.routes if getattr(route, "path", None) == "/v3/compute")
        assert compute_app.openapi()["info"]["version"] == __api_version__

    async def test_servers_entry(self, app: FastAPI) -> None:

        assert app.openapi()["servers"] == [{"url": "/"}]

    async def test_no_catch_all_operations(self, app: FastAPI) -> None:

        paths = app.openapi()["paths"]
        assert [path for path in paths if "{path}" in path] == []

    async def test_operation_ids_are_unique(self, app: FastAPI) -> None:

        operation_ids = _operation_ids(app.openapi())
        assert len(operation_ids) == len(set(operation_ids))

    @pytest.mark.skipif(AI_COPILOT_AVAILABLE or MCP_AVAILABLE, reason="AI extras are installed")
    async def test_ai_routes_absent_without_extras(self, app: FastAPI) -> None:

        paths = app.openapi()["paths"]
        assert [path for path in paths if path.startswith(AI_PATH_PREFIXES)] == []

    async def test_setting_hides_ai_routes_and_keeps_the_rest(self, tmp_path) -> None:

        with_ai = _build_spec(tmp_path, include_ai=True)
        without_ai = _build_spec(tmp_path, include_ai=False)

        assert [path for path in without_ai["paths"] if path.startswith(AI_PATH_PREFIXES)] == []
        non_ai_paths = {path: item for path, item in with_ai["paths"].items() if not path.startswith(AI_PATH_PREFIXES)}
        assert without_ai["paths"] == non_ai_paths
        assert len(_operation_ids(without_ai)) == len(set(_operation_ids(without_ai)))
