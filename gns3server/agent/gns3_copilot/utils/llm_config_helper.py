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

LLM Model Configuration Helper for GNS3 Copilot

This module provides utility functions to retrieve LLM model configurations
with decrypted API keys by directly accessing the database.

Usage:
    from gns3server.agent.gns3_copilot.utils.llm_config_helper import (
        get_user_llm_config_with_app,
    )

    # Get user's default LLM config (with API key)
    config = await get_user_llm_config_with_app(user_id, app)
    if config:
        provider = config['provider']
        api_key = config['api_key']
        model = config['model']
"""

import logging
from typing import Any
from typing import Dict
from typing import Optional
from uuid import UUID

from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def get_user_llm_config_with_app(
    user_id: UUID, app: FastAPI
) -> Optional[Dict[str, Any]]:
    """
    Get user's default LLM model configuration with decrypted API key.

    This function directly accesses the database through the app reference,
    bypassing API security restrictions to get the complete configuration including
    decrypted API keys, even for inherited group configurations.

    Args:
        user_id: User UUID
        app: FastAPI application instance

    Returns:
        Configuration dict with provider, api_key, model, etc., or None if not found

    Example:
        config = await get_user_llm_config_with_app(user_id, app)
        if config:
            print(f"Provider: {config['provider']}")
            print(f"Model: {config['model']}")
            print(f"API Key: {config['api_key']}")
            print(f"Source: {config['source']}")
    """
    from gns3server.db.tasks import get_user_llm_config_full

    try:
        user_id_str = str(user_id)
        config = await get_user_llm_config_full(user_id_str, app)

        if config:
            logger.info(
                f"Successfully retrieved LLM config for user {user_id}: "
                f"provider={config.get('provider')}, model={config.get('model')}"
            )
        else:
            logger.warning(f"No LLM configuration found for user {user_id}")

        return config

    except Exception as e:
        logger.error(
            f"Failed to retrieve LLM config for user {user_id}: {e}",
            exc_info=True,
        )
        return None
