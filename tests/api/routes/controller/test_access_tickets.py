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

import hashlib
from types import SimpleNamespace
from typing import List

import aiohttp
import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from pydantic import SecretStr

from gns3server.config import Config
from gns3server.controller import Controller
from gns3server.controller.compute import Compute
from gns3server.controller.node import Node
from gns3server.controller.project import Project
from gns3server.services import access_ticket_service
from gns3server.services.access_tickets import (
    AccessTicketService,
    DEFAULT_TICKET_TTL,
    TICKET_PREFIX,
)
from gns3server.utils.http_client import HTTPClient
from tests.api.routes.controller.test_nodes import FakeComputeConsoleWebSocket


class TestAccessTicketService:
    """Unit tests for the in-memory ticket store (fresh instances, no app)."""

    def test_mint_format(self) -> None:

        service = AccessTicketService()
        ticket = service.mint("admin", 1, project_id="p1", node_id="n1")
        assert ticket.startswith(TICKET_PREFIX)
        # 12 random bytes -> 16 urlsafe chars; shell-safe alphabet (no quoting hazards)
        assert len(ticket) == len(TICKET_PREFIX) + 16
        assert "." not in ticket  # never confusable with a JWT
        assert service.mint("admin", 1, project_id="p1", node_id="n1") != ticket

    def test_redeem_valid_ticket_is_multi_use(self) -> None:

        service = AccessTicketService()
        ticket = service.mint("admin", 7, project_id="p1", node_id="n1")
        path_params = {"project_id": "p1", "node_id": "n1"}
        first = service.redeem(ticket, path_params)
        second = service.redeem(ticket, path_params)  # console clients reconnect, tickets stay usable
        assert first is not None and second is not None
        assert first.username == "admin"
        assert first.token_version == 7

    def test_redeem_rejects_wrong_binding(self) -> None:

        service = AccessTicketService()
        ticket = service.mint("admin", 0, project_id="p1", node_id="n1")
        assert service.redeem(ticket, {"project_id": "p1", "node_id": "n2"}) is None
        assert service.redeem(ticket, {"project_id": "p2", "node_id": "n1"}) is None
        # routes without a node_id path parameter (notifications, wireshark…) never accept a ticket
        assert service.redeem(ticket, {"project_id": "p1"}) is None
        assert service.redeem(ticket, {}) is None

    def test_redeem_rejects_unknown_ticket(self) -> None:

        service = AccessTicketService()
        assert service.redeem(TICKET_PREFIX + "doesnotexist", {"project_id": "p1", "node_id": "n1"}) is None

    def test_expired_ticket_is_rejected_and_removed(self) -> None:

        service = AccessTicketService()
        ticket = service.mint("admin", 0, project_id="p1", node_id="n1", ttl=0)
        assert service.redeem(ticket, {"project_id": "p1", "node_id": "n1"}) is None
        assert ticket not in service._tickets

    def test_mint_sweeps_expired_entries(self) -> None:

        service = AccessTicketService()
        stale = service.mint("admin", 0, project_id="p1", node_id="n1", ttl=0)
        fresh = service.mint("admin", 0, project_id="p1", node_id="n2", ttl=DEFAULT_TICKET_TTL)
        assert stale not in service._tickets
        assert fresh in service._tickets

    def test_redeem_for_path_valid_ticket_is_multi_use(self) -> None:

        service = AccessTicketService()
        ticket = service.mint("admin", 3, path="/v3/projects/p1/links/l1/capture/file")
        first = service.redeem_for_path(ticket, "/v3/projects/p1/links/l1/capture/file")
        second = service.redeem_for_path(ticket, "/v3/projects/p1/links/l1/capture/file")
        assert first is not None and second is not None
        assert first.username == "admin"
        assert first.token_version == 3

    def test_redeem_for_path_rejects_other_path(self) -> None:

        service = AccessTicketService()
        ticket = service.mint("admin", 0, path="/v3/projects/p1/links/l1/capture/file")
        assert service.redeem_for_path(ticket, "/v3/projects/p1/links/l2/capture/file") is None
        assert service.redeem_for_path(ticket, "/v3/projects/p2/links/l1/capture/file") is None
        assert service.redeem_for_path(ticket, "/v3/symbols/router.svg/raw") is None

    def test_binding_modes_are_isolated(self) -> None:

        service = AccessTicketService()
        # a node-bound ticket must not authenticate REST resources…
        ws_ticket = service.mint("admin", 0, project_id="p1", node_id="n1")
        assert service.redeem_for_path(ws_ticket, "/v3/projects/p1/nodes/n1/console/ws") is None
        # …and a path-bound ticket must not authenticate WebSocket routes
        rest_ticket = service.mint("admin", 0, path="/v3/projects/p1/links/l1/capture/file")
        assert service.redeem(rest_ticket, {"project_id": "p1", "node_id": "n1"}) is None


class TestAccessTicketWebSocketAuth:
    """
    Drive the console WebSocket auth dependency end-to-end through the real
    routes (the shared service singleton is the one the dependency consults).
    """

    pytestmark = pytest.mark.asyncio

    @pytest.fixture(autouse=True)
    def _reset_controller_singleton(self, controller):
        # The project/compute fixtures register state on the shared Controller
        # singleton; reset it after each test so files running later (e.g. the
        # controller statistics endpoint) see a pristine controller regardless
        # of test order — same reset the controller fixture applies at setup.
        yield
        Controller._instance = None

    @pytest.fixture
    def node(self, project: Project, compute: Compute) -> Node:

        compute.host = "127.0.0.1"
        compute.port = 3080
        node = Node(project, compute, "test", node_type="vpcs")
        project._nodes[node.id] = node
        return node

    @pytest.fixture
    def compute_credentials(self) -> None:

        server_config = Config.instance().settings.Server
        server_config.compute_username = "admin"
        server_config.compute_password = SecretStr("password")

    @staticmethod
    def _ws_client(app: FastAPI, base_client: AsyncClient) -> AsyncClient:
        # base_client must be requested so the app gets the test-DB dependency
        # override, but the WebSocket connection itself needs a function-local
        # client: closing the WS transport from the class-scoped base_client
        # teardown exits anyio cancel scopes in the wrong task.
        return AsyncClient(base_url="http://test-api", transport=ASGIWebSocketTransport(app=app))

    @staticmethod
    def _forward_compute_ws(monkeypatch, messages: List[aiohttp.WSMessage]) -> FakeComputeConsoleWebSocket:

        compute_ws = FakeComputeConsoleWebSocket(messages)
        monkeypatch.setattr(
            HTTPClient,
            "get_client",
            classmethod(lambda cls: SimpleNamespace(ws_connect=lambda *args, **kwargs: compute_ws))
        )
        return compute_ws

    async def test_console_ws_accepts_valid_ticket(
            self,
            app: FastAPI,
            base_client: AsyncClient,
            compute_credentials,
            project: Project,
            node: Node,
            monkeypatch
    ) -> None:
        # admin is the seeded superadmin, so the RBAC privilege check is skipped
        ticket = access_ticket_service.mint("admin", 0, project_id=project.id, node_id=node.id)
        self._forward_compute_ws(monkeypatch, [
            aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, "device output", None),
        ])

        async with self._ws_client(app, base_client) as client:
            async with aconnect_ws(
                    f"/v3/projects/{project.id}/nodes/{node.id}/console/ws",
                    client,
                    params={"token": ticket}
            ) as ws:
                # reaching the compute forwarding loop means ticket auth succeeded
                assert await ws.receive_text() == "device output"

    async def test_console_ws_rejects_ticket_bound_to_other_node(
            self,
            app: FastAPI,
            base_client: AsyncClient,
            project: Project,
            node: Node
    ) -> None:

        other_node = "00000000-0000-0000-0000-000000000000"
        ticket = access_ticket_service.mint("admin", 0, project_id=project.id, node_id=other_node)
        async with self._ws_client(app, base_client) as client:
            async with aconnect_ws(
                    f"/v3/projects/{project.id}/nodes/{node.id}/console/ws",
                    client,
                    params={"token": ticket}
            ) as ws:
                notification = await ws.receive_json()
                assert notification["event"]["message"] == (
                    "Could not authenticate while connecting to controller WebSocket: "
                    "Invalid or expired console ticket "
                    f"(received token sha256 prefix: {hashlib.sha256(ticket.encode()).hexdigest()[:8]})"
                )

    async def test_console_ws_rejects_ticket_with_stale_token_version(
            self,
            app: FastAPI,
            base_client: AsyncClient,
            project: Project,
            node: Node
    ) -> None:
        # logging out bumps the user's token_version: outstanding tickets must die with it
        ticket = access_ticket_service.mint("admin", 999, project_id=project.id, node_id=node.id)
        async with self._ws_client(app, base_client) as client:
            async with aconnect_ws(
                    f"/v3/projects/{project.id}/nodes/{node.id}/console/ws",
                    client,
                    params={"token": ticket}
            ) as ws:
                notification = await ws.receive_json()
                assert "Token has been revoked for 'admin'" in notification["event"]["message"]

    async def test_ticket_rejected_on_non_console_websocket(
            self,
            app: FastAPI,
            base_client: AsyncClient
    ) -> None:
        # the controller notification stream shares the WS auth dependency but has
        # no node binding: a console ticket must not authenticate it
        ticket = access_ticket_service.mint("admin", 0, project_id="p1", node_id="n1")
        async with self._ws_client(app, base_client) as client:
            async with aconnect_ws("/v3/notifications/ws", client, params={"token": ticket}) as ws:
                notification = await ws.receive_json()
                assert "Invalid or expired console ticket" in notification["event"]["message"]


class TestAccessTicketRestAuth:
    """
    Drive the REST auth dependency (get_user_from_token) end-to-end: a
    path-bound ticket authenticates exactly one resource path.
    """

    pytestmark = pytest.mark.asyncio

    async def test_rest_accepts_path_bound_ticket(
            self,
            app: FastAPI,
            base_client: AsyncClient
    ) -> None:
        # base_client carries no Authorization header, so the ?token= parameter is used
        ticket = access_ticket_service.mint("admin", 0, path="/v3/projects")
        response = await base_client.get("/v3/projects", params={"token": ticket})
        assert response.status_code == status.HTTP_200_OK

    async def test_rest_rejects_ticket_bound_to_other_path(
            self,
            app: FastAPI,
            base_client: AsyncClient
    ) -> None:

        ticket = access_ticket_service.mint("admin", 0, path="/v3/symbols/router.svg/raw")
        response = await base_client.get("/v3/projects", params={"token": ticket})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or expired access ticket" in response.text

    async def test_rest_rejects_node_bound_ticket(
            self,
            app: FastAPI,
            base_client: AsyncClient
    ) -> None:
        # node-bound (console) tickets must not authenticate REST resources
        ticket = access_ticket_service.mint("admin", 0, project_id="p1", node_id="n1")
        response = await base_client.get("/v3/projects", params={"token": ticket})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_rest_rejects_ticket_with_stale_token_version(
            self,
            app: FastAPI,
            base_client: AsyncClient
    ) -> None:
        # logging out bumps the user's token_version: outstanding tickets must die with it
        ticket = access_ticket_service.mint("admin", 999, path="/v3/projects")
        response = await base_client.get("/v3/projects", params={"token": ticket})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "revoked" in response.text
