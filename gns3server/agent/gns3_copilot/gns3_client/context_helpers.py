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
Request-Scoped Context Helpers for GNS3-Copilot

This module provides context variable management for request-scoped data
(JWT tokens and LLM configurations) using Python's contextvars module.

These functions are separated into their own module to avoid circular imports
between agent_service.py, gns3_copilot.py, and gns3_client modules.

Key Features:
- Thread-safe and async-safe request-scoped context management
- Automatic cleanup when request context ends
- No manual cleanup required

Usage:
    from gns3server.agent.gns3_copilot.gns3_client.context_helpers import (
        set_current_jwt_token,
        get_current_jwt_token,
        set_current_llm_config,
        get_current_llm_config,
    )

    # In request handler
    set_current_jwt_token(token)
    set_current_llm_config(config)

    # In downstream code
    token = get_current_jwt_token()
    config = get_current_llm_config()
"""

import logging
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

# Context variables for request-scoped data
# Automatically cleaned up when request context ends
_jwt_token_context: ContextVar[Optional[str]] = ContextVar(
    "_jwt_token_context", default=None
)
_llm_config_context: ContextVar[Optional[dict]] = ContextVar(
    "_llm_config_context", default=None
)


def set_current_jwt_token(token: str) -> None:
    """Set the JWT token for the current request context.

    Args:
        token: JWT token string
    """
    _jwt_token_context.set(token)
    logger.debug("JWT token set in context")


def get_current_jwt_token() -> Optional[str]:
    """Get the JWT token for the current request context.

    Returns:
        JWT token string if available, None otherwise
    """
    token = _jwt_token_context.get()
    if token:
        logger.debug("JWT token retrieved from context")
    else:
        logger.warning("JWT token not found in context")
    return token


def set_current_llm_config(config: dict) -> None:
    """Set the LLM config for the current request context.

    Args:
        config: LLM configuration dictionary with provider, model, api_key,
                etc.
    """
    _llm_config_context.set(config)
    logger.debug(
        "LLM config set in context: provider=%s, model=%s",
        config.get("provider"),
        config.get("model"),
    )


def get_current_llm_config() -> Optional[dict]:
    """Get the LLM config for the current request context.

    Returns:
        LLM configuration dict if available, None otherwise
    """
    config = _llm_config_context.get()
    if config:
        logger.debug(
            "LLM config retrieved from context: provider=%s, model=%s",
            config.get("provider"),
            config.get("model"),
        )
    else:
        logger.warning("LLM config not found in context")
    return config


__all__ = [
    "set_current_jwt_token",
    "get_current_jwt_token",
    "set_current_llm_config",
    "get_current_llm_config",
]
