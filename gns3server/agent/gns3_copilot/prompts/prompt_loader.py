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
# Copyright (C) 2025 Yue Guobin (� Yue Guobin)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Prompt Loader for GNS3-Copilot

This module provides utilities for loading system prompts from the external
GNS3-Skills repository.
Supports multiple prompt variants based on LLM model configuration.

Available Modes (controlled by config.copilot_mode in llm_model_configs):
- "teaching_assistant" (default): Teaching assistant mode - diagnostics only,
  no configuration
- "lab_automation_assistant": Full lab automation assistant mode - diagnostics
  and configuration enabled
- "troubleshooting_injection": Troubleshooting issue injection mode

All prompts are loaded from the external GNS3-Skills repository via SkillsManager.
"""

import logging

from gns3server.agent.gns3_copilot.skills.registry import get_prompt

logger = logging.getLogger(__name__)


def load_system_prompt(llm_config: dict | None = None) -> str:
    """
    Load the system prompt for GNS3-Copilot from the external repository.

    The prompt mode is controlled by the `copilot_mode` field in the LLM
    model config:
    - "teaching_assistant" (default): Teaching assistant mode - diagnostics
      only, no configuration
    - "lab_automation_assistant": Full lab automation assistant mode -
      diagnostics and configuration enabled
    - "troubleshooting_injection": Troubleshooting issue injection mode -
      inject network faults for practice

    Prompts are loaded from the external GNS3-Skills repository via SkillsManager.

    Args:
        llm_config: LLM model configuration dictionary (flattened structure
                   from get_user_llm_config_full)

    Returns:
        str: The system prompt string, or empty string if not found.
    """
    if not llm_config:
        logger.debug(
            "No LLM config provided, using default TEACHING_ASSISTANT "
            "prompt mode"
        )
        return _load_prompt("teaching_assistant")

    # llm_config is a flattened dict with copilot_mode at the top level
    # Example: {"provider": "...", "model": "...", "copilot_mode": "...", ...}
    mode = llm_config.get("copilot_mode", "teaching_assistant").lower()

    if mode == "lab_automation_assistant":
        logger.debug(
            "Using LAB_AUTOMATION_ASSISTANT prompt mode (diagnostics + "
            "configuration)"
        )
        return _load_prompt("lab_automation_assistant")
    elif mode == "troubleshooting_injection":
        logger.debug(
            "Using TROUBLESHOOTING_INJECTION prompt mode (fault injection)"
        )
        return _load_prompt("troubleshooting_injection")
    else:
        logger.debug("Using TEACHING_ASSISTANT prompt mode (diagnostics only)")
        return _load_prompt("teaching_assistant")


def _load_prompt(prompt_name: str) -> str:
    """
    Load a prompt from the external skills repository.

    Args:
        prompt_name: Name of the prompt (e.g., "teaching_assistant")

    Returns:
        Prompt content as string, or empty string if not found
    """
    prompt = get_prompt(prompt_name)
    if prompt:
        logger.debug(f"Loaded prompt '{prompt_name}' from external repository")
        return prompt

    logger.warning(f"Prompt '{prompt_name}' not found in external repository")
    return ""
