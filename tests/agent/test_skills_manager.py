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
Tests for SkillsManager repository robustness and per-category reloads.
"""

import shutil

import pytest

from gns3server.agent.gns3_copilot.skills import registry
from gns3server.agent.gns3_copilot.skills.manager import SkillsManager
from gns3server.config import Config

DEVICE_YAML = """
name: "VPCS"
description: "VPCS test device"
device_type: "gns3_vpcs_telnet"
category: "device"
config_commands:
  ip_config:
    syntax: "ip <address>/<mask>"
"""

FEATURE_YAML = """
name: "Topology Planner"
description: "Plan topologies"
device_type: "topology_planner"
category: "feature"
"""


@pytest.fixture
def skills_root(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "config_dir", property(lambda self: str(tmp_path)))
    root = tmp_path / "skills"
    root.mkdir()
    return root


@pytest.fixture(autouse=True)
def fake_registries(monkeypatch):
    """Isolate the module registries: each test starts from empty dicts."""
    monkeypatch.setattr(registry, "SKILLS_REGISTRY", {})
    monkeypatch.setattr(registry, "INJECTION_SKILLS_REGISTRY", {})
    monkeypatch.setattr(registry, "PACKET_ANALYSIS_REGISTRY", {})


def write_skill(root, category, filename, content):
    directory = root / category
    directory.mkdir(exist_ok=True)
    (directory / filename).write_text(content, encoding="utf-8")


class TestRepositoryInitialization:
    def test_non_git_directory_is_used_as_is(self, skills_root):
        # A manually copied/cloned checkout without .git must still load;
        # cloning into a non-empty directory cannot work.
        write_skill(skills_root, "device", "vpcs.yaml", DEVICE_YAML)

        manager = SkillsManager()
        assert manager.initialize() is True
        assert not (skills_root / ".git").exists()
        assert manager.reload_skills() is True
        assert "gns3_vpcs_telnet" in registry.SKILLS_REGISTRY

    def test_update_reinitializes_after_directory_disappears(self, skills_root, monkeypatch):
        write_skill(skills_root, "device", "vpcs.yaml", DEVICE_YAML)
        manager = SkillsManager()
        assert manager.initialize() is True

        shutil.rmtree(skills_root)
        cloned = []
        monkeypatch.setattr(manager, "_clone", lambda: cloned.append(True) or True)

        manager._update_if_needed()
        assert cloned == [True]


class TestReloadSkills:
    def test_device_loads_when_injection_directory_missing(self, skills_root):
        write_skill(skills_root, "device", "vpcs.yaml", DEVICE_YAML)

        manager = SkillsManager()
        assert manager.initialize() is True
        assert manager.reload_skills() is True
        assert "gns3_vpcs_telnet" in registry.SKILLS_REGISTRY

    def test_missing_injection_keeps_existing_entries(self, skills_root):
        write_skill(skills_root, "device", "vpcs.yaml", DEVICE_YAML)
        registry.INJECTION_SKILLS_REGISTRY["injection_ospf"] = {
            "name": "OSPF",
            "description": "existing",
            "issues": {},
        }

        manager = SkillsManager()
        assert manager.initialize() is True
        assert manager.reload_skills() is True
        assert "injection_ospf" in registry.INJECTION_SKILLS_REGISTRY

    def test_missing_device_directory_keeps_existing_device_skills(self, skills_root):
        write_skill(skills_root, "feature", "topology_planner.yaml", FEATURE_YAML)
        registry.SKILLS_REGISTRY["old_device"] = {
            "name": "Old Device",
            "description": "existing",
            "category": "device",
        }

        manager = SkillsManager()
        assert manager.initialize() is True
        assert manager.reload_skills() is True
        assert "old_device" in registry.SKILLS_REGISTRY
        assert "topology_planner" in registry.SKILLS_REGISTRY

    def test_no_categories_loaded_returns_false(self, skills_root):
        manager = SkillsManager()
        manager._repo = None
        assert manager.reload_skills() is False


class TestReloadPacketAnalysis:
    def test_missing_directory_keeps_existing_protocols(self, skills_root):
        registry.PACKET_ANALYSIS_REGISTRY["ospf"] = {"name": "OSPF"}

        manager = SkillsManager()
        manager._repo = None
        assert manager.reload_packet_analysis_protocols() is False
        assert "ospf" in registry.PACKET_ANALYSIS_REGISTRY
