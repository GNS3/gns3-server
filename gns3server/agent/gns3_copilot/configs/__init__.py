# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# Copyright (C) 2025 Yue Guobin
#

"""
Configuration package for GNS3 Copilot.
"""

from .skills_config import (
    SKILLS_CONFIG,
    get_skills_config,
    update_skills_config,
)

__all__ = [
    "SKILLS_CONFIG",
    "get_skills_config",
    "update_skills_config",
]
