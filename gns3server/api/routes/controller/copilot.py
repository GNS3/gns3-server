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

from fastapi import APIRouter, Depends, HTTPException, Response, status
from uuid import UUID

from gns3server import schemas
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerBadRequestError,
    ControllerNotFoundError,
)

from gns3server.db.repositories.copilot import CopilotRepository

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository

import logging

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/config", response_model=schemas.CopilotConfig)
async def get_copilot_config(
        current_user: schemas.User = Depends(get_current_active_user),
        copilot_repo: CopilotRepository = Depends(get_repository(CopilotRepository))
) -> schemas.CopilotConfig:
    """
    Get the current user's copilot configuration.
    """
    log.debug(f"Fetching copilot config for user {current_user.username}")
    config = await copilot_repo.get_copilot_config(current_user.user_id)
    if not config:
        log.warning(f"Copilot config not found for user {current_user.username}")
        raise ControllerNotFoundError(f"Copilot configuration not found. Please create one first.")
    log.debug(f"Returning copilot config for user {current_user.username}: {config.provider}/{config.model_name}")
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
    log.info(f"Creating copilot config for user {current_user.username}: {config_create.provider}/{config_create.model_name}")

    existing_config = await copilot_repo.get_copilot_config(current_user.user_id)
    if existing_config:
        log.warning(f"Copilot config already exists for user {current_user.username}")
        raise ControllerBadRequestError(f"Copilot configuration already exists. Use PUT to update.")

    config = await copilot_repo.create_copilot_config(config_create, current_user.user_id)
    log.info(f"Created copilot config {config.config_id} for user {current_user.username}")
    return config


@router.put("/config", response_model=schemas.CopilotConfig)
async def update_copilot_config(
        config_update: schemas.CopilotConfigUpdate,
        current_user: schemas.User = Depends(get_current_active_user),
        copilot_repo: CopilotRepository = Depends(get_repository(CopilotRepository))
) -> schemas.CopilotConfig:
    """
    Update the current user's copilot configuration.
    """
    log.info(f"Updating copilot config for user {current_user.username}")
    config = await copilot_repo.update_copilot_config(current_user.user_id, config_update)
    if not config:
        log.warning(f"Copilot config not found for user {current_user.username}")
        raise ControllerNotFoundError(f"Copilot configuration not found. Please create one first.")
    log.info(f"Updated copilot config for user {current_user.username}: {config.provider}/{config.model_name}")
    return config


@router.delete("/config", status_code=status.HTTP_204_NO_CONTENT)
async def delete_copilot_config(
        current_user: schemas.User = Depends(get_current_active_user),
        copilot_repo: CopilotRepository = Depends(get_repository(CopilotRepository))
) -> None:
    """
    Delete the current user's copilot configuration.
    """
    log.info(f"Deleting copilot config for user {current_user.username}")
    success = await copilot_repo.delete_copilot_config(current_user.user_id)
    if not success:
        log.warning(f"Copilot config not found for user {current_user.username}")
        raise ControllerNotFoundError(f"Copilot configuration not found.")
    log.info(f"Deleted copilot config for user {current_user.username}")
