"""
Device config tool tests with mocked topology and Nornir layers.

Covers the VPCS node-type guard, the error contract shared by
device_config_send / device_show_run / vpcs_config_set, and the
same-device entry merging that keeps duplicate entries from
overwriting each other's commands and outputs.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from gns3server.agent.gns3_copilot.utils.device_configs import (
    merge_duplicate_device_configs,
)

VPCS_MOD = "gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko"
DISPLAY_MOD = "gns3server.agent.gns3_copilot.tools_v2.display_tools_nornir"
CONFIG_MOD = "gns3server.agent.gns3_copilot.tools_v2.config_tools_nornir"

PROJECT_ID = "0c0fde25-6ead-4413-a283-ea8fd2324291"


def _topology_ports(node_type):
    """Mocked get_device_ports_from_topology return value for one device."""
    return {"PC1": {"port": 5000, "node_type": node_type}}


def _topology_two_devices():
    """Mocked topology with two console-reachable devices."""
    return {
        "R1": {"port": 5000, "node_type": "iou"},
        "R2": {"port": 5001, "node_type": "iou"},
    }


def _aggregated_result(output_by_device):
    """Real AggregatedResult: device -> MultiResult with one successful Result."""
    from nornir.core.task import AggregatedResult, MultiResult, Result

    aggregated = AggregatedResult("task")
    for name, output in output_by_device.items():
        multi = MultiResult("task")
        multi.append(Result(host=None, result=output, failed=False))
        aggregated[name] = multi
    return aggregated


class TestVPCSNodeTypeGuard:
    def test_non_vpcs_node_is_rejected(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        with patch(f"{VPCS_MOD}.get_device_ports_from_topology", return_value=_topology_ports("iou")) as topo:
            result = VPCSCommands()._run(
                json.dumps(
                    {
                        "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                        "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
                    }
                )
            )
            assert topo.called
        assert len(result) == 1
        assert result[0]["device_name"] == "PC1"
        assert result[0]["status"] == "failed"
        assert "not a VPCS node" in result[0]["error"]

    def test_missing_node_type_is_rejected(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        with patch(f"{VPCS_MOD}.get_device_ports_from_topology", return_value={"PC1": {"port": 5000}}):
            result = VPCSCommands()._run(
                json.dumps(
                    {
                        "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                        "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
                    }
                )
            )
        assert result[0]["status"] == "failed"
        assert "unknown-type" in result[0]["error"]

    def test_vpcs_node_passes_the_guard(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        tool = VPCSCommands()
        nornir = MagicMock()
        host_result = MagicMock(failed=False)
        host_result.result = "OK"
        nornir.run.return_value = {"PC1": host_result}
        with (
            patch(f"{VPCS_MOD}.get_device_ports_from_topology", return_value=_topology_ports("vpcs")),
            patch.object(VPCSCommands, "_initialize_nornir", return_value=nornir),
        ):
            result = tool._run(
                json.dumps(
                    {
                        "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                        "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
                    }
                )
            )
        assert result[0]["status"] == "success"
        assert result[0]["output"] == "OK"

    def test_execution_failure_reports_failed_with_error(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        tool = VPCSCommands()
        nornir = MagicMock()
        host_result = MagicMock(failed=True)
        host_result.result = "Command failed (ReadTimeout)"
        nornir.run.return_value = {"PC1": host_result}
        with (
            patch(f"{VPCS_MOD}.get_device_ports_from_topology", return_value=_topology_ports("vpcs")),
            patch.object(VPCSCommands, "_initialize_nornir", return_value=nornir),
        ):
            result = tool._run(
                json.dumps(
                    {
                        "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                        "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
                    }
                )
            )
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

        with patch(f"{VPCS_MOD}.get_device_ports_from_topology", side_effect=ValueError("topology unreachable")):
            result = VPCSCommands()._run(
                json.dumps(
                    {
                        "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                        "device_configs": [{"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]}],
                    }
                )
            )
        assert result == [{"status": "failed", "error": "topology unreachable"}]

    def test_config_tool_topology_level_error_has_status(self):
        from gns3server.agent.gns3_copilot.tools_v2.config_tools_nornir import (
            ExecuteMultipleDeviceConfigCommands,
        )

        with patch(
            "gns3server.agent.gns3_copilot.tools_v2.config_tools_nornir.get_device_ports_from_topology",
            side_effect=ValueError("no valid devices"),
        ):
            result = ExecuteMultipleDeviceConfigCommands()._run(
                json.dumps(
                    {
                        "project_id": "0c0fde25-6ead-4413-a283-ea8fd2324291",
                        "device_configs": [{"device_name": "R1", "config_commands": ["int lo0"]}],
                    }
                )
            )
        assert result == [{"status": "failed", "error": "no valid devices"}]

    def test_mcp_handler_param_error_has_status(self, ctx=None):
        from gns3server.agent.mcp.device_config import (
            device_config_send_handler,
            device_show_run_handler,
            vpcs_config_set_handler,
        )

        for handler in (device_config_send_handler, device_show_run_handler, vpcs_config_set_handler):
            result = handler({}, {"server_url": "http://x", "jwt_token": "t"})
            assert result == [
                {
                    "status": "failed",
                    "error": result[0]["error"],  # message text may differ per handler
                }
            ]
            assert "required" in result[0]["error"]

    def test_template_render_error_has_status(self):
        from gns3server.agent.mcp.device_config import _render_template

        result = _render_template("{{ unclosed", [{"device_name": "R1", "vars": {"n": 1}}])
        assert len(result) == 1
        assert result[0]["status"] == "failed"
        assert "Template rendering failed" in result[0]["error"]


class TestDuplicateDeviceMerging:
    """
    Same-device entries in one batch must merge before execution.

    Regression: the per-device command map kept only the last entry's
    commands while result processing iterated every original entry, so all
    rows reported the last entry's output (first reproduced with the MCP
    direct-commands path, no template).
    """

    def test_show_run_merges_same_device_entries(self):
        from gns3server.agent.gns3_copilot.tools_v2.display_tools_nornir import (
            ExecuteMultipleDeviceCommands,
        )

        nornir = MagicMock()
        nornir.run.return_value = _aggregated_result({"R1": "merged output", "R2": "r2 output"})
        with (
            patch(f"{DISPLAY_MOD}.get_device_ports_from_topology", return_value=_topology_two_devices()),
            patch.object(ExecuteMultipleDeviceCommands, "_initialize_nornir", return_value=nornir),
        ):
            result = ExecuteMultipleDeviceCommands()._run(
                json.dumps(
                    {
                        "project_id": PROJECT_ID,
                        "device_configs": [
                            {"device_name": "R1", "commands": ["show ip route"]},
                            {"device_name": "R2", "commands": ["show version"]},
                            {"device_name": "R1", "commands": ["show ip interface brief"]},
                        ],
                    }
                )
            )

        # every command reached the execution layer, in order
        assert nornir.run.call_args.kwargs["device_configs_map"] == {
            "R1": ["show ip route", "show ip interface brief"],
            "R2": ["show version"],
        }
        # one truthful row per device
        assert [row["device_name"] for row in result] == ["R1", "R2"]
        assert result[0]["status"] == "success"
        assert result[0]["output"] == "merged output"
        assert result[0]["diagnostic_commands"] == ["show ip route", "show ip interface brief"]

    def test_config_send_merges_same_device_entries(self):
        from gns3server.agent.gns3_copilot.tools_v2.config_tools_nornir import (
            ExecuteMultipleDeviceConfigCommands,
        )

        nornir = MagicMock()
        nornir.run.return_value = _aggregated_result({"R1": "merged output"})
        with (
            patch(
                f"{CONFIG_MOD}.get_device_ports_from_topology", return_value={"R1": {"port": 5000, "node_type": "iou"}}
            ),
            patch.object(ExecuteMultipleDeviceConfigCommands, "_initialize_nornir", return_value=nornir),
        ):
            result = ExecuteMultipleDeviceConfigCommands()._run(
                json.dumps(
                    {
                        "project_id": PROJECT_ID,
                        "device_configs": [
                            {"device_name": "R1", "config_commands": ["int lo0"]},
                            {"device_name": "R1", "config_commands": ["ip address 1.1.1.1 255.255.255.255", "exit"]},
                        ],
                    }
                )
            )

        assert nornir.run.call_args.kwargs["device_configs_map"] == {
            "R1": ["int lo0", "ip address 1.1.1.1 255.255.255.255", "exit"],
        }
        assert len(result) == 1
        assert result[0]["status"] == "success"
        assert result[0]["config_commands"] == ["int lo0", "ip address 1.1.1.1 255.255.255.255", "exit"]

    def test_vpcs_merges_same_device_entries(self):
        from gns3server.agent.gns3_copilot.tools_v2.vpcs_tools_netmiko import VPCSCommands

        nornir = MagicMock()
        host_result = MagicMock(failed=False)
        host_result.result = "OK"
        nornir.run.return_value = {"PC1": host_result}
        with (
            patch(f"{VPCS_MOD}.get_device_ports_from_topology", return_value=_topology_ports("vpcs")),
            patch.object(VPCSCommands, "_initialize_nornir", return_value=nornir),
        ):
            result = VPCSCommands()._run(
                json.dumps(
                    {
                        "project_id": PROJECT_ID,
                        "device_configs": [
                            {"device_name": "PC1", "commands": ["ip 10.0.0.1/24"]},
                            {"device_name": "PC1", "commands": ["save"]},
                        ],
                    }
                )
            )

        assert nornir.run.call_args.kwargs["device_configs_map"] == {"PC1": ["ip 10.0.0.1/24", "save"]}
        assert len(result) == 1
        assert result[0]["status"] == "success"
        assert result[0]["commands"] == ["ip 10.0.0.1/24", "save"]

    def test_blocked_commands_accumulate_across_duplicate_entries(self):
        """Blocked-command info must not last-win between same-device entries."""
        from gns3server.agent.gns3_copilot.tools_v2.display_tools_nornir import (
            ExecuteMultipleDeviceCommands,
        )

        def fake_filter(commands):
            blocked = {c: "matched forbidden pattern" for c in commands if c.startswith("debug")}
            allowed = [c for c in commands if not c.startswith("debug")]
            return allowed, blocked

        nornir = MagicMock()
        nornir.run.return_value = _aggregated_result({"R1": "ok"})
        with (
            patch(
                f"{DISPLAY_MOD}.get_device_ports_from_topology", return_value={"R1": {"port": 5000, "node_type": "iou"}}
            ),
            patch.object(ExecuteMultipleDeviceCommands, "_initialize_nornir", return_value=nornir),
            patch(f"{DISPLAY_MOD}.filter_forbidden_commands", side_effect=fake_filter),
        ):
            result = ExecuteMultipleDeviceCommands()._run(
                json.dumps(
                    {
                        "project_id": PROJECT_ID,
                        "device_configs": [
                            {"device_name": "R1", "commands": ["show version", "debug ip routing"]},
                            {"device_name": "R1", "commands": ["debug ospf events", "show clock"]},
                        ],
                    }
                )
            )

        assert nornir.run.call_args.kwargs["device_configs_map"] == {"R1": ["show version", "show clock"]}
        assert result[0]["status"] == "partial_success"
        assert set(result[0]["blocked_commands"]) == {"debug ip routing", "debug ospf events"}

    def test_entry_without_device_name_fails_the_whole_batch(self):
        """An unaddressable entry must abort with an error, not vanish."""
        from gns3server.agent.gns3_copilot.tools_v2.display_tools_nornir import (
            ExecuteMultipleDeviceCommands,
        )

        result = ExecuteMultipleDeviceCommands()._run(
            json.dumps(
                {
                    "project_id": PROJECT_ID,
                    "device_configs": [
                        {"device_name": "R1", "commands": ["show version"]},
                        {"commands": ["show clock"]},
                    ],
                }
            )
        )

        assert result[0]["status"] == "failed"
        assert "device_configs[1]" in result[0]["error"]


class TestMergeDuplicateDeviceConfigs:
    """Unit tests for the shared normalization helper."""

    def test_merges_in_first_appearance_order(self):
        merged = merge_duplicate_device_configs(
            [
                {"device_name": "R1", "commands": ["a"]},
                {"device_name": "R2", "commands": ["b"]},
                {"device_name": "R1", "commands": ["c", "d"]},
            ],
            commands_field="commands",
        )
        assert merged == [
            {"device_name": "R1", "commands": ["a", "c", "d"]},
            {"device_name": "R2", "commands": ["b"]},
        ]

    def test_preserves_first_entry_fields_without_mutating_input(self):
        original = [
            {"device_name": "R1", "commands": ["a"], "extra": 1},
            {"device_name": "R1", "commands": ["b"]},
        ]
        merged = merge_duplicate_device_configs(original, commands_field="commands")
        assert merged == [{"device_name": "R1", "commands": ["a", "b"], "extra": 1}]
        assert original[0]["commands"] == ["a"]

    def test_entry_without_device_name_is_rejected(self):
        # Silently dropping it would let the batch execute partially while
        # every returned row reports success.
        with pytest.raises(ValueError, match=r"device_configs\[0\]"):
            merge_duplicate_device_configs(
                [{"commands": ["a"]}, {"device_name": "R1", "commands": ["b"]}],
                commands_field="commands",
            )

    def test_entry_that_is_not_an_object_is_rejected(self):
        with pytest.raises(ValueError, match=r"device_configs\[1\]"):
            merge_duplicate_device_configs(
                [{"device_name": "R1", "commands": ["a"]}, "R2"],
                commands_field="commands",
            )

    def test_missing_commands_field_defaults_to_empty(self):
        merged = merge_duplicate_device_configs(
            [{"device_name": "R1"}, {"device_name": "R1", "commands": ["b"]}],
            commands_field="commands",
        )
        assert merged == [{"device_name": "R1", "commands": ["b"]}]
