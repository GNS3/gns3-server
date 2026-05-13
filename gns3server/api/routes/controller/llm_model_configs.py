#!/usr/bin/env python
#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
API routes for LLM model configurations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from gns3server import schemas
from gns3server.controller.controller_error import (
    ControllerBadRequestError,
    ControllerNotFoundError,
)

from gns3server.db.repositories.llm_model_configs import LLMModelConfigsRepository
from gns3server.db.repositories.users import UsersRepository

from .dependencies.database import get_repository
from .dependencies.rbac import has_privilege

import logging

log = logging.getLogger(__name__)

router = APIRouter()


def _filter_api_key_from_config(config: dict) -> dict:
    """
    Remove API key from config dict for security.
    API keys should NEVER be returned via API endpoints.

    :param config: Configuration dictionary
    :return: Configuration dictionary with api_key set to None
    """
    filtered = config.copy()
    if "api_key" in filtered:
        filtered["api_key"] = None
    return filtered


# ============================================================================
# User LLM Model Configuration Endpoints
# ============================================================================

@router.get(
    "/users/{user_id}/llm-model-configs",
    response_model=schemas.LLMModelConfigInheritedResponse
)
async def get_user_llm_model_configs(
        user_id: UUID,
        current_user: schemas.User = Depends(has_privilege("User.Audit")),
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigInheritedResponse:
    """
    Get user's effective LLM model configurations (own + inherited from groups).

    Required privilege: User.Audit
    """

    try:
        result = await llm_repo.get_user_effective_configs(
            user_id,
            current_user_id=current_user.user_id,
            current_user_is_superadmin=current_user.is_superadmin
        )
        return schemas.LLMModelConfigInheritedResponse(
            configs=result["configs"],
            default_config=result.get("default_config"),
            total=len(result["configs"])
        )
    except Exception as e:
        log.error(f"Failed to retrieve user LLM model configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve LLM model configurations"
        )


@router.get(
    "/users/{user_id}/llm-model-configs/own",
    response_model=List[schemas.LLMModelConfigResponse],
    dependencies=[Depends(has_privilege("User.Audit"))]
)
async def get_user_own_llm_model_configs(
        user_id: UUID,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> List[schemas.LLMModelConfigResponse]:
    """
    Get user's own LLM model configurations (excluding inherited ones).

    Required privilege: User.Audit
    """

    try:
        configs = await llm_repo.get_user_configs(user_id)
        return [
            schemas.LLMModelConfigResponse(
                config_id=config.config_id,
                name=config.name,
                model_type=config.model_type,
                config=_filter_api_key_from_config(config.config),
                user_id=config.user_id,
                group_id=config.group_id,
                is_default=config.is_default,
                version=config.version,
                created_at=config.created_at,
                updated_at=config.updated_at
            )
            for config in configs
        ]
    except Exception as e:
        log.error(f"Failed to retrieve user's own LLM model configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve LLM model configurations"
        )


@router.get(
    "/users/{user_id}/llm-model-configs/default",
    response_model=schemas.LLMModelConfigResponse,
    dependencies=[Depends(has_privilege("User.Audit"))]
)
async def get_user_default_llm_model_config(
        user_id: UUID,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigResponse:
    """
    Get user's default LLM model configuration.

    Required privilege: User.Audit
    """

    try:
        config = await llm_repo.get_user_default_config(user_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No default LLM model configuration found for user '{user_id}'"
            )

        return schemas.LLMModelConfigResponse(
            config_id=config.config_id,
            name=config.name,
            model_type=config.model_type,
            config=_filter_api_key_from_config(config.config),
            user_id=config.user_id,
            group_id=config.group_id,
            is_default=config.is_default,
            version=config.version,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to retrieve user's default LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve LLM model configuration"
        )


@router.post(
    "/users/{user_id}/llm-model-configs",
    response_model=schemas.LLMModelConfigResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("User.Modify"))]
)
async def create_user_llm_model_config(
        user_id: UUID,
        config_create: schemas.LLMModelConfigCreate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigResponse:
    """
    Create a new LLM model configuration for a user.

    Required privilege: User.Modify

    IMPORTANT: context_limit is REQUIRED. Unit is K tokens (e.g., 128 = 128K = 128,000 tokens).
    Please check your model provider's documentation for the current context window size.
    """

    # Verify user exists
    user = await users_repo.get_user(user_id)
    if not user:
        raise ControllerNotFoundError(f"User '{user_id}' not found")

    # Validate context_limit is provided
    if not hasattr(config_create, 'context_limit') or config_create.context_limit is None:
        raise ControllerBadRequestError(
            "context_limit is required (unit: K tokens, e.g., 128 = 128K = 128,000 tokens). "
            "Please check your model provider's documentation for the current context window size "
            "and specify it in the configuration."
        )

    try:
        # Extract config fields (excluding table-level fields)
        config_fields = config_create.model_dump(exclude={"name", "model_type", "is_default"})
        new_config = await llm_repo.create_user_config(
            user_id,
            config_create.name,
            config_create.model_type,
            config_fields,
            is_default=config_create.is_default
        )

        return schemas.LLMModelConfigResponse(
            config_id=new_config.config_id,
            name=new_config.name,
            model_type=new_config.model_type,
            config=_filter_api_key_from_config(new_config.config),
            user_id=new_config.user_id,
            group_id=new_config.group_id,
            is_default=new_config.is_default,
            version=new_config.version,
            created_at=new_config.created_at,
            updated_at=new_config.updated_at
        )
    except ValueError as e:
        raise ControllerBadRequestError(str(e))
    except Exception as e:
        log.error(f"Failed to create LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create LLM model configuration: {e}"
        )


@router.put(
    "/users/{user_id}/llm-model-configs/{config_id}",
    response_model=schemas.LLMModelConfigResponse,
    dependencies=[Depends(has_privilege("User.Modify"))]
)
async def update_user_llm_model_config(
        user_id: UUID,
        config_id: UUID,
        config_update: schemas.LLMModelConfigUpdate,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigResponse:
    """
    Update a user's LLM model configuration.
    Supports optimistic locking via expected_version field.

    Required privilege: User.Modify
    """

    try:
        # Build updates dict with only non-None values
        updates = {k: v for k, v in config_update.model_dump().items() if v is not None}

        # Extract expected_version for optimistic locking
        expected_version = updates.pop("expected_version", None)

        updated_config = await llm_repo.update_user_config(
            config_id,
            user_id,
            updates,
            expected_version=expected_version
        )

        if not updated_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM model configuration '{config_id}' not found"
            )

        return schemas.LLMModelConfigResponse(
            config_id=updated_config.config_id,
            name=updated_config.name,
            model_type=updated_config.model_type,
            config=_filter_api_key_from_config(updated_config.config),
            user_id=updated_config.user_id,
            group_id=updated_config.group_id,
            is_default=updated_config.is_default,
            version=updated_config.version,
            created_at=updated_config.created_at,
            updated_at=updated_config.updated_at
        )
    except HTTPException:
        raise
    except ValueError as e:
        # Handle optimistic lock errors
        if "Concurrent modification" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise ControllerBadRequestError(str(e))
    except Exception as e:
        log.error(f"Failed to update LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update LLM model configuration"
        )


@router.delete(
    "/users/{user_id}/llm-model-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("User.Modify"))]
)
async def delete_user_llm_model_config(
        user_id: UUID,
        config_id: UUID,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> None:
    """
    Delete a user's LLM model configuration.

    Required privilege: User.Modify
    """

    try:
        success = await llm_repo.delete_user_config(config_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM model configuration '{config_id}' not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to delete LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete LLM model configuration"
        )


@router.put(
    "/users/{user_id}/llm-model-configs/default/{config_id}",
    response_model=schemas.LLMModelConfigResponse,
    dependencies=[Depends(has_privilege("User.Modify"))]
)
async def set_user_default_llm_model_config(
        user_id: UUID,
        config_id: UUID,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigResponse:
    """
    Set a user's default LLM model configuration.

    Required privilege: User.Modify
    """

    try:
        success = await llm_repo.set_user_default_config(user_id, config_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM model configuration '{config_id}' not found"
            )

        # Get the updated config
        config = await llm_repo.get_user_config(config_id)
        return schemas.LLMModelConfigResponse(
            config_id=config.config_id,
            name=config.name,
            model_type=config.model_type,
            config=_filter_api_key_from_config(config.config),
            user_id=config.user_id,
            group_id=config.group_id,
            is_default=config.is_default,
            version=config.version,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to set default LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set default LLM model configuration"
        )


# ============================================================================
# Group LLM Model Configuration Endpoints
# ============================================================================

@router.get(
    "/groups/{group_id}/llm-model-configs",
    response_model=schemas.LLMModelConfigListResponse,
    dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_group_llm_model_configs(
        group_id: UUID,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigListResponse:
    """
    Get all LLM model configurations for a user group.

    Required privilege: Group.Audit
    """

    try:
        configs = await llm_repo.get_group_configs(group_id)
        config_responses = [
            schemas.LLMModelConfigResponse(
                config_id=config.config_id,
                name=config.name,
                model_type=config.model_type,
                config=_filter_api_key_from_config(config.config),
                user_id=config.user_id,
                group_id=config.group_id,
                is_default=config.is_default,
                version=config.version,
                created_at=config.created_at,
                updated_at=config.updated_at
            )
            for config in configs
        ]

        # Find default config (same logic as user configs)
        default_config = None
        for config in config_responses:
            if config.is_default:
                default_config = config
                break

        # Fallback to first config if no default is marked
        if default_config is None and config_responses:
            default_config = config_responses[0]

        return schemas.LLMModelConfigListResponse(
            configs=config_responses,
            default_config=default_config,
            total=len(config_responses)
        )
    except Exception as e:
        log.error(f"Failed to retrieve group LLM model configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve LLM model configurations"
        )


@router.get(
    "/groups/{group_id}/llm-model-configs/default",
    response_model=schemas.LLMModelConfigResponse,
    dependencies=[Depends(has_privilege("Group.Audit"))]
)
async def get_group_default_llm_model_config(
        group_id: UUID,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigResponse:
    """
    Get group's default LLM model configuration.

    Required privilege: Group.Audit
    """

    try:
        config = await llm_repo.get_group_default_config(group_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No default LLM model configuration found for group '{group_id}'"
            )

        return schemas.LLMModelConfigResponse(
            config_id=config.config_id,
            name=config.name,
            model_type=config.model_type,
            config=_filter_api_key_from_config(config.config),
            user_id=config.user_id,
            group_id=config.group_id,
            is_default=config.is_default,
            version=config.version,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to retrieve group's default LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve LLM model configuration"
        )


@router.post(
    "/groups/{group_id}/llm-model-configs",
    response_model=schemas.LLMModelConfigResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def create_group_llm_model_config(
        group_id: UUID,
        config_create: schemas.LLMModelConfigCreate,
        users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigResponse:
    """
    Create a new LLM model configuration for a user group.

    Required privilege: Group.Modify

    IMPORTANT: context_limit is REQUIRED. Unit is K tokens (e.g., 128 = 128K = 128,000 tokens).
    Please check your model provider's documentation for the current context window size.
    """

    # Verify group exists
    group = await users_repo.get_user_group(group_id)
    if not group:
        raise ControllerNotFoundError(f"User group '{group_id}' not found")

    # Validate context_limit is provided
    if not hasattr(config_create, 'context_limit') or config_create.context_limit is None:
        raise ControllerBadRequestError(
            "context_limit is required (unit: K tokens, e.g., 128 = 128K = 128,000 tokens). "
            "Please check your model provider's documentation for the current context window size "
            "and specify it in the configuration."
        )

    try:
        # Extract config fields (excluding table-level fields)
        config_fields = config_create.model_dump(exclude={"name", "model_type", "is_default"})
        new_config = await llm_repo.create_group_config(
            group_id,
            config_create.name,
            config_create.model_type,
            config_fields,
            is_default=config_create.is_default
        )

        return schemas.LLMModelConfigResponse(
            config_id=new_config.config_id,
            name=new_config.name,
            model_type=new_config.model_type,
            config=_filter_api_key_from_config(new_config.config),
            user_id=new_config.user_id,
            group_id=new_config.group_id,
            is_default=new_config.is_default,
            version=new_config.version,
            created_at=new_config.created_at,
            updated_at=new_config.updated_at
        )
    except ValueError as e:
        raise ControllerBadRequestError(str(e))
    except Exception as e:
        log.error(f"Failed to create LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create LLM model configuration: {e}"
        )


@router.put(
    "/groups/{group_id}/llm-model-configs/{config_id}",
    response_model=schemas.LLMModelConfigResponse,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def update_group_llm_model_config(
        group_id: UUID,
        config_id: UUID,
        config_update: schemas.LLMModelConfigUpdate,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigResponse:
    """
    Update a group's LLM model configuration.
    Supports optimistic locking via expected_version field.

    Required privilege: Group.Modify
    """

    try:
        # Build updates dict with only non-None values
        updates = {k: v for k, v in config_update.model_dump().items() if v is not None}

        # Extract expected_version for optimistic locking
        expected_version = updates.pop("expected_version", None)

        updated_config = await llm_repo.update_group_config(
            config_id,
            group_id,
            updates,
            expected_version=expected_version
        )

        if not updated_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM model configuration '{config_id}' not found"
            )

        return schemas.LLMModelConfigResponse(
            config_id=updated_config.config_id,
            name=updated_config.name,
            model_type=updated_config.model_type,
            config=_filter_api_key_from_config(updated_config.config),
            user_id=updated_config.user_id,
            group_id=updated_config.group_id,
            is_default=updated_config.is_default,
            version=updated_config.version,
            created_at=updated_config.created_at,
            updated_at=updated_config.updated_at
        )
    except HTTPException:
        raise
    except ValueError as e:
        # Handle optimistic lock errors
        if "Concurrent modification" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )
        raise ControllerBadRequestError(str(e))
    except Exception as e:
        log.error(f"Failed to update LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update LLM model configuration"
        )


@router.delete(
    "/groups/{group_id}/llm-model-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def delete_group_llm_model_config(
        group_id: UUID,
        config_id: UUID,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> None:
    """
    Delete a group's LLM model configuration.

    Required privilege: Group.Modify
    """

    try:
        success = await llm_repo.delete_group_config(config_id, group_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM model configuration '{config_id}' not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to delete LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete LLM model configuration"
        )


@router.put(
    "/groups/{group_id}/llm-model-configs/default/{config_id}",
    response_model=schemas.LLMModelConfigResponse,
    dependencies=[Depends(has_privilege("Group.Modify"))]
)
async def set_group_default_llm_model_config(
        group_id: UUID,
        config_id: UUID,
        llm_repo: LLMModelConfigsRepository = Depends(get_repository(LLMModelConfigsRepository))
) -> schemas.LLMModelConfigResponse:
    """
    Set a group's default LLM model configuration.

    Required privilege: Group.Modify
    """

    try:
        success = await llm_repo.set_group_default_config(group_id, config_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM model configuration '{config_id}' not found"
            )

        # Get the updated config
        config = await llm_repo.get_group_config(config_id)
        return schemas.LLMModelConfigResponse(
            config_id=config.config_id,
            name=config.name,
            model_type=config.model_type,
            config=_filter_api_key_from_config(config.config),
            user_id=config.user_id,
            group_id=config.group_id,
            is_default=config.is_default,
            version=config.version,
            created_at=config.created_at,
            updated_at=config.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to set default LLM model config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set default LLM model configuration"
        )
