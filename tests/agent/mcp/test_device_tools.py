"""
Device config tool tests with mocked topology and Nornir layers.

Covers the VPCS node-type guard and the error contract shared by
device_config_send / device_show_run / vpcs_config_set.
"""
import json

import pytest
from unittest.mock import MagicMock, patch

VPCS_MOD = "gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko"


def _topology_ports(node_type):
    """Mocked get_device_ports_from_topology return value for one device."""
    return {"PC1": {"port": 5000, "node_type": node_type}}


class TestVPCSNodeTypeGuard:

    def test_non_vpcs_node_is_rejected(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        with patch(f"{VPCS_MOD}.get_device_ports_from_topology",
                   return_value=_topology_ports("iou")) as topo:
            result = VPCSCommands()._run(json.dumps({
                "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
            }))
            assert topo.called
        assert len(result) == 1
        assert result[0]["device_name"] == "PC1"
        assert result[0]["status"] == "failed"
        assert "not a VPCS node" in result[0]["error"]

    def test_missing_node_type_is_rejected(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        with patch(f"{VPCS_MOD}.get_device_ports_from_topology",
                   return_value={"PC1": {"port": 5000}}):
            result = VPCSCommands()._run(json.dumps({
                "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
            }))
        assert result[0]["status"] == "failed"
        assert "unknown-type" in result[0]["error"]

    def test_vpcs_node_passes_the_guard(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        tool = VPCSCommands()
        nornir = MagicMock()
        host_result = MagicMock(failed=False)
        host_result.result = "OK"
        nornir.run.return_value = {"PC1": host_result}
        with patch(f"{VPCS_MOD}.get_device_ports_from_topology",
                   return_value=_topology_ports("vpcs")), \
             patch.object(VPCSCommands, "_initialize_nornir", return_value=nornir):
            result = tool._run(json.dumps({
                "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
            }))
        assert result[0]["status"] == "success"
        assert result[0]["output"] == "OK"

    def test_execution_failure_reports_failed_with_error(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        tool = VPCSCommands()
        nornir = MagicMock()
        host_result = MagicMock(failed=True)
        host_result.result = "Command failed (ReadTimeout)"
        nornir.run.return_value = {"PC1": host_result}
        with patch(f"{VPCS_MOD}.get_device_ports_from_topology",
                   return_value=_topology_ports("vpcs")), \
             patch.object(VPCSCommands, "_initialize_nornir", return_value=nornir):
            result = tool._run(json.dumps({
                "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
            }))
        assert result[0]["status"] == "failed"
        assert result[0]["error"] == "Command failed (ReadTimeout)"
        assert "output" not in result[0]


class TestDeviceToolErrorContract:
    """
    Every in-band error entry carries status "failed" plus an "error"
    message, whether it is topology-level (no device) or per-device.
    """

    def test_topology_level_error_has_status(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        with patch(f"{VPCS_MOD}.get_device_ports_from_topology",
                   side_effect=ValueError("topology unreachable")):
            result = VPCSCommands()._run(json.dumps({
                "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
            }))
        assert result == [{"status": "failed", "error": "topology unreachable"}]

    def test_config_tool_topology_level_error_has_status(self):
        from gns3server.agent.gns3_copilot.tools_v2.config_tools_nornir import (
            ExecuteMultipleDeviceConfigCommands,
        )

        with patch("gns3server.agent.gns3_copilot.tools_v2.config_tools_nornir"
                   ".get_device_ports_from_topology",
                   side_effect=ValueError("no valid devices")):
            result = ExecuteMultipleDeviceConfigCommands()._run(json.dumps({
                "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                "device_configs": [{"device_name": "R1", "config_commands": ["int lo0"]}],
            }))
        assert result == [{"status": "failed", "error": "no valid devices"}]

    def test_mcp_handler_param_error_has_status(self, ctx=None):
        from gns3server.agent.mcp.device_config import (
            device_config_send_handler,
            device_show_run_handler,
            vpcs_config_set_handler,
        )

        for handler in (device_config_send_handler, device_show_run_handler, vpcs_config_set_handler):
            result = handler({}, {"server_url": "http://x", "jwt_token": "t"})
            assert result == [{
                "status": "failed",
                "error": result[0]["error"],  # message text may differ per handler
            }]
            assert "required" in result[0]["error"]

    def test_template_render_error_has_status(self):
        from gns3server.agent.mcp.device_config import _render_template

        result = _render_template("{{ unclosed", [{"device_name": "R1", "vars": {"n": 1}}])
        assert len(result) == 1
        assert result[0]["status"] == "failed"
        assert "Template rendering failed" in result[0]["error"]
