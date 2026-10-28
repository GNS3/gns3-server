#!/usr/bin/env python
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
from fastapi import APIRouter, FastAPI, status
from httpx import ASGITransport, AsyncClient

from gns3server.api.routes.controller import build_ai_stub_routers

pytestmark = pytest.mark.asyncio


@pytest.fixture
def stub_app() -> FastAPI:
    """
    The /access layout of the controller API without the AI dependencies:
    the LLM stub is included before a later /access router, as API keys are.
    """

    _, _, llm_router = build_ai_stub_routers()
    later_router = APIRouter()

    @later_router.post("/access/api-keys")
    async def create_api_key():
        return {"created": True}

    application = FastAPI()
    application.include_router(llm_router, prefix="/v3/access")
    application.include_router(later_router, prefix="/v3")
    return application


async def test_llm_stub_does_not_shadow_later_access_routes(stub_app: FastAPI) -> None:

    async with AsyncClient(transport=ASGITransport(app=stub_app), base_url="http://test") as client:
        response = await client.post("/v3/access/api-keys")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"created": True}


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/v3/access/users/1/llm-model-configs"),
        ("GET", "/v3/access/users/1/llm-model-configs/own"),
        ("POST", "/v3/access/users/1/llm-model-configs"),
        ("PUT", "/v3/access/users/1/llm-model-configs/default/2"),
        ("DELETE", "/v3/access/groups/1/llm-model-configs/2"),
    ],
)
async def test_llm_stub_answers_llm_paths(stub_app: FastAPI, method: str, path: str) -> None:

    async with AsyncClient(transport=ASGITransport(app=stub_app), base_url="http://test") as client:
        response = await client.request(method, path)
    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
    assert "AI Copilot is not available" in response.json()["detail"]


async def test_create_api_key(app: FastAPI, client: AsyncClient) -> None:

    response = await client.post(app.url_path_for("create_api_key"), json={"name": "stub-check"})
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["api_key"].startswith("gns3_")
