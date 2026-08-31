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

"""
Tests for device skill topic splitting: directory layout loading
(_base.yaml + topic files) and topic-level retrieval via get_skill /
DeviceSkillsTool.
"""

import pytest

from gns3server.agent.gns3_copilot.skills.loader import SkillsLoader
from gns3server.agent.gns3_copilot.skills.registry import (
    DeviceSkillsTool,
    get_skill,
)


@pytest.fixture
def skills_dir(tmp_path):
    """
    Build a skills directory with both device layouts:

    - vpcs.yaml: single-file device (no topics)
    - frr/: split device (_base.yaml + ospf/bgp topic files,
      one mismatched topic file, one file without a topic field)
    - orphan/: directory without _base.yaml (skipped)
    """
    device_dir = tmp_path / "device"
    device_dir.mkdir()

    (device_dir / "vpcs.yaml").write_text(
        """
name: "VPCS"
description: "VPCS test device"
device_type: "gns3_vpcs_telnet"
category: "device"
config_commands:
  ip_config:
    syntax: "ip <address>/<mask> <gateway>"
    description: "Set PC address"
""",
        encoding="utf-8",
    )

    frr_dir = device_dir / "frr"
    frr_dir.mkdir()
    (frr_dir / "_base.yaml").write_text(
        """
name: "FRR (Free Range Routing)"
description: "FRR test device"
device_type: "frr_vtysh"
category: "device"
config_commands:
  write_memory:
    syntax: "write memory"
    description: "Save config"
""",
        encoding="utf-8",
    )
    (frr_dir / "ospf.yaml").write_text(
        """
device_type: "frr_vtysh"
topic: ospf
name: "OSPF (FRR 10.x)"
description: "OSPF topic"
config_commands:
  ospfv2:
    syntax: "router ospf"
    description: "OSPFv2 process"
""",
        encoding="utf-8",
    )
    (frr_dir / "bgp.yaml").write_text(
        """
device_type: "frr_vtysh"
topic: bgp
name: "BGP (FRR 10.x)"
description: "BGP topic"
config_commands:
  bgp_base:
    syntax: "router bgp <asn>"
    description: "BGP base"
""",
        encoding="utf-8",
    )
    # device_type mismatch with the base -> topic must be skipped
    (frr_dir / "mpls.yaml").write_text(
        """
device_type: "other_device_type"
topic: mpls
name: "MPLS"
config_commands:
  mpls_base:
    syntax: "router mpls"
    description: "..."
""",
        encoding="utf-8",
    )
    # no topic field -> falls back to the filename stem
    (frr_dir / "static.yaml").write_text(
        """
device_type: "frr_vtysh"
name: "Static routing"
config_commands:
  static_routes:
    syntax: "ip route <prefix>/<len> <nexthop>"
    description: "..."
""",
        encoding="utf-8",
    )

    # directory without _base.yaml -> whole device skipped
    orphan_dir = device_dir / "orphan"
    orphan_dir.mkdir()
    (orphan_dir / "some_topic.yaml").write_text(
        """
device_type: "orphan_device"
topic: anything
name: "Orphan"
""",
        encoding="utf-8",
    )

    return tmp_path


class TestDeviceSkillsLoading:
    """
    SkillsLoader.load_device_skills() with single-file and split layouts.
    """

    def test_both_layouts_are_loaded(self, skills_dir):
        skills = SkillsLoader(str(skills_dir)).load_device_skills()

        assert "gns3_vpcs_telnet" in skills
        assert "frr_vtysh" in skills
        # the orphan directory (no _base.yaml) must not produce an entry
        assert "orphan_device" not in skills
        assert len(skills) == 2

    def test_topics_are_merged_under_topics(self, skills_dir):
        skills = SkillsLoader(str(skills_dir)).load_device_skills()
        frr = skills["frr_vtysh"]

        # base-level content stays at the top level
        assert frr["config_commands"]["write_memory"]["syntax"] == "write memory"
        assert frr["category"] == "device"

        topics = frr["topics"]
        assert topics["ospf"]["name"] == "OSPF (FRR 10.x)"
        assert topics["bgp"]["config_commands"]["bgp_base"]["syntax"] == "router bgp <asn>"
        # file without a topic field falls back to its filename stem
        assert "static" in topics
        # mismatched device_type is skipped
        assert "mpls" not in topics

    def test_topic_metadata_is_stripped(self, skills_dir):
        skills = SkillsLoader(str(skills_dir)).load_device_skills()
        for topic_data in skills["frr_vtysh"]["topics"].values():
            assert "device_type" not in topic_data
            assert "topic" not in topic_data
            assert "category" not in topic_data
            assert "topics" not in topic_data

    def test_single_file_device_has_no_topics_key(self, skills_dir):
        skills = SkillsLoader(str(skills_dir)).load_device_skills()
        assert "topics" not in skills["gns3_vpcs_telnet"]


@pytest.fixture
def device_registry():
    """
    Populate SKILLS_REGISTRY with a split device and a single-file device,
    restoring the previous content afterwards.
    """
    from gns3server.agent.gns3_copilot.skills import registry

    saved = dict(registry.SKILLS_REGISTRY)
    registry.SKILLS_REGISTRY.clear()
    registry.SKILLS_REGISTRY.update(
        {
            "frr_vtysh": {
                "name": "FRR (Free Range Routing)",
                "description": "FRR test device",
                "category": "device",
                "config_commands": {"write_memory": {"syntax": "write memory"}},
                "topics": {
                    "ospf": {
                        "name": "OSPF (FRR 10.x)",
                        "description": "OSPF topic",
                        "config_commands": {"ospfv2": {"syntax": "router ospf"}},
                    },
                    "bgp": {
                        "name": "BGP (FRR 10.x)",
                        "description": "BGP topic",
                        "config_commands": {"bgp_base": {"syntax": "router bgp <asn>"}},
                    },
                },
            },
            "gns3_vpcs_telnet": {
                "name": "VPCS",
                "description": "VPCS test device",
                "category": "device",
                "config_commands": {"ip_config": {"syntax": "ip <address>/<mask>"}},
            },
        }
    )
    yield registry
    registry.SKILLS_REGISTRY.clear()
    registry.SKILLS_REGISTRY.update(saved)


class TestGetSkillTopics:
    """
    Topic-level retrieval and topic index behavior in get_skill().
    """

    def test_topic_lookup_returns_topic_body(self, device_registry):
        result = get_skill("frr_vtysh", topic="bgp")
        assert result["device_type"] == "frr_vtysh"
        assert result["skill_name"] == "FRR (Free Range Routing)"
        assert result["topic"]["bgp"]["config_commands"]["bgp_base"]["syntax"] == "router bgp <asn>"

    def test_topic_lookup_is_case_insensitive(self, device_registry):
        result = get_skill("frr_vtysh", topic="BGP")
        assert "bgp" in result["topic"]

    def test_unknown_topic_lists_available_topics(self, device_registry):
        result = get_skill("frr_vtysh", topic="mpls")
        assert "error" in result
        assert sorted(result["available_topics"]) == ["bgp", "ospf"]

    def test_full_without_topic_returns_index_not_bodies(self, device_registry):
        result = get_skill("frr_vtysh", detail="full")
        # base-level content is included...
        assert result["config_commands"]["write_memory"]["syntax"] == "write memory"
        # ...but topic bodies are never included without an explicit topic
        assert result["topics"] == {
            "ospf": "OSPF (FRR 10.x)",
            "bgp": "BGP (FRR 10.x)",
        }
        assert "config_commands" not in result["topics"]["ospf"]

    def test_index_includes_topic_index(self, device_registry):
        result = get_skill("frr_vtysh", detail="index")
        assert result["topics"]["bgp"] == "BGP (FRR 10.x)"

    def test_summary_includes_topic_descriptions(self, device_registry):
        result = get_skill("frr_vtysh", detail="summary")
        assert result["topics"]["ospf"] == {
            "name": "OSPF (FRR 10.x)",
            "description": "OSPF topic",
        }

    def test_single_file_device_still_works(self, device_registry):
        result = get_skill("gns3_vpcs_telnet")
        assert result["config_commands"]["ip_config"]["syntax"] == "ip <address>/<mask>"
        assert "topics" not in result


class TestDeviceSkillsToolTopics:
    """
    DeviceSkillsTool passes the topic parameter through to get_skill().
    """

    def test_tool_topic_request(self, device_registry):
        import json

        tool = DeviceSkillsTool()
        result = json.loads(tool._run('{"device_type": "frr_vtysh", "topic": "ospf"}'))
        assert result["topic"]["ospf"]["config_commands"]["ospfv2"]["syntax"] == "router ospf"

    def test_tool_list_shows_topic_counts(self, device_registry):
        import json

        tool = DeviceSkillsTool()
        result = json.loads(tool._run('{"action": "list"}'))
        by_type = {s["device_type"]: s for s in result["skills"]}
        assert by_type["frr_vtysh"]["topic_count"] == 2
        assert by_type["gns3_vpcs_telnet"]["topic_count"] == 0


class TestReloadSkillsValidation:
    """
    Invalid injection skills are dropped instead of merged into the registry.
    """

    def test_invalid_injection_skill_is_dropped(self, tmp_path, monkeypatch):
        from gns3server.config import Config
        from gns3server.agent.gns3_copilot.skills import registry
        from gns3server.agent.gns3_copilot.skills.manager import SkillsManager

        # SkillsManager derives its local path from <config_dir>/skills
        injection_dir = tmp_path / "skills" / "injection"
        injection_dir.mkdir(parents=True)
        (injection_dir / "valid.yaml").write_text(
            """
name: "OSPF Issues Injection"
description: "OSPF faults"
category: "injection"
issues:
  ospf_area_mismatch:
    name: "OSPF Area Mismatch"
    description: "Areas differ"
""",
            encoding="utf-8",
        )
        # missing the required "issues" field -> invalid, must be dropped
        (injection_dir / "broken.yaml").write_text(
            """
name: "Broken Injection"
description: "No issues field"
""",
            encoding="utf-8",
        )

        monkeypatch.setattr(Config, "config_dir", property(lambda self: str(tmp_path)))

        saved_injection = dict(registry.INJECTION_SKILLS_REGISTRY)
        saved_skills = dict(registry.SKILLS_REGISTRY)
        registry.INJECTION_SKILLS_REGISTRY.clear()
        registry.SKILLS_REGISTRY.clear()
        try:
            manager = SkillsManager(repo_url="https://example.invalid/gns3-skills.git")
            manager._repo = None
            assert manager.reload_skills() is True
            assert "injection_valid" in registry.INJECTION_SKILLS_REGISTRY
            assert "injection_broken" not in registry.INJECTION_SKILLS_REGISTRY
        finally:
            registry.INJECTION_SKILLS_REGISTRY.clear()
            registry.INJECTION_SKILLS_REGISTRY.update(saved_injection)
            registry.SKILLS_REGISTRY.clear()
            registry.SKILLS_REGISTRY.update(saved_skills)
