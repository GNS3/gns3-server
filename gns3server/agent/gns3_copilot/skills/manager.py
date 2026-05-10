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
Skills Manager

This module provides functionality to manage the skills repository,
including Git operations and hot reload of skills.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import git
except ImportError:
    git = None

from gns3server.config import Config
from .loader import SkillsLoader

logger = logging.getLogger(__name__)

# Git timeout settings for network operations.
# Applied per-command via the `env` parameter to avoid polluting
# the global process environment.
_GIT_TIMEOUT_ENV = {
    'GIT_HTTP_TIMEOUT': '10',           # Connection timeout (default: 120s)
    'GIT_HTTP_LOW_SPEED_TIME': '5',     # Slow speed threshold window
    'GIT_HTTP_LOW_SPEED_LIMIT': '1000', # < 1 KB/s = slow → abort
}


class SkillsManager:
    """
    Manage skills repository and hot reload functionality.

    This class handles:
    - Cloning the skills repository
    - Pulling latest updates
    - Hot reloading skills into memory
    - Version tracking
    """

    def __init__(
        self,
        repo_url: str = None,
        branch: str = "main",
        auto_update: bool = False
    ):
        """
        Initialize the skills manager.

        Args:
            repo_url: Git repository URL (default: https://github.com/yueguobin/GNS3-Skills.git)
            branch: Git branch to use (default: "main")
            auto_update: Whether to automatically pull updates on reload
        """
        if repo_url is None:
            repo_url = "https://github.com/yueguobin/GNS3-Skills.git"

        # Get local path from GNS3 config directory
        config_dir = Config.instance().config_dir
        local_path = os.path.join(config_dir, "skills")

        self.repo_url = repo_url
        self.local_path = Path(local_path)
        self.branch = branch
        self.auto_update = auto_update
        self.loader = SkillsLoader(str(local_path))
        self._repo: Optional["git.Repo"] = None
        self._prompt_count = 0

        if git is None:
            logger.warning("GitPython is not installed. Skills management features will be limited.")

    def initialize(self) -> bool:
        """
        Initialize the skills repository.

        Behavior:
        - If no local repo → clone from remote
        - If local repo exists → open and run _update_if_needed()

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.local_path.exists():
                logger.info(f"Creating skills directory: {self.local_path}")
                self.local_path.mkdir(parents=True, exist_ok=True)

            if not (self.local_path / ".git").exists():
                return self._clone()

            # Repo exists, open it
            try:
                self._repo = git.Repo(self.local_path)
            except Exception as e:
                logger.error(f"Failed to open existing repository: {e}")
                return False

            self._update_if_needed()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize skills repository: {e}")
            return False

    def _update_if_needed(self) -> None:
        """
        Check local repo status and pull updates if safe.

        - Uncommitted changes → warn and skip
        - Behind remote → pull
        - Up to date → nothing
        - Network error → use existing files, log warning
        """
        if git is None or self._repo is None:
            return

        # Check for uncommitted changes
        if self._repo.is_dirty(untracked_files=True):
            logger.warning(
                "Skills repository has uncommitted changes, skipping pull. "
                "Commit or stash changes in %s to enable automatic updates.",
                self.local_path
            )
            return

        # Fetch remote
        try:
            origin = self._repo.remotes.origin
            origin.fetch(env=_GIT_TIMEOUT_ENV)
        except Exception as e:
            logger.warning(f"Failed to fetch remote: {e}. Using local files.")
            return

        # Check if behind and pull
        try:
            behind_commits = list(self._repo.iter_commits(
                f'{self.branch}..origin/{self.branch}'
            ))
            if behind_commits:
                logger.info(
                    "Skills repository is behind by %d commit(s), pulling...",
                    len(behind_commits)
                )
                origin.pull(self.branch, env=_GIT_TIMEOUT_ENV)
                logger.info(f"Updated to commit {self.get_current_version()}")
            else:
                logger.info("Skills repository is up to date")
        except Exception as e:
            logger.warning(f"Failed to pull updates: {e}. Using local files.")

    def _clone(self) -> bool:
        """
        Clone the skills repository.

        Returns:
            True if successful, False otherwise
        """
        if git is None:
            logger.error("GitPython is not installed. Cannot clone repository.")
            return False

        try:
            self._repo = git.Repo.clone_from(
                self.repo_url,
                self.local_path,
                branch=self.branch,
                env=_GIT_TIMEOUT_ENV
            )
            logger.info(f"Successfully cloned skills repository to {self.local_path}")
            return True
        except git.GitCommandError as e:
            logger.error(f"Git clone failed: {e}")
            return False

    def reload_skills(self) -> bool:
        """
        Hot reload skills from YAML files into the registry.

        Loads the latest skill definitions from YAML files and updates
        the INJECTION_SKILLS_REGISTRY.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Import here to avoid circular dependency
            from .registry import INJECTION_SKILLS_REGISTRY, SKILLS_REGISTRY

            # Load new injection skills from YAML files
            new_injection_skills = self.loader.load_injection_skills()

            if not new_injection_skills:
                logger.warning("No injection skills loaded, keeping existing skills")
                return False

            # Validate injection skills
            for skill_key, skill_data in new_injection_skills.items():
                if not self.loader.validate_skill_format(skill_data):
                    logger.error(f"Invalid skill format for {skill_key}, skipping")
                    continue

            # Load new device/feature skills from YAML files
            new_device_skills = self.loader.load_device_skills()

            # Update registries (safe replace - never leaves dict empty)
            for k in list(INJECTION_SKILLS_REGISTRY):
                if k not in new_injection_skills:
                    del INJECTION_SKILLS_REGISTRY[k]
            INJECTION_SKILLS_REGISTRY.update(new_injection_skills)

            for k in list(SKILLS_REGISTRY):
                if k not in new_device_skills:
                    del SKILLS_REGISTRY[k]
            SKILLS_REGISTRY.update(new_device_skills)

            logger.debug(f"Successfully reloaded {len(new_injection_skills)} injection skills and {len(new_device_skills)} device skills")
            return True
        except Exception as e:
            logger.error(f"Failed to reload skills: {e}")
            return False

    def reload_prompts(self) -> bool:
        """
        Hot reload prompts from Markdown files.

        Loads the latest prompt definitions from Markdown files in
        the skills repository.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Available prompt names
            prompt_names = [
                "lab_automation_assistant",
                "teaching_assistant",
                "troubleshooting_injection",
                "title"
            ]

            # Load all prompts
            loaded_count = 0
            for prompt_name in prompt_names:
                prompt_content = self.loader.load_prompt(prompt_name)
                if prompt_content:
                    loaded_count += 1
                else:
                    logger.warning(f"Failed to load prompt: {prompt_name}")

            if loaded_count == 0:
                logger.warning("No prompts loaded, keeping existing prompts")
                return False

            self._prompt_count = loaded_count
            logger.debug(f"Successfully reloaded {loaded_count} prompts")
            return True
        except Exception as e:
            logger.error(f"Failed to reload prompts: {e}")
            return False

    def load_prompt(self, prompt_name: str) -> str:
        """
        Load a specific prompt from the skills repository.

        Args:
            prompt_name: Name of the prompt (without .md extension)

        Returns:
            Prompt content as string, or empty string if not found
        """
        try:
            return self.loader.load_prompt(prompt_name)
        except Exception as e:
            logger.error(f"Failed to load prompt '{prompt_name}': {e}")
            return ""

    def load_forbidden_commands(self) -> list:
        """
        Load forbidden command patterns from the skills repository.

        Returns:
            List of forbidden command patterns, or empty list if not found
        """
        try:
            return self.loader.load_forbidden_commands()
        except Exception as e:
            logger.error(f"Failed to load forbidden commands: {e}")
            return []

    def get_current_version(self) -> str:
        """
        Get the current git commit hash of the skills repository.

        Returns:
            Commit hash as string, or empty string if not available
        """
        if git is None or self._repo is None:
            try:
                self._repo = git.Repo(self.local_path)
            except Exception:
                return ""

        try:
            return self._repo.head.commit.hexsha
        except Exception:
            return ""

    def get_skill_count(self) -> int:
        """
        Get the number of currently loaded injection skills.

        Returns:
            Number of skills in the registry
        """
        try:
            from .registry import INJECTION_SKILLS_REGISTRY
            return len(INJECTION_SKILLS_REGISTRY)
        except Exception:
            return 0

    def get_prompt_count(self) -> int:
        """
        Get the number of currently loaded prompts.

        Returns:
            Number of prompts loaded
        """
        return self._prompt_count

    def get_repository_info(self) -> Dict[str, Any]:
        """
        Get information about the skills repository.

        Returns:
            Dictionary containing repository information
        """
        return {
            "repo_url": self.repo_url,
            "local_path": str(self.local_path),
            "branch": self.branch,
            "current_version": self.get_current_version(),
            "skill_count": self.get_skill_count(),
            "prompt_count": self.get_prompt_count(),
            "auto_update": self.auto_update,
            "is_initialized": (self.local_path / ".git").exists()
        }

    def rollback(self, commit_hash: str) -> bool:
        """
        Rollback the skills repository to a specific commit.

        Args:
            commit_hash: Git commit hash to rollback to

        Returns:
            True if successful, False otherwise
        """
        if git is None:
            logger.error("GitPython is not installed. Cannot rollback.")
            return False

        try:
            if self._repo is None:
                self._repo = git.Repo(self.local_path)

            self._repo.git.reset("--hard", commit_hash)
            logger.info(f"Successfully rolled back to commit {commit_hash}")

            # Reload skills after rollback
            return self.reload_skills()
        except git.GitCommandError as e:
            logger.error(f"Git rollback failed: {e}")
            return False

    def get_available_versions(self, limit: int = 10) -> list:
        """
        Get a list of recent commit hashes.

        Args:
            limit: Maximum number of commits to return

        Returns:
            List of commit information dictionaries
        """
        if git is None:
            return []

        try:
            if self._repo is None:
                self._repo = git.Repo(self.local_path)

            commits = []
            for commit in self._repo.iter_commits(max_count=limit):
                commits.append({
                    "hash": commit.hexsha,
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat()
                })
            return commits
        except Exception as e:
            logger.error(f"Failed to get commit history: {e}")
            return []
