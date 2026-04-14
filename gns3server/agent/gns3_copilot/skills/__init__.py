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
Device Skills Package

This package provides device-specific skills for GNS3 Copilot.
Skills are organized by vendor and product series for easy extensibility.

Directory Structure:
- skills/
  - registry.py      # SKILLS_REGISTRY and get_skill()
  - cisco/           # Cisco devices
  - huawei/          # Huawei devices
  - h3c/             # H3C devices
  - ruijie/          # Ruijie devices
  - vpcs/            # GNS3 VPCS
  - generic/          # Base templates
"""

from .registry import SKILLS_REGISTRY, get_skill, DeviceSkillsTool

__all__ = [
    "SKILLS_REGISTRY",
    "get_skill",
    "DeviceSkillsTool",
]
