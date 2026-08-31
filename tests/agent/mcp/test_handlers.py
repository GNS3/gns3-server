"""
MCP handler unit tests with mocked Gns3Connector.

Tests that handlers correctly transform tool parameters into HTTP calls.
"""
import json

import pytest
from unittest.mock import MagicMock, patch


def _mock_conn(json_result=None):
    """Create a mocked Gns3Connector with base_url and http_call."""
    conn = MagicMock()
    conn.base_url = "http://192.168.1.3:3080/v3"
    conn.http_call.return_value.json.return_value = json_result or {"status": "ok"}
    conn.http_call.return_value.content = b"{}"  # non-empty body by default
    return conn


BASE = "gns3server.agent.mcp"
AH = "gns3server.agent.gns3_copilot.gns3_client.api_handlers"  # node/link handlers sunk here


@pytest.fixture
def ctx():
    return {"server_url": "http://192.168.1.3:3080", "jwt_token": "token", "jwt_username": "admin"}


# ── Project ─────────────────────────────────────────────────────────────


class TestProject:

    mod = "projects"

    def test_list(self, ctx):
        from gns3server.agent.mcp.projects import list_projects_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn([{"project_id": "p1", "name": "Test", "status": "opened"}])
            result = list_projects_handler({}, ctx)
            assert result["count"] == 1

    def test_get(self, ctx):
        from gns3server.agent.mcp.projects import get_project_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn({"project_id": "p1"})
            result = get_project_handler({"project_id": "p1"}, ctx)
            assert result["project_id"] == "p1"

    def test_get_missing_id(self, ctx):
        from gns3server.agent.mcp.projects import get_project_handler
        assert "error" in get_project_handler({}, ctx)

    def test_create(self, ctx):
        from gns3server.agent.mcp.projects import create_project_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            conn = _mock_conn({"project_id": "p1"})
            m.return_value = conn
            result = create_project_handler({"name": "New", "auto_close": False}, ctx)
            assert result["project_id"] == "p1"
            conn.http_call.assert_called_once_with(
                "post", f"{conn.base_url}/projects", json_data={"name": "New", "auto_close": False}
            )

    def test_create_without_auto_close(self, ctx):
        from gns3server.agent.mcp.projects import create_project_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            conn = _mock_conn({"project_id": "p2"})
            m.return_value = conn
            create_project_handler({"name": "New"}, ctx)
            conn.http_call.assert_called_once_with(
                "post", f"{conn.base_url}/projects", json_data={"name": "New"}
            )

    def test_delete(self, ctx):
        from gns3server.agent.mcp.projects import delete_project_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn({})
            result = delete_project_handler({"project_id": "p1"}, ctx)
            assert "message" in result

    def test_open(self, ctx):
        from gns3server.agent.mcp.projects import open_project_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn({"status": "opened"})
            result = open_project_handler({"project_id": "p1"}, ctx)
            assert result["status"] == "opened"

    def test_close(self, ctx):
        from gns3server.agent.mcp.projects import close_project_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn({"status": "closed"})
            result = close_project_handler({"project_id": "p1"}, ctx)
            assert "error" not in result

    def test_update(self, ctx):
        from gns3server.agent.mcp.projects import update_project_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn({"name": "Updated"})
            result = update_project_handler({"project_id": "p1", "name": "Updated"}, ctx)
            assert result["name"] == "Updated"

    def test_stats(self, ctx):
        from gns3server.agent.mcp.projects import get_project_stats_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn({"nodes": 5, "links": 3})
            result = get_project_stats_handler({"project_id": "p1"}, ctx)
            assert result["nodes"] == 5


# ── Node ────────────────────────────────────────────────────────────────


class TestNode:


    def test_list_fields(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_nodes_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn([
                {"node_id": "n1", "name": "R1", "status": "started", "node_type": "qemu", "console": 5000},
            ])
            result = get_nodes_handler({"project_id": "p1", "fields": ["name", "status"]}, ctx)
            assert result == {"nodes": [{"name": "R1", "status": "started"}], "count": 1}

    def test_list_invalid_fields(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_nodes_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn([])
            result = get_nodes_handler({"project_id": "p1", "fields": "not-a-list"}, ctx)
            assert "error" in result

    def test_get(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_node_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"node_id": "n1", "name": "R1"})
            result = get_node_handler({"project_id": "p1", "node_id": "n1"}, ctx)
            assert result["name"] == "R1"

    def test_create_single_passes_name(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_node_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"node_id": "n1", "name": "MyRouter"})
            m.return_value = conn
            result = create_node_handler({
                "project_id": "p1", "template_id": "t1",
                "name": "MyRouter", "x": 100, "y": 200,
            }, ctx)
            conn.http_call.assert_called_with(
                "post", "http://192.168.1.3:3080/v3/projects/p1/templates/t1",
                json_data={"x": 100, "y": 200, "compute_id": "local", "name": "MyRouter"},
            )
            assert result == {"node_id": "n1", "name": "MyRouter"}

    def test_create_fields_filter(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_node_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"node_id": "n1", "name": "R1", "status": "started"})
            result = create_node_handler({
                "project_id": "p1", "template_id": "t1",
                "fields": ["node_id", "name"],
            }, ctx)
            assert result == {"node_id": "n1", "name": "R1"}

    def test_create_fields_validation(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_node_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn()
            m.return_value = conn
            result = create_node_handler({
                "project_id": "p1", "template_id": "t1", "fields": "not-a-list",
            }, ctx)
            assert "error" in result
            assert "fields must be a list" in result["error"]
            conn.http_call.assert_not_called()

    def test_create_batch_inherits_template_id(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_node_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"node_id": "n1", "name": "R1"})
            result = create_node_handler({
                "project_id": "p1", "template_id": "default-tpl",
                "nodes": [{"name": "R1", "x": 0, "y": 0}],
            }, ctx)
            assert result[0]["status"] == "success"

    def test_create_batch_preserves_submission_order(self, ctx):
        import time
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_node_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn()
            def _http_call(method, url, json_data=None, **kwargs):
                # first submissions sleep longest so completion order is reversed
                time.sleep({"slow": 0.25, "mid": 0.1}.get(json_data.get("name"), 0.0))
                resp = MagicMock()
                resp.json.return_value = {"node_id": "n1", "name": json_data["name"]}
                return resp
            conn.http_call.side_effect = _http_call
            m.return_value = conn
            result = create_node_handler({
                "project_id": "p1", "template_id": "t1",
                "nodes": [{"name": "slow"}, {"name": "mid"}, {"name": "fast"}],
            }, ctx)
            assert [r["node"]["name"] for r in result] == ["slow", "mid", "fast"]

    def test_create_batch_default_names_created_sequentially(self, ctx):
        import threading
        import time
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_node_handler

        def _run(nodes_param):
            with patch(f"{AH}._get_connector") as m:
                conn = _mock_conn()
                lock = threading.Lock()
                active = [0, 0]  # in-flight requests, high-water mark
                counter = [0]

                def _http_call(method, url, json_data=None, **kwargs):
                    with lock:
                        active[0] += 1
                        active[1] = max(active[1], active[0])
                        counter[0] += 1
                        seq = counter[0]
                    time.sleep(0.05)  # wide enough that parallel calls would overlap
                    with lock:
                        active[0] -= 1
                    resp = MagicMock()
                    resp.json.return_value = {"node_id": f"n{seq}", "name": json_data.get("name", f"R-{seq}")}
                    return resp

                conn.http_call.side_effect = _http_call
                m.return_value = conn
                result = create_node_handler({"project_id": "p1", "template_id": "t1", "nodes": nodes_param}, ctx)
                return result, active[1]

        # nodes relying on default naming are created one at a time so the
        # server assigns default names/console ports in submission order
        result, max_active = _run([{}, {}, {}])
        assert [r["node"]["name"] for r in result] == ["R-1", "R-2", "R-3"]
        assert max_active == 1
        # one nameless node is enough to serialize the whole batch
        result, max_active = _run([{"name": "explicit"}, {}])
        assert [r["node"]["name"] for r in result] == ["explicit", "R-2"]
        assert max_active == 1

    def test_create_missing_project_id(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_node_handler
        assert create_node_handler({}, ctx) == {"error": "project_id is required"}

    def test_delete_batch(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import delete_node_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({})
            result = delete_node_handler({"project_id": "p1", "node_ids": ["n1", "n2"]}, ctx)
            assert len(result) == 2
            # same status vocabulary as create/start/stop batches
            assert all(r["status"] == "success" for r in result)

    def test_start_batch(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import start_node_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"status": "started"})
            result = start_node_handler({"project_id": "p1", "node_ids": ["n1"]}, ctx)
            assert result[0]["status"] == "success"

    def test_stop_batch(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import stop_node_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"status": "stopped"})
            result = stop_node_handler({"project_id": "p1", "node_ids": ["n1"]}, ctx)
            assert result[0]["status"] == "success"

    def test_suspend_batch(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import suspend_node_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"status": "suspended"})
            result = suspend_node_handler({"project_id": "p1", "node_ids": ["n1"]}, ctx)
            assert result[0]["status"] == "success"

    def test_console(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_node_console_info_handler
        from gns3server.services import access_ticket_service
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"console_url": "ws://host/console"})
            result = get_node_console_info_handler({"project_id": "p1", "node_id": "n1"}, ctx)
            assert "command" in result
            # the URL embeds a short console ticket (not a JWT) redeemable for this node
            assert "?token=gns3t_" in result["ws_url"]
            ticket = result["ws_url"].split("token=")[1]
            assert ticket in result["command"]
            assert result["token_ttl_seconds"] == 600
            assert len(result["token_sha256_prefix"]) == 8
            redeemed = access_ticket_service.redeem(ticket, {"project_id": "p1", "node_id": "n1"})
            assert redeemed is not None and redeemed.username == "admin"
            assert "vnc_url" not in result  # console_type is not vnc

    def test_console_vnc_uses_same_ticket(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_node_console_info_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"console_type": "vnc"})
            result = get_node_console_info_handler({"project_id": "p1", "node_id": "n1"}, ctx)
            ticket = result["ws_url"].split("token=")[1]
            # one node-bound ticket covers both console endpoints (identical path params)
            assert result["vnc_url"] == f"/v3/projects/p1/nodes/n1/console/vnc?token={ticket}"

    def test_console_without_username_omits_token(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_node_console_info_handler
        unauthenticated_ctx = {k: v for k, v in ctx.items() if k != "jwt_username"}
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"console_url": "ws://host/console"})
            result = get_node_console_info_handler({"project_id": "p1", "node_id": "n1"}, unauthenticated_ctx)
            assert "token=" not in result["ws_url"]
            assert "token_sha256_prefix" not in result

    @staticmethod
    def _file_conn(text):
        conn = _mock_conn()
        conn.http_call.return_value.text = text
        return conn

    def test_file_get_keeps_trailing_newline(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_node_file_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = self._file_conn("line1\nline2\n")
            result = get_node_file_handler({"project_id": "p1", "node_id": "n1", "file_path": "startup.cfg"}, ctx)
            assert result["content"] == "line1\nline2\n"
            assert result["metadata"]["total_bytes"] == 12
            assert result["metadata"]["returned_bytes"] == 12
            assert result["metadata"]["has_more"] is False

    def test_file_get_keeps_crlf_endings(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_node_file_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = self._file_conn("line1\r\nline2\r\n")
            result = get_node_file_handler({"project_id": "p1", "node_id": "n1", "file_path": "startup.cfg"}, ctx)
            assert result["content"] == "line1\r\nline2\r\n"
            assert result["metadata"]["returned_bytes"] == 14

    def test_file_get_without_trailing_newline(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_node_file_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = self._file_conn("line1\nline2")
            result = get_node_file_handler({"project_id": "p1", "node_id": "n1", "file_path": "startup.cfg"}, ctx)
            assert result["content"] == "line1\nline2"

    def test_file_get_pagination(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_node_file_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = self._file_conn("line1\nline2\nline3\n")
            result = get_node_file_handler(
                {"project_id": "p1", "node_id": "n1", "file_path": "startup.cfg", "offset": 1, "limit": 1}, ctx
            )
            assert result["content"] == "line2\n"
            assert result["metadata"]["total_lines"] == 3
            assert result["metadata"]["returned_lines"] == 1
            assert result["metadata"]["has_more"] is True


# ── Link ────────────────────────────────────────────────────────────────


class TestLink:


    def test_list(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_links_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn([{"link_id": "l1", "link_type": "ethernet"}])
            result = get_links_handler({"project_id": "p1", "fields": ["link_id"]}, ctx)
            assert result["links"] == [{"link_id": "l1"}]

    def test_get(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import get_link_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"link_id": "l1", "link_type": "ethernet"})
            result = get_link_handler({"project_id": "p1", "link_id": "l1"}, ctx)
            assert result["link_id"] == "l1"

    def test_create_compact_format(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_link_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"link_id": "l1", "link_type": "ethernet", "nodes": []})
            m.return_value = conn
            result = create_link_handler({
                "project_id": "p1",
                "nodes": ["n1", 0, 0, "n2", 0, 0],
            }, ctx)
            conn.http_call.assert_called_with(
                "post", "http://192.168.1.3:3080/v3/projects/p1/links",
                json_data={"nodes": [
                    {"node_id": "n1", "adapter_number": 0, "port_number": 0},
                    {"node_id": "n2", "adapter_number": 0, "port_number": 0},
                ]},
            )

    def test_create_standard_format(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_link_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"link_id": "l1"})
            result = create_link_handler({
                "project_id": "p1",
                "nodes": [
                    {"node_id": "n1", "adapter_number": 0, "port_number": 0},
                    {"node_id": "n2", "adapter_number": 0, "port_number": 0},
                ],
            }, ctx)
            assert result["link_id"] == "l1"

    def test_create_fields_validation(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_link_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn()
            m.return_value = conn
            result = create_link_handler({
                "project_id": "p1", "fields": "bad",
                "nodes": ["n1", 0, 0, "n2", 0, 0],
            }, ctx)
            assert "error" in result
            assert "fields must be a list" in result["error"]
            conn.http_call.assert_not_called()

    def test_delete_batch(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import delete_link_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({})
            result = delete_link_handler({"project_id": "p1", "link_ids": ["l1", "l2"]}, ctx)
            assert len(result) == 2
            # same status vocabulary as create batches
            assert all(r["status"] == "success" for r in result)

    def test_create_batch_preserves_submission_order(self, ctx):
        import time
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import create_link_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn()
            def _http_call(method, url, json_data=None, **kwargs):
                # first submission sleeps longest so completion order is reversed
                first_node = json_data["nodes"][0]["node_id"]
                time.sleep(0.25 if first_node == "n1" else 0.0)
                resp = MagicMock()
                resp.json.return_value = {"link_id": f"link-{first_node}"}
                return resp
            conn.http_call.side_effect = _http_call
            m.return_value = conn
            result = create_link_handler({
                "project_id": "p1",
                "links": [
                    {"nodes": ["n1", 0, 0, "n2", 0, 0]},
                    {"nodes": ["n3", 0, 0, "n4", 0, 0]},
                ],
                "fields": ["link_id"],
            }, ctx)
            assert [r["link"]["link_id"] for r in result] == ["link-n1", "link-n3"]

    def test_update(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import update_link_handler
        with patch(f"{AH}._get_connector") as m:
            m.return_value = _mock_conn({"link_id": "l1", "suspend": True})
            result = update_link_handler({
                "project_id": "p1", "link_id": "l1", "suspend": True,
            }, ctx)
            assert result["suspend"] is True

    def test_download_capture_file(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import download_capture_file_handler
        from gns3server.services import access_ticket_service
        result = download_capture_file_handler({"project_id": "p1", "link_id": "l1"}, ctx)
        # a short path-bound ticket replaces the long Bearer JWT in the URL
        assert "?token=gns3t_" in result["download_url"]
        assert "Bearer" not in result["curl_command"]
        path = f"/v3/projects/p1/links/l1/capture/file"
        ticket = result["download_url"].split("token=")[1]
        assert result["curl_command"] == f"curl -L -o capture.pcap '{result['download_url']}'"
        redeemed = access_ticket_service.redeem_for_path(ticket, path)
        assert redeemed is not None and redeemed.username == "admin"

    def test_download_capture_file_batch(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import download_capture_file_handler
        from gns3server.services import access_ticket_service
        result = download_capture_file_handler({"project_id": "p1", "link_ids": ["l1", "l2"]}, ctx)
        assert result["count"] == 2
        # each link gets its own ticket bound to its own download path
        tickets = [entry["download_url"].split("token=")[1] for entry in result["downloads"]]
        assert tickets[0] != tickets[1]
        for lid, ticket in zip(["l1", "l2"], tickets):
            redeemed = access_ticket_service.redeem_for_path(ticket, f"/v3/projects/p1/links/{lid}/capture/file")
            assert redeemed is not None


# ── Symbol ──────────────────────────────────────────────────────────────


class TestSymbol:

    mod = "symbols"

    def test_get_symbol_download(self, ctx):
        from gns3server.agent.mcp.symbols import get_symbol_handler
        from gns3server.services import access_ticket_service
        result = get_symbol_handler({"symbol_id": "router.svg"}, ctx)
        assert "?token=gns3t_" in result["download_url"]
        assert "Bearer" not in result["curl_command"]
        ticket = result["download_url"].split("token=")[1]
        redeemed = access_ticket_service.redeem_for_path(ticket, "/v3/symbols/router.svg/raw")
        assert redeemed is not None and redeemed.username == "admin"

    def test_get_symbol_without_username_omits_token(self, ctx):
        from gns3server.agent.mcp.symbols import get_symbol_handler
        unauthenticated_ctx = {k: v for k, v in ctx.items() if k != "jwt_username"}
        result = get_symbol_handler({"symbol_id": "router.svg"}, unauthenticated_ctx)
        assert "token=" not in result["download_url"]
        assert "curl_command" not in result


# ── Appliance ───────────────────────────────────────────────────────────


class TestAppliance:

    mod = "appliances"

    def test_get(self, ctx):
        from gns3server.agent.mcp.appliances import get_appliance_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn({"appliance_id": "a1", "name": "Cisco ISE"})
            result = get_appliance_handler({"appliance_id": "a1"}, ctx)
            assert result["name"] == "Cisco ISE"

    def test_install_with_version(self, ctx):
        from gns3server.agent.mcp.appliances import install_appliance_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            conn = _mock_conn({"template_id": "t1", "name": "FRR", "version": "8.2.2", "template_type": "docker"})
            m.return_value = conn
            result = install_appliance_handler({
                "appliance_id": "a1", "version": "2.7.0.356",
            }, ctx)
            conn.http_call.assert_called_with(
                "post", "http://192.168.1.3:3080/v3/appliances/a1/install",
                params={"version": "2.7.0.356"},
            )
            assert result["template"] == {
                "template_id": "t1", "name": "FRR", "version": "8.2.2", "template_type": "docker",
            }

    def test_install_empty_body(self, ctx):
        # a 204-style empty response must not blow up with a JSON decode error
        # (the template is still created server-side)
        from gns3server.agent.mcp.appliances import install_appliance_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            conn = _mock_conn()
            conn.http_call.return_value.content = b""
            conn.http_call.return_value.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
            m.return_value = conn
            result = install_appliance_handler({"appliance_id": "a1"}, ctx)
            assert "template" not in result
            assert result["message"] == "Appliance a1 installed"

    def test_install_missing_id(self, ctx):
        from gns3server.agent.mcp.appliances import install_appliance_handler
        result = install_appliance_handler({}, ctx)
        assert "error" in result


# ── Template ────────────────────────────────────────────────────────────


class TestTemplate:

    mod = "templates"

    def test_list_fields(self, ctx):
        from gns3server.agent.mcp.templates import list_templates_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn([
                {"template_id": "t1", "name": "Cisco 7200", "template_type": "dynamips",
                 "category": "router", "default_name_format": "{name}-{0}"},
            ])
            result = list_templates_handler({"fields": ["template_id", "name"]}, ctx)
            assert result["templates"] == [{"template_id": "t1", "name": "Cisco 7200"}]

    def test_list_invalid_field(self, ctx):
        from gns3server.agent.mcp.templates import list_templates_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn()
            result = list_templates_handler({"fields": ["does_not_exist"]}, ctx)
            assert "error" in result

    def test_get(self, ctx):
        from gns3server.agent.mcp.templates import get_template_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn({"template_id": "t1", "name": "Test"})
            result = get_template_handler({"template_id": "t1"}, ctx)
            assert result["name"] == "Test"

    def test_delete(self, ctx):
        from gns3server.agent.mcp.templates import delete_template_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            m.return_value = _mock_conn({})
            result = delete_template_handler({"template_id": "t1"}, ctx)
            assert "deleted" in str(result).lower()


# ── Image ───────────────────────────────────────────────────────────────


class TestImage:

    mod = "images"

    def test_install_manifest(self, ctx):
        from gns3server.agent.mcp.images import install_images_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            conn = _mock_conn({
                "created": [{"template_id": "t1", "name": "Empty VM", "version": "100G", "template_type": "qemu"}],
                "skipped": [{"name": "csr1000v.qcow2", "reason": "image is already used by one or more templates"}],
            })
            m.return_value = conn
            result = install_images_handler({}, ctx)
            assert result["created"][0]["name"] == "Empty VM"
            assert result["skipped"][0]["name"] == "csr1000v.qcow2"

    def test_install_empty_body(self, ctx):
        from gns3server.agent.mcp.images import install_images_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            conn = _mock_conn()
            conn.http_call.return_value.content = b""
            conn.http_call.return_value.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
            m.return_value = conn
            result = install_images_handler({}, ctx)
            assert result == {"message": "Image installation completed"}


class TestCompute:

    mod = "computes"

    def test_get_local_by_default(self, ctx):
        from gns3server.agent.mcp.computes import get_compute_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            conn = _mock_conn({"compute_id": "local", "name": "local"})
            m.return_value = conn
            result = get_compute_handler({}, ctx)
            assert result["compute_id"] == "local"
            url = conn.http_call.call_args[0][1]
            assert url.endswith("/computes/local")

    def test_get_explicit_compute_id(self, ctx):
        from gns3server.agent.mcp.computes import get_compute_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            conn = _mock_conn({"compute_id": "4fcfb6b5-5b0b-4f43-bd5e-e8ae2a69c8e6"})
            m.return_value = conn
            get_compute_handler({"compute_id": "4fcfb6b5-5b0b-4f43-bd5e-e8ae2a69c8e6"}, ctx)
            url = conn.http_call.call_args[0][1]
            assert url.endswith("/computes/4fcfb6b5-5b0b-4f43-bd5e-e8ae2a69c8e6")

    def test_images_local_by_default(self, ctx):
        from gns3server.agent.mcp.computes import get_compute_images_handler
        with patch(f"{BASE}.{self.mod}._get_connector") as m:
            conn = _mock_conn(["img1.qcow2"])
            m.return_value = conn
            result = get_compute_images_handler({"emulator": "qemu"}, ctx)
            assert result["count"] == 1
            url = conn.http_call.call_args[0][1]
            assert url.endswith("/computes/local/qemu/images")

    def test_images_requires_emulator(self, ctx):
        from gns3server.agent.mcp.computes import get_compute_images_handler
        assert "error" in get_compute_images_handler({}, ctx)


# ── Marker (traffic-insight) ────────────────────────────────────────────


class TestLinkMarker:
    """link_marker_handler direction tri-state: omit=preserve, tx/rx=set, both=clear (→ null)."""


    def test_update_direction_both_clears(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import link_marker_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "icmp"})
            m.return_value = conn
            link_marker_handler(
                {"project_id": "p", "link_id": "l", "action": "update",
                 "marker_name": "icmp", "direction": "both"}, ctx,
            )
            conn.http_call.assert_called_with(
                "put", "http://192.168.1.3:3080/v3/projects/p/links/l/markers/icmp",
                json_data={"direction": None},
            )

    def test_update_direction_tx_sets(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import link_marker_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "icmp"})
            m.return_value = conn
            link_marker_handler(
                {"project_id": "p", "link_id": "l", "action": "update",
                 "marker_name": "icmp", "direction": "tx"}, ctx,
            )
            conn.http_call.assert_called_with(
                "put", "http://192.168.1.3:3080/v3/projects/p/links/l/markers/icmp",
                json_data={"direction": "tx"},
            )

    def test_update_direction_omitted_preserved(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import link_marker_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "icmp"})
            m.return_value = conn
            link_marker_handler(
                {"project_id": "p", "link_id": "l", "action": "update",
                 "marker_name": "icmp", "tag": 1}, ctx,
            )
            conn.http_call.assert_called_with(
                "put", "http://192.168.1.3:3080/v3/projects/p/links/l/markers/icmp",
                json_data={"tag": 1},
            )

    def test_create_direction_both_omitted(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import link_marker_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "icmp"})
            m.return_value = conn
            link_marker_handler(
                {"project_id": "p", "link_id": "l", "action": "create",
                 "bpf": "icmp", "direction": "both"}, ctx,
            )
            conn.http_call.assert_called_with(
                "post", "http://192.168.1.3:3080/v3/projects/p/links/l/markers",
                json_data={"bpf": "icmp"},
            )

    def test_create_data_link_type_passthrough(self, ctx):
        """create passes a serial WAN encapsulation through; update ignores it."""
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import link_marker_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "icmp"})
            m.return_value = conn
            link_marker_handler(
                {"project_id": "p", "link_id": "l", "action": "create",
                 "bpf": "icmp", "data_link_type": "DLT_C_HDLC"}, ctx,
            )
            conn.http_call.assert_called_with(
                "post", "http://192.168.1.3:3080/v3/projects/p/links/l/markers",
                json_data={"bpf": "icmp", "data_link_type": "DLT_C_HDLC"},
            )

            conn = _mock_conn({"name": "icmp"})
            m.return_value = conn
            link_marker_handler(
                {"project_id": "p", "link_id": "l", "action": "update",
                 "marker_name": "icmp", "tag": 1, "data_link_type": "DLT_PPP_SERIAL"}, ctx,
            )
            # create-only: dropped from the update body
            conn.http_call.assert_called_with(
                "put", "http://192.168.1.3:3080/v3/projects/p/links/l/markers/icmp",
                json_data={"tag": 1},
            )

    def test_create_direction_tx(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import link_marker_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "icmp"})
            m.return_value = conn
            link_marker_handler(
                {"project_id": "p", "link_id": "l", "action": "create",
                 "bpf": "icmp", "direction": "tx"}, ctx,
            )
            conn.http_call.assert_called_with(
                "post", "http://192.168.1.3:3080/v3/projects/p/links/l/markers",
                json_data={"bpf": "icmp", "direction": "tx"},
            )


class TestMarkerDefinition:
    """marker_definition_handler build create/update bodies.

    A definition has NO direction: it fans out to every link and auto-selects its
    capture node on each, so tx/rx (relative to that node) has no consistent
    meaning — any direction passed is ignored, never reaching the request body.
    """


    def test_create_builds_body(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import marker_definition_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "arp"})
            m.return_value = conn
            marker_definition_handler(
                {"project_id": "p", "action": "create",
                 "bpf": "arp", "tag": 1, "color": "#fff"}, ctx,
            )
            conn.http_call.assert_called_with(
                "post", "http://192.168.1.3:3080/v3/projects/p/marker-definitions",
                json_data={"bpf": "arp", "tag": 1, "color": "#fff"},
            )

    def test_create_ignores_direction(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import marker_definition_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "arp"})
            m.return_value = conn
            marker_definition_handler(
                {"project_id": "p", "action": "create",
                 "bpf": "arp", "direction": "tx"}, ctx,
            )
            conn.http_call.assert_called_with(
                "post", "http://192.168.1.3:3080/v3/projects/p/marker-definitions",
                json_data={"bpf": "arp"},
            )

    def test_update_builds_body(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import marker_definition_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "arp"})
            m.return_value = conn
            marker_definition_handler(
                {"project_id": "p", "action": "update",
                 "def_name": "arp", "tag": 1}, ctx,
            )
            conn.http_call.assert_called_with(
                "put", "http://192.168.1.3:3080/v3/projects/p/marker-definitions/arp",
                json_data={"tag": 1},
            )

    def test_update_ignores_direction(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import marker_definition_handler
        with patch(f"{AH}._get_connector") as m:
            conn = _mock_conn({"name": "arp"})
            m.return_value = conn
            marker_definition_handler(
                {"project_id": "p", "action": "update",
                 "def_name": "arp", "tag": 1, "direction": "rx"}, ctx,
            )
            conn.http_call.assert_called_with(
                "put", "http://192.168.1.3:3080/v3/projects/p/marker-definitions/arp",
                json_data={"tag": 1},
            )

    def test_update_requires_a_field(self, ctx):
        from gns3server.agent.gns3_copilot.gns3_client.api_handlers import marker_definition_handler
        with patch(f"{AH}._get_connector"):
            result = marker_definition_handler(
                {"project_id": "p", "action": "update", "def_name": "arp"}, ctx,
            )
        assert "error" in result
