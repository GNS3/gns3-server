# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# This file is part of GNS3-Copilot project.
#
# GNS3-Copilot is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# GNS3-Copilot is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (C) 2025 Yue Guobin
# Author: Yue Guobin
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Skills Package

This package provides skills management for GNS3 Copilot.
All skills are loaded from the external GNS3-Skills repository.

Directory Structure:
- skills/
  - registry.py      # SKILLS_REGISTRY and get_skill()
  - manager.py       # SkillsManager - Git clone/pull and hot reload
  - loader.py        # SkillsLoader - YAML/Markdown file loading
"""

from .registry import (
    SKILLS_REGISTRY,
    INJECTION_SKILLS_REGISTRY,
    get_skill,
    get_injection_skill,
    DeviceSkillsTool,
    InjectionSkillsTool,
    PacketAnalysisSkillsTool,
    set_skills_manager,
    get_skills_manager,
    reload_injection_skills,
    reload_forbidden_commands,
    reload_skills_repository,
    get_skills_repository_info,
)
from .manager import SkillsManager
from .loader import SkillsLoader

__all__ = [
    "SKILLS_REGISTRY",
    "INJECTION_SKILLS_REGISTRY",
    "get_skill",
    "get_injection_skill",
    "DeviceSkillsTool",
    "InjectionSkillsTool",
    "PacketAnalysisSkillsTool",
    "SkillsManager",
    "SkillsLoader",
    "set_skills_manager",
    "get_skills_manager",
    "reload_injection_skills",
    "reload_skills_repository",
    "get_skills_repository_info",
]
