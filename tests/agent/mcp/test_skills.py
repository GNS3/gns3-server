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
Unit tests for the MCP device skills tool (registry faked, no I/O).
"""

import pytest

from gns3server.agent.gns3_copilot.skills import registry as skills_registry
from gns3server.agent.mcp.skills import device_skills_handler

FAKE_SKILLS = {
    "frr_vtysh": {
        "name": "FRR",
        "description": "vtysh console model",
        "category": "device",
        "topics": {"bgp": {"name": "BGP", "syntax": "router bgp <asn>"}},
    },
    "cisco_ios_telnet": {"name": "IOS", "description": "IOS quirks", "category": "device"},
    "gns3_vpcs_telnet": {"name": "VPCS", "description": "VPCS syntax", "category": "device"},
}


@pytest.fixture(autouse=True)
def fake_registry(monkeypatch):
    """Deterministic skills registry — the real one depends on whether the
    skills repository has been cloned on this machine."""
    monkeypatch.setattr(skills_registry, "SKILLS_REGISTRY", FAKE_SKILLS)


class TestDeviceSkillsHandler:
    def test_list(self):
        result = device_skills_handler({"action": "list"}, {})
        assert result["status"] == "ok"
        assert result["count"] == 3
        assert {s["device_type"] for s in result["skills"]} == set(FAKE_SKILLS)

    def test_no_args_defaults_to_list(self):
        result = device_skills_handler({}, {})
        assert result["status"] == "ok" and result["count"] == 3

    def test_get_by_key(self):
        result = device_skills_handler({"device_type": "frr_vtysh"}, {})
        assert result["status"] == "ok"
        assert result["skill"]["name"] == "FRR"

    def test_topic_body_only_on_explicit_request(self):
        indexed = device_skills_handler({"device_type": "frr_vtysh"}, {})["skill"]
        assert indexed["topics"]["bgp"] == "BGP"  # index: names only, body withheld

        topic = device_skills_handler({"device_type": "frr_vtysh", "topic": "bgp"}, {})["skill"]
        assert topic["topic"] == {"bgp": {"name": "BGP", "syntax": "router bgp <asn>"}}

    def test_unknown_key_lists_available(self):
        # Not a key the list would return — the error carries the loaded
        # keys anyway, so a stale caller can see what step 1 offers.
        result = device_skills_handler({"device_type": "cisco_asa"}, {})
        assert result["status"] == "failed"
        assert "Unknown device_type" in result["error"]
        assert set(result["available_device_types"]) == set(FAKE_SKILLS)

    def test_missing_device_type(self):
        result = device_skills_handler({"action": "get"}, {})
        assert result["status"] == "failed"
        assert "Provide device_type" in result["error"]
