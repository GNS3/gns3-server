#!/usr/bin/env python
#
# Copyright (C) 2025 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
API routes for copilot configuration.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse

from gns3server import schemas
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerBadRequestError,
    ControllerNotFoundError,
)
from gns3server.db.repositories.copilot import CopilotRepository

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/config")
async def get_copilot_config(
        current_user: schemas.User = Depends(get_current_active_user),
        copilot_repo: CopilotRepository = Depends(get_repository(CopilotRepository))
):
    """
    Get the current user's copilot configuration.
    """
    log.debug("Fetching copilot config for user %s", current_user.username)
    config = await copilot_repo.get_copilot_config(current_user.user_id)
    if not config:
        log.warning("Copilot config not found for user %s", current_user.username)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "message": "Copilot configuration not found. Please create one first.",
                "details": {
                    "action": "Create a copilot configuration",
                    "endpoint": "POST /v3/copilot/config",
                    "required_fields": {
                        "provider": "AI provider (e.g., 'openai', 'anthropic', 'ollama', 'azure_openai')",
                        "model_name": "Model name (e.g., 'gpt-4', 'claude-3-5-sonnet-20241022')",
                        "api_key": "Your API key for the provider",
                        "base_url": "API base URL (optional, required for some providers)",
                        "temperature": "Sampling temperature (0.0-2.0, optional, default: 0.7)",
                        "max_tokens": "Maximum tokens to generate (optional, default: 2000)",
                        "enabled": "Whether the configuration is enabled (optional, default: true)"
                    },
                    "example": {
                        "provider": "openai",
                        "model_name": "gpt-4",
                        "api_key": "sk-...",
                        "base_url": "https://api.openai.com/v1",
                        "temperature": 0.7,
                        "max_tokens": 2000,
                        "enabled": True
                    }
                }
            }
        )
    log.debug("Returning copilot config for user %s: %s/%s",
              current_user.username, config.provider, config.model_name)
    return config


@router.post("/config", response_model=schemas.CopilotConfig, status_code=status.HTTP_201_CREATED)
async def create_copilot_config(
        config_create: schemas.CopilotConfigCreate,
        current_user: schemas.User = Depends(get_current_active_user),
        copilot_repo: CopilotRepository = Depends(get_repository(CopilotRepository))
) -> schemas.CopilotConfig:
    """
    Create a new copilot configuration for the current user.
    """
    log.info("Creating copilot config for user %s: %s/%s",
             current_user.username, config_create.provider, config_create.model_name)

    existing_config = await copilot_repo.get_copilot_config(current_user.user_id)
    if existing_config:
        log.warning("Copilot config already exists for user %s", current_user.username)
        raise ControllerBadRequestError(f"Copilot configuration already exists. Use PUT to update.")

    config = await copilot_repo.create_copilot_config(config_create, current_user.user_id)
    log.info("Created copilot config %s for user %s", config.config_id, current_user.username)
    return config


@router.put("/config")
async def update_copilot_config(
        config_update: schemas.CopilotConfigUpdate,
        current_user: schemas.User = Depends(get_current_active_user),
        copilot_repo: CopilotRepository = Depends(get_repository(CopilotRepository))
):
    """
    Update the current user's copilot configuration.
    """
    log.info("Updating copilot config for user %s", current_user.username)
    config = await copilot_repo.update_copilot_config(current_user.user_id, config_update)
    if not config:
        log.warning("Copilot config not found for user %s", current_user.username)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "message": "Copilot configuration not found. Please create one first.",
                "details": {
                    "action": "Create a copilot configuration",
                    "endpoint": "POST /v3/copilot/config",
                    "note": "Use POST to create a new configuration, then use PUT to update it."
                }
            }
        )
    log.info("Updated copilot config for user %s: %s/%s",
             current_user.username, config.provider, config.model_name)
    return config


@router.delete("/config", status_code=status.HTTP_204_NO_CONTENT)
async def delete_copilot_config(
        current_user: schemas.User = Depends(get_current_active_user),
        copilot_repo: CopilotRepository = Depends(get_repository(CopilotRepository))
) -> None:
    """
    Delete the current user's copilot configuration.
    """
    log.info("Deleting copilot config for user %s", current_user.username)
    success = await copilot_repo.delete_copilot_config(current_user.user_id)
    if not success:
        log.warning("Copilot config not found for user %s", current_user.username)
        raise ControllerNotFoundError(f"Copilot configuration not found.")
    log.info("Deleted copilot config for user %s", current_user.username)
