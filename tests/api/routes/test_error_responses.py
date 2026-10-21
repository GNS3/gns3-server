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

import uuid
from typing import Tuple
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.api.errors import code_for_status
from gns3server.controller.compute import Compute
from gns3server.controller.controller_error import ComputeConflictError, ControllerError
from gns3server.controller.node import Node
from gns3server.controller.ports.ethernet_port import EthernetPort
from gns3server.controller.project import Project
from gns3server.db.models import User
from gns3server.schemas import ErrorMessage
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY
from tests.utils import AsyncioMagicMock, asyncio_patch

pytestmark = pytest.mark.asyncio


class TestErrorResponses:
    @pytest_asyncio.fixture
    async def nodes(self, compute: Compute, project: Project) -> Tuple[Node, Node]:

        response = MagicMock()
        response.json = {"console": 2048}
        compute.post = AsyncioMagicMock(return_value=response)

        node1 = await project.add_node(compute, "node1", None, node_type="qemu")
        node1._ports = [EthernetPort("E0", 0, 0, 3)]
        node2 = await project.add_node(compute, "node2", None, node_type="qemu")
        node2._ports = [EthernetPort("E0", 0, 2, 4)]
        return node1, node2

    async def test_unauthorized(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        response = await client.get(
            app.url_path_for("get_project", project_id=project.id),
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        body = response.json()
        assert isinstance(body["message"], str)
        assert body["code"] == "unauthorized"
        assert "detail" not in body

    async def test_forbidden(self, app: FastAPI, client: AsyncClient, test_user: User, project: Project) -> None:

        token = auth_service.create_access_token(test_user.username, secret_key=DEFAULT_JWT_SECRET_KEY)
        response = await client.delete(
            app.url_path_for("delete_project", project_id=project.id),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        body = response.json()
        assert isinstance(body["message"], str)
        assert body["code"] == "forbidden"

    async def test_unknown_node(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        node_id = str(uuid.uuid4())
        response = await client.get(app.url_path_for("get_node", project_id=project.id, node_id=node_id))
        assert response.status_code == status.HTTP_404_NOT_FOUND
        body = response.json()
        assert body["message"] == f"Node ID {node_id} doesn't exist"
        assert body["code"] == "node_not_found"
        assert body["details"] == {"node_id": node_id}

    async def test_unknown_project(self, app: FastAPI, client: AsyncClient) -> None:

        project_id = str(uuid.uuid4())
        response = await client.get(app.url_path_for("get_project", project_id=project_id))
        assert response.status_code == status.HTTP_404_NOT_FOUND
        body = response.json()
        assert body["code"] == "project_not_found"
        assert body["details"] == {"project_id": project_id}

    async def test_unknown_route(self, client: AsyncClient) -> None:

        response = await client.get("/v3/no/such/route")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        body = response.json()
        assert body["message"] == "Not Found"
        assert body["code"] == "not_found"
        assert "detail" not in body

    async def test_port_in_use(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, node2 = nodes
        payload = {
            "nodes": [
                {"node_id": node1.id, "adapter_number": 0, "port_number": 3},
                {"node_id": node2.id, "adapter_number": 2, "port_number": 4},
            ]
        }
        with asyncio_patch("gns3server.controller.udp_link.UDPLink.create"):
            first = await client.post(app.url_path_for("create_link", project_id=project.id), json=payload)
            assert first.status_code == status.HTTP_201_CREATED
            second = await client.post(app.url_path_for("create_link", project_id=project.id), json=payload)

        assert second.status_code == status.HTTP_409_CONFLICT
        body = second.json()
        assert body["message"] == "Port is already used"
        assert body["code"] == "port_in_use"
        assert body["details"]["node_id"] == node1.id
        assert body["details"]["adapter_number"] == 0
        assert body["details"]["port_number"] == 3
        assert body["details"]["link_id"] == first.json()["link_id"]

    async def test_generic_conflict(
        self, app: FastAPI, client: AsyncClient, project: Project, nodes: Tuple[Node, Node]
    ) -> None:

        node1, _ = nodes
        node1._ports = [EthernetPort("E0", 0, 0, 3), EthernetPort("E1", 0, 0, 4)]
        response = await client.post(
            app.url_path_for("create_link", project_id=project.id),
            json={
                "nodes": [
                    {"node_id": node1.id, "adapter_number": 0, "port_number": 3},
                    {"node_id": node1.id, "adapter_number": 0, "port_number": 4},
                ]
            },
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        body = response.json()
        assert body["message"] == "Cannot connect to itself"
        assert body["code"] == "conflict"
        assert "details" not in body

    async def test_validation_error(self, app: FastAPI, client: AsyncClient, project: Project) -> None:

        response = await client.post(app.url_path_for("create_link", project_id=project.id), json={"nodes": "bad"})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        body = response.json()
        assert isinstance(body["message"], str)
        assert body["code"] == "validation_error"
        assert body["details"]["errors"]
        assert {"loc", "msg", "type"} <= set(body["details"]["errors"][0])
        assert "detail" not in body

    async def test_message_only_clients_keep_working(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_project", project_id=str(uuid.uuid4())))
        assert ErrorMessage.model_validate({"message": response.json()["message"]}).code is None
        assert isinstance(response.json()["message"], str)


class TestErrorCodes:
    async def test_default_codes(self) -> None:

        assert ControllerError("x").code == "conflict"
        assert ControllerError("x", code="custom", details={"a": 1}).details == {"a": 1}

    async def test_compute_conflict_code(self) -> None:

        error = ComputeConflictError("http://c/x", {"message": "boom", "code": "port_in_use"})
        assert error.code == "port_in_use"
        assert ComputeConflictError("http://c/x", {"message": "boom"}).code == "compute_conflict"

    @pytest.mark.parametrize(
        "status_code,code",
        [(401, "unauthorized"), (403, "forbidden"), (404, "not_found"), (409, "conflict"), (501, "not_implemented")],
    )
    async def test_code_for_status(self, status_code: int, code: str) -> None:

        assert code_for_status(status_code) == code


class TestOpenAPIErrorSchemas:
    async def test_error_schemas(self, client: AsyncClient) -> None:

        response = await client.get("/openapi.json")
        assert response.status_code == status.HTTP_200_OK
        spec = response.json()

        schemas = spec["components"]["schemas"]
        assert "HTTPValidationError" not in schemas
        assert "ValidationError" not in schemas
        assert set(schemas["ErrorMessage"]["properties"]) == {"message", "code", "details"}
        assert schemas["ErrorMessage"]["required"] == ["message"]

        error_ref = {"$ref": "#/components/schemas/ErrorMessage"}
        authenticated = 0
        for path, path_item in spec["paths"].items():
            for method, operation in path_item.items():
                responses = operation["responses"]
                if "422" in responses:
                    assert responses["422"]["content"]["application/json"]["schema"] == error_ref, (method, path)
                if operation.get("security"):
                    authenticated += 1
                    for code in ("401", "403", "422"):
                        assert responses[code]["content"]["application/json"]["schema"] == error_ref, (
                            method,
                            path,
                            code,
                        )
        assert authenticated > 0
        assert "HTTPValidationError" not in response.text
