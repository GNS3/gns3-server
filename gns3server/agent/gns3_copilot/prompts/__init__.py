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
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Prompts Module for GNS3-Copilot

This package provides system prompts loading utilities for the GNS3-Copilot AI agent.

All system prompts are now loaded from the external GNS3-Skills repository:
https://github.com/yueguobin/GNS3-Skills

Available prompts (loaded from external repository):
- lab_automation_assistant.md: Lab automation mode (diagnostics + config)
- teaching_assistant.md: Teaching assistant mode (diagnostics only)
- troubleshooting_injection.md: Fault injection specialist
- title.md: Title generation prompt template

Use the SkillsManager to load these prompts:
    from gns3server.agent.gns3_copilot.skills.manager import skills_manager

    # Load prompts
    lab_prompt = skills_manager.load_prompt("lab_automation_assistant")
    teaching_prompt = skills_manager.load_prompt("teaching_assistant")
    injection_prompt = skills_manager.load_prompt("troubleshooting_injection")
    title_prompt = skills_manager.load_prompt("title")
"""

from .prompt_loader import load_system_prompt

__all__ = ["load_system_prompt"]
