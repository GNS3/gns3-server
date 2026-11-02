#
# Copyright (C) 2026 GNS3 Technologies Inc.
# Author: Yue Guobin
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
#

"""
Unit tests for the MCP fault-injection skills tool (registry faked, no I/O).
"""

import pytest

from gns3server.agent.gns3_copilot.skills import registry as skills_registry
from gns3server.agent.gns3_copilot.skills.registry import list_available_injection_skills
from gns3server.agent.mcp.skills import injection_skills_handler

FAKE_INJECTION_SKILLS = {
    "injection_ospf_issues": {
        "name": "OSPF Issues Injection",
        "description": "OSPF faults",
        "category": "injection",
        "protocols": ["ospf", "ospfv2", "ospfv3"],
        "issues": {
            "ospf_hello_dead_mismatch": {"name": "Hello/Dead Mismatch", "description": "timers differ"},
            "ospf_area_mismatch": {"name": "Area Mismatch", "description": "area ids differ"},
        },
    },
    "injection_bgp_issues": {
        "name": "BGP Issues Injection",
        "description": "BGP faults",
        "category": "injection",
        "protocols": ["bgp", "ebgp", "ibgp"],
        "issues": {
            "bgp_missing_route": {"name": "Missing Route", "description": "route absent"},
        },
    },
    "injection_vlan_issues": {
        "name": "VLAN Issues Injection",
        "description": "VLAN faults",
        "category": "injection",
        "protocols": ["vlan", "stp"],
        "issues": {},
    },
}


@pytest.fixture(autouse=True)
def fake_registry(monkeypatch):
    monkeypatch.setattr(skills_registry, "INJECTION_SKILLS_REGISTRY", FAKE_INJECTION_SKILLS)


class TestInjectionFilter:
    """Context matching covers the declared protocols, not just the key."""

    def test_protocol_aliases_match(self):
        assert [s["device_type"] for s in list_available_injection_skills(["ebgp"])] == ["injection_bgp_issues"]
        assert [s["device_type"] for s in list_available_injection_skills(["ospfv3"])] == ["injection_ospf_issues"]
        assert [s["device_type"] for s in list_available_injection_skills(["stp"])] == ["injection_vlan_issues"]

    def test_case_insensitive(self):
        assert [s["device_type"] for s in list_available_injection_skills(["BGP"])] == ["injection_bgp_issues"]

    def test_no_match(self):
        assert list_available_injection_skills(["mpls"]) == []

    def test_no_context_returns_all(self):
        assert len(list_available_injection_skills()) == 3


class TestInjectionSkillsHandler:
    def test_list_requires_context(self):
        result = injection_skills_handler({"action": "list"}, {})
        assert result["status"] == "failed"
        assert "context is required" in result["error"]
        assert result["total_available"] == 3

    def test_list_filters_by_topology_context(self):
        result = injection_skills_handler({"action": "list", "context": ["ospf"]}, {})
        assert result["status"] == "ok"
        assert result["count"] == 1
        assert result["fault_types"][0]["device_type"] == "injection_ospf_issues"

    def test_get_index(self):
        result = injection_skills_handler({"device_type": "injection_ospf_issues", "detail": "index"}, {})
        assert result["status"] == "ok"
        assert result["skill"]["issues"] == {
            "ospf_hello_dead_mismatch": "Hello/Dead Mismatch",
            "ospf_area_mismatch": "Area Mismatch",
        }

    def test_get_single_issue(self):
        result = injection_skills_handler(
            {"device_type": "injection_ospf_issues", "issue": "ospf_hello_dead_mismatch"}, {}
        )
        assert result["status"] == "ok"
        assert set(result["skill"]["issue"]) == {"ospf_hello_dead_mismatch"}

    def test_unknown_category_lists_available(self):
        result = injection_skills_handler({"device_type": "injection_ospf"}, {})
        assert result["status"] == "failed"
        assert "Unknown injection fault type" in result["error"]
        assert set(result["available_fault_types"]) == set(FAKE_INJECTION_SKILLS)

    def test_missing_device_type(self):
        result = injection_skills_handler({"action": "get"}, {})
        assert result["status"] == "failed"
        assert "Provide device_type" in result["error"]

    def test_uninitialized_repository_reports_failure(self, monkeypatch):
        monkeypatch.setattr(skills_registry, "INJECTION_SKILLS_REGISTRY", {})
        monkeypatch.setattr(skills_registry, "get_skills_manager", lambda: None)
        result = injection_skills_handler({"action": "list", "context": ["ospf"]}, {})
        assert result["status"] == "failed"
        assert "not initialized" in result["error"]
