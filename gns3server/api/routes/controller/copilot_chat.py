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
API routes for project chat with copilot.
"""

import json
import logging
from typing import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from gns3server import schemas
from gns3server.controller import Controller
from gns3server.controller.controller_error import (
    ControllerError,
    ControllerBadRequestError,
    ControllerNotFoundError,
)
from gns3server.controller.project import Project
from gns3server.db.repositories.copilot import CopilotRepository

from .dependencies.authentication import get_current_active_user
from .dependencies.database import get_repository

log = logging.getLogger(__name__)

router = APIRouter()


async def dep_project(project_id: UUID) -> Project:
    """
    Dependency to retrieve a project.
    """
    log.debug("Loading project %s", project_id)
    controller = Controller.instance()
    project = await controller.get_loaded_project(str(project_id))
    log.debug("Project loaded: %s (%s)", project.name, project.id)
    return project


async def _stream_chat_response(
    message: str,
    project_id: str,
    conversation_id: str,
    copilot_config: schemas.CopilotConfig,
    controller: Controller,
) -> AsyncGenerator[str, None]:
    """
    Stream chat response from the copilot agent.
    """
    log.info("Starting chat stream for project %s, conversation %s", project_id, conversation_id)
    try:
        # Import the copilot agent service
        from gns3server.services.copilot_service import CopilotService

        log.debug("Creating CopilotService instance")
        copilot_service = CopilotService(copilot_config, controller)

        # Stream the response
        event_count = 0
        async for event in copilot_service.chat_stream(
            message=message,
            project_id=project_id,
            conversation_id=conversation_id,
        ):
            event_count += 1
            log.debug("Streaming event #%s: %s", event_count, event.event)
            # Format as SSE event
            yield "event: %s\n" % event.event
            yield "data: %s\n\n" % json.dumps({'data': event.data, 'conversation_id': event.conversation_id})

        log.info("Chat stream completed, sent %s events", event_count)

    except Exception as e:
        log.error("Error in copilot chat stream: %s", str(e), exc_info=True)
        error_event = schemas.ChatStreamEvent(
            event="error",
            data=str(e),
            conversation_id=conversation_id
        )
        yield f"event: {error_event.event}\n"
        yield f"data: {json.dumps({'data': error_event.data, 'conversation_id': error_event.conversation_id})}\n\n"


@router.post("/chat", response_model=schemas.ChatResponse)
async def chat_with_copilot(
    chat_request: schemas.ChatRequest,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    copilot_repo: CopilotRepository = Depends(get_repository(CopilotRepository)),
) -> schemas.ChatResponse:
    """
    Chat with the copilot agent for a project (non-streaming).

    The agent has access to the project topology and can perform actions
    such as creating nodes, links, and executing commands on devices.
    """
    log.info("Chat request from user %s for project %s", current_user.username, project.name)

    # Get user's copilot configuration
    log.debug("Fetching copilot config for user %s", current_user.user_id)
    config = await copilot_repo.get_copilot_config(current_user.user_id)
    if not config:
        log.warning("Copilot config not found for user %s", current_user.user_id)
        raise ControllerNotFoundError("Copilot configuration not found. Please configure it first.")

    if not config.enabled:
        log.warning("Copilot disabled for user %s", current_user.user_id)
        raise ControllerBadRequestError("Copilot is disabled for this user.")

    log.debug("Copilot config: %s/%s", config.provider, config.model_name)

    try:
        from gns3server.services.copilot_service import CopilotService

        controller = Controller.instance()
        log.debug("Creating CopilotService instance")
        copilot_service = CopilotService(config, controller)
        conversation_id = chat_request.conversation_id or "%s_%s" % (current_user.user_id, project.id)

        log.info("Processing chat with conversation_id: %s", conversation_id)
        response = await copilot_service.chat(
            message=chat_request.message,
            project_id=project.id,
            conversation_id=conversation_id,
        )

        log.info("Chat response successful, tools_used: %s", response.get('tools_used', []))
        return schemas.ChatResponse(
            response=response["response"],
            conversation_id=conversation_id,
            tools_used=response.get("tools_used", []),
        )

    except Exception as e:
        log.error("Error in copilot chat: %s", str(e), exc_info=True)
        raise ControllerError("Copilot chat error: %s" % str(e))


@router.post("/chat/stream")
async def chat_with_copilot_stream(
    chat_request: schemas.ChatRequest,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
    copilot_repo: CopilotRepository = Depends(get_repository(CopilotRepository)),
):
    """
    Chat with the copilot agent for a project (streaming).

    Uses Server-Sent Events (SSE) to stream the agent response in real-time.

    The agent has access to the project topology and can perform actions
    such as creating nodes, links, and executing commands on devices.
    """
    log.info("Chat stream request from user %s for project %s", current_user.username, project.name)

    # Get user's copilot configuration
    log.debug("Fetching copilot config for user %s", current_user.user_id)
    config = await copilot_repo.get_copilot_config(current_user.user_id)
    if not config:
        log.warning("Copilot config not found for user %s", current_user.user_id)
        raise ControllerNotFoundError("Copilot configuration not found. Please configure it first.")

    if not config.enabled:
        log.warning("Copilot disabled for user %s", current_user.user_id)
        raise ControllerBadRequestError("Copilot is disabled for this user.")

    log.debug("Copilot config: %s/%s", config.provider, config.model_name)

    conversation_id = chat_request.conversation_id or "%s_%s" % (current_user.user_id, project.id)
    controller = Controller.instance()

    log.info("Starting chat stream with conversation_id: %s", conversation_id)
    return StreamingResponse(
        _stream_chat_response(
            message=chat_request.message,
            project_id=project.id,
            conversation_id=conversation_id,
            copilot_config=config,
            controller=controller,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
