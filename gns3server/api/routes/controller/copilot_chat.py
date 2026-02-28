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

import asyncio
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
    heartbeat_interval: float = 15.0,
    heartbeat_enabled: bool = True,
) -> AsyncGenerator[str, None]:
    """
    Stream chat response from the copilot agent with SSE format and heartbeat.

    This implementation uses asyncio.wait() for efficient timeout-based heartbeat,
    avoiding the overhead of queues and background tasks. This is optimized for
    multi-user concurrent scenarios.

    Args:
        message: User message
        project_id: GNS3 project ID
        conversation_id: Conversation/thread ID
        copilot_config: Copilot configuration
        controller: GNS3 controller instance
        heartbeat_interval: Heartbeat interval in seconds (default: 15.0)
        heartbeat_enabled: Whether to enable heartbeat (default: True)
    """
    log.info("Starting chat stream for project %s, conversation %s", project_id, conversation_id)

    try:
        from gns3server.services.copilot_service import CopilotService

        log.debug("Creating CopilotService instance")
        copilot_service = CopilotService(copilot_config, controller)

        # Create async iterator from the event stream
        event_stream = copilot_service.chat_stream(
            message=message,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        stream_aiter = aiter(event_stream)

        # Track event count for SSE IDs
        event_count = 0
        # Single task that we keep waiting on (no cancellation)
        next_event_task = None

        while True:
            # Create task if not already created
            if next_event_task is None:
                next_event_task = asyncio.create_task(anext(stream_aiter))

            try:
                if heartbeat_enabled and heartbeat_interval > 0:
                    # Wait with timeout - task continues running if timeout
                    done, pending = await asyncio.wait(
                        [next_event_task],
                        timeout=heartbeat_interval
                    )

                    if done:
                        # Event received - process it
                        event = next_event_task.result()
                        next_event_task = None  # Reset for next iteration

                        # Stream the event
                        event_count += 1
                        log.debug("Streaming event #%s: %s", event_count, event.event)

                        # Format SSE event
                        event_data = {
                            "conversation_id": event.conversation_id,
                            "data": event.data,
                        }
                        json_str = json.dumps(event_data, ensure_ascii=False)
                        json_str = json_str.replace('\n', '\\n').replace('\r', '\\r')

                        yield "event: %s\n" % event.event
                        yield "id: %s\n" % event_count
                        yield "data: %s\n\n" % json_str

                        # Check if stream is done
                        if event.event == "done":
                            log.info("Stream completed naturally, sent %s events", event_count)
                            break
                    else:
                        # Timeout - send heartbeat, keep task running
                        log.debug("Sending heartbeat after %ss idle", heartbeat_interval)
                        heartbeat_data = {
                            "conversation_id": conversation_id,
                            "timestamp": event_count,
                        }
                        json_str = json.dumps(heartbeat_data, ensure_ascii=False)
                        yield "event: heartbeat\n"
                        yield "data: %s\n\n" % json_str
                        # Don't reset next_event_task - continue waiting on same task

                else:
                    # Heartbeat disabled - just wait for event
                    event = await next_event_task
                    next_event_task = None

                    # Stream the event
                    event_count += 1
                    log.debug("Streaming event #%s: %s", event_count, event.event)

                    # Format SSE event
                    event_data = {
                        "conversation_id": event.conversation_id,
                        "data": event.data,
                    }
                    json_str = json.dumps(event_data, ensure_ascii=False)
                    json_str = json_str.replace('\n', '\\n').replace('\r', '\\r')

                    yield "event: %s\n" % event.event
                    yield "id: %s\n" % event_count
                    yield "data: %s\n\n" % json_str

                    # Check if stream is done
                    if event.event == "done":
                        log.info("Stream completed naturally, sent %s events", event_count)
                        break

            except StopAsyncIteration:
                # Stream ended normally
                log.info("Stream ended by StopAsyncIteration, sent %s events", event_count)
                # Send final done event if not already sent
                if event_count > 0:
                    done_data = {
                        "conversation_id": conversation_id,
                        "status": "completed",
                    }
                    yield "event: done\n"
                    yield "data: %s\n\n" % json.dumps(done_data)
                break

    except asyncio.CancelledError:
        log.info("Stream cancelled by client")
        # Send error event for cancellation
        try:
            error_data = {
                "conversation_id": conversation_id,
                "error": "Stream cancelled by client",
            }
            json_str = json.dumps(error_data, ensure_ascii=False)
            yield "event: error\n"
            yield "data: %s\n\n" % json_str
        except Exception:
            pass

    except Exception as e:
        log.error("Error in stream: %s", str(e), exc_info=True)
        # Send error event
        try:
            error_data = {
                "conversation_id": conversation_id,
                "error": str(e),
            }
            json_str = json.dumps(error_data, ensure_ascii=False)
            yield "event: error\n"
            yield "data: %s\n\n" % json_str
        except Exception:
            pass


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
    heartbeat_interval: float = 15.0,
    heartbeat_enabled: bool = True,
):
    """
    Chat with the copilot agent for a project (streaming).

    Uses Server-Sent Events (SSE) to stream the agent response in real-time.

    The agent has access to the project topology and can perform actions
    such as creating nodes, links, and executing commands on devices.

    Args:
        chat_request: Chat request with message and optional conversation_id
        project: GNS3 project
        current_user: Authenticated user
        copilot_repo: Copilot configuration repository
        heartbeat_interval: SSE heartbeat interval in seconds (default: 15.0)
        heartbeat_enabled: Whether to enable SSE heartbeat (default: True)
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
    log.debug("SSE heartbeat: enabled=%s, interval=%ss", heartbeat_enabled, heartbeat_interval)

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
            heartbeat_interval=heartbeat_interval,
            heartbeat_enabled=heartbeat_enabled,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
