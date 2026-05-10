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
Skills Loader

This module provides functionality to load skills from YAML files.
Supports loading injection skills and device/feature skills.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)


class SkillsLoader:
    """
    Load skills from YAML files in the skills directory.

    This loader reads YAML files and converts them to the skill dictionary
    format expected by the skills registry.
    """

    def __init__(self, skills_dir: str):
        """
        Initialize the skills loader.

        Args:
            skills_dir: Path to the skills directory containing YAML files
        """
        self.skills_dir = Path(skills_dir)
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory does not exist: {self.skills_dir}")

    def load_injection_skills(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all injection skills from YAML files.

        Returns:
            Dictionary mapping skill keys to skill definitions
        """
        if yaml is None:
            logger.error("PyYAML is not installed. Cannot load skills from YAML.")
            return {}

        skills = {}
        injection_dir = self.skills_dir / "injection"

        if not injection_dir.exists():
            logger.warning(f"Injection skills directory not found: {injection_dir}")
            return {}

        for yaml_file in injection_dir.glob("*.yaml"):
            try:
                skill_data = self._load_yaml(yaml_file)
                if not skill_data:
                    logger.warning(f"Skipping empty YAML file: {yaml_file}")
                    continue
                # Generate key from filename (e.g., "ospf_issues.yaml" -> "injection_ospf")
                skill_key = f"injection_{yaml_file.stem}"
                skills[skill_key] = skill_data
                logger.debug(f"Loaded injection skill: {skill_key} from {yaml_file}")
            except Exception as e:
                logger.error(f"Failed to load skill from {yaml_file}: {e}")

        logger.debug(f"Loaded {len(skills)} injection skills from {injection_dir}")
        return skills

    def load_device_skills(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all device/feature skills from YAML files.

        Returns:
            Dictionary mapping skill keys to skill definitions
        """
        if yaml is None:
            logger.error("PyYAML is not installed. Cannot load skills from YAML.")
            return {}

        skills = {}
        device_dir = self.skills_dir / "device"

        if not device_dir.exists():
            logger.warning(f"Device skills directory not found: {device_dir}")
            return {}

        for yaml_file in device_dir.glob("*.yaml"):
            try:
                skill_data = self._load_yaml(yaml_file)
                if not skill_data:
                    logger.warning(f"Skipping empty YAML file: {yaml_file}")
                    continue
                # Use device_type from YAML content as the key
                # Fallback to filename stem if device_type not present
                skill_key = skill_data.get("device_type") if isinstance(skill_data, dict) else None
                if not skill_key:
                    skill_key = yaml_file.stem
                    logger.warning(f"No device_type in {yaml_file}, using filename '{skill_key}' as key")
                skills[skill_key] = skill_data
                logger.debug(f"Loaded device skill: {skill_key} from {yaml_file}")
            except Exception as e:
                logger.error(f"Failed to load skill from {yaml_file}: {e}")

        logger.info(f"Loaded {len(skills)} device skills from {device_dir}")
        return skills

    def load_prompt(self, prompt_name: str) -> str:
        """
        Load a prompt from a markdown file.

        Args:
            prompt_name: Name of the prompt file (without .md extension)

        Returns:
            Prompt content as string, or empty string if not found
        """
        prompts_dir = self.skills_dir / "prompts"
        prompt_file = prompts_dir / f"{prompt_name}.md"

        if not prompt_file.exists():
            logger.warning(f"Prompt file not found: {prompt_file}")
            return ""

        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                content = f.read()
            logger.debug(f"Loaded prompt: {prompt_name} from {prompt_file}")
            return content
        except Exception as e:
            logger.error(f"Failed to load prompt from {prompt_file}: {e}")
            return ""

    def load_forbidden_commands(self) -> list:
        """
        Load forbidden commands from the config directory.

        Returns:
            List of forbidden command patterns, or empty list if not found
        """
        config_dir = self.skills_dir / "config"
        config_file = config_dir / "forbidden_commands.txt"

        if not config_file.exists():
            logger.warning(f"Forbidden commands file not found: {config_file}")
            return []

        try:
            commands = []
            with open(config_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    commands.append(line.lower())
            logger.debug(f"Loaded {len(commands)} forbidden commands from {config_file}")
            return commands
        except Exception as e:
            logger.error(f"Failed to load forbidden commands from {config_file}: {e}")
            return []

    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """
        Load a YAML file and return its content.

        Args:
            file_path: Path to the YAML file

        Returns:
            Parsed YAML content as dictionary, or empty dict if file is empty
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            logger.warning(f"YAML file {file_path} is empty or has invalid format")
            return {}
        return data

    def validate_skill_format(self, skill_data: Dict[str, Any]) -> bool:
        """
        Validate that a skill dictionary has the required fields.

        Args:
            skill_data: Skill dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["name", "description", "issues"]
        for field in required_fields:
            if field not in skill_data:
                logger.error(f"Skill missing required field: {field}")
                return False

        if not isinstance(skill_data["issues"], dict):
            logger.error("Skill 'issues' field must be a dictionary")
            return False

        for issue_key, issue_data in skill_data["issues"].items():
            if not isinstance(issue_data, dict):
                logger.error(f"Issue '{issue_key}' must be a dictionary")
                return False

            issue_required = ["name", "description"]
            for field in issue_required:
                if field not in issue_data:
                    logger.error(f"Issue '{issue_key}' missing required field: {field}")
                    return False

        return True
