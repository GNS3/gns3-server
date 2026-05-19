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
Model Factory for GNS3-Copilot Agent

This module provides factory functions to create fresh LLM model instances.
Configuration is passed directly from the database.

"""

import logging
from typing import Any
from typing import Optional

from langchain.chat_models import init_chat_model

logger = logging.getLogger(__name__)


def _load_llm_config(
    llm_config: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    """
    Convert llm_config dict to model factory format.

    Args:
        llm_config: Configuration dictionary from database

    Returns:
        Dictionary containing model configuration.

    Raises:
        ValueError: If configuration is missing or invalid.
    """
    if not llm_config:
        raise ValueError("LLM configuration is required")

    logger.info(
        "Using LLM config: provider=%s, model=%s",
        llm_config.get("provider"),
        llm_config.get("model"),
    )

    return {
        "model_name": llm_config.get("model", ""),
        "model_provider": llm_config.get("provider", ""),
        "api_key": llm_config.get("api_key", ""),
        "base_url": llm_config.get("base_url", ""),
        "temperature": str(llm_config.get("temperature", "0")),
    }


def create_base_model(
    llm_config: Optional[dict[str, Any]] = None,
) -> Any:
    """
    Create a fresh base LLM model instance.

    Args:
        llm_config: Configuration dictionary from database

    Returns:
        Any: A new LLM model instance configured with current settings.
              The actual type depends on the provider (e.g., ChatOpenAI, etc.).

    Raises:
        ValueError: If required configuration fields are missing or invalid.
        RuntimeError: If model creation fails.
    """
    config_vars = _load_llm_config(llm_config)

    # Log the loaded configuration (mask sensitive data)
    logger.info(
        "Creating base model: name=%s, provider=%s, base_url=%s, "
        "temperature=%s",
        config_vars["model_name"],
        config_vars["model_provider"],
        config_vars["base_url"] if config_vars["base_url"] else "default",
        config_vars["temperature"],
    )

    # Validate required fields
    if not config_vars["model_name"]:
        raise ValueError("LLM configuration requires 'model' field")

    if not config_vars["model_provider"]:
        raise ValueError("LLM configuration requires 'provider' field")

    try:
        # Prepare parameters for init_chat_model
        init_params = {
            "model": config_vars["model_name"],
            "model_provider": config_vars["model_provider"],
            "api_key": config_vars["api_key"],
            "base_url": config_vars["base_url"],
            "temperature": config_vars["temperature"],
            "configurable_fields": "any",
            "config_prefix": "foo",
        }

        # Disable DeepSeek thinking mode to avoid reasoning_content handling issues
        # DeepSeek models enable thinking mode by default, which returns reasoning_content
        # that must be passed back to the API in subsequent requests. To simplify
        # message handling and avoid 400 errors, we disable it here.
        if config_vars["model_provider"] == "deepseek":
            init_params["extra_body"] = {"thinking": {"type": "disabled"}}
            logger.debug("DeepSeek thinking mode disabled")

        model = init_chat_model(**init_params)

        logger.debug("Base model created successfully")
        return model

    except Exception as e:
        logger.error("Failed to create base model: %s", e)
        raise RuntimeError(f"Failed to create base model: {e}") from e


def create_title_model(
    llm_config: Optional[dict[str, Any]] = None,
) -> Any:
    """
    Create a fresh title generation model instance.

    This creates a model instance suitable for generating conversation titles.
    It uses the same configuration as the base model but with a higher
    temperature for more creative output.

    Args:
        llm_config: Configuration dictionary from database

    Returns:
        Any: A new LLM model instance for title generation.
              The actual type depends on the provider.

    Raises:
        ValueError: If required configuration fields are missing or invalid.
        RuntimeError: If model creation fails.
    """
    config_vars = _load_llm_config(llm_config)

    logger.info(
        "Creating title model: name=%s, provider=%s, base_url=%s, "
        "temperature=1.0",
        config_vars["model_name"],
        config_vars["model_provider"],
        config_vars["base_url"] if config_vars["base_url"] else "default",
    )

    # Validate required fields
    if not config_vars["model_name"]:
        raise ValueError("LLM configuration requires 'model' field")

    if not config_vars["model_provider"]:
        raise ValueError("LLM configuration requires 'provider' field")

    try:
        # Prepare parameters for init_chat_model
        init_params = {
            "model": config_vars["model_name"],
            "model_provider": config_vars["model_provider"],
            "api_key": config_vars["api_key"],
            "base_url": config_vars["base_url"],
            "temperature": "1.0",  # Higher temperature for more creative titles
            "configurable_fields": "any",
            "config_prefix": "foo",
        }

        # Disable DeepSeek thinking mode to avoid reasoning_content handling issues
        # DeepSeek models enable thinking mode by default, which returns reasoning_content
        # that must be passed back to the API in subsequent requests. To simplify
        # message handling and avoid 400 errors, we disable it here.
        if config_vars["model_provider"] == "deepseek":
            init_params["extra_body"] = {"thinking": {"type": "disabled"}}
            logger.debug("DeepSeek thinking mode disabled for title model")

        model = init_chat_model(**init_params)

        logger.debug("Title model created successfully")
        return model

    except Exception as e:
        logger.error("Failed to create title model: %s", e)
        raise RuntimeError(f"Failed to create title model: {e}") from e


def create_model_with_tools(
    model: Any,
    tools: list[Any],
) -> Any:
    """
    Bind tools to a model instance.

    Args:
        model: The base model instance.
        tools: List of tools to bind to the model.

    Returns:
        Any: A model instance with tools bound (type varies by provider).

    Raises:
        RuntimeError: If tool binding fails.
    """
    try:
        model_with_tools = model.bind_tools(tools)
        logger.debug("Model bound with %d tools successfully", len(tools))
        return model_with_tools
    except Exception as e:
        logger.error("Failed to bind tools to model: %s", e)
        raise RuntimeError(f"Failed to bind tools to model: {e}") from e


def create_base_model_with_tools(
    tools: list[Any],
    llm_config: Optional[dict[str, Any]] = None,
) -> Any:
    """
    Create a fresh base model instance with tools bound.

    This is a convenience function that combines creating the base model
    and binding tools to it.

    Args:
        tools: List of tools to bind to the model.
        llm_config: Configuration dictionary from database

    Returns:
        Any: A new model instance with tools bound (type varies by provider).

    Raises:
        ValueError: If required configuration fields are missing.
        RuntimeError: If model creation or tool binding fails.
    """
    base_model = create_base_model(llm_config)
    return create_model_with_tools(base_model, tools)
