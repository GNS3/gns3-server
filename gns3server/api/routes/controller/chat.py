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
API routes for GNS3 Copilot Chat integration.

Nested under projects: /v3/projects/{project_id}/chat/...
"""

import json
import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from uuid import UUID

from gns3server import schemas
from gns3server.controller import Controller
from gns3server.controller.project import Project
from gns3server.controller.controller_error import ControllerNotFoundError
from gns3server.agent.gns3_copilot.project_agent_manager import get_project_agent_manager

from .dependencies.authentication import get_current_active_user

log = logging.getLogger(__name__)

responses = {404: {"model": schemas.ErrorMessage, "description": "Resource not found"}}

router = APIRouter(responses=responses)


def dep_project(project_id: UUID) -> Project:
    """
    Dependency to retrieve a project.

    Args:
        project_id: GNS3 project ID

    Returns:
        Project instance

    Raises:
        ControllerNotFoundError: If project not found
    """
    controller = Controller.instance()
    project = controller.get_project(str(project_id))
    if not project:
        raise ControllerNotFoundError(f"Project '{project_id}' not found")
    return project


@router.post(
    "/stream",
    response_model=None,
    summary="Stream chat responses from GNS3 Copilot",
    description="Send a message to GNS3 Copilot and stream the response via Server-Sent Events (SSE)."
)
async def stream_chat(
    request: schemas.ChatRequest,
    http_request: Request,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
) -> StreamingResponse:
    """
    Stream chat endpoint for GNS3 Copilot.

    This endpoint uses Server-Sent Events (SSE) to stream responses from
    the AI agent. Each message is a JSON object with a `type` field indicating
    the message kind (content, tool_call, tool_start, tool_end, error, done, heartbeat).

    The project must be opened to use chat functionality.
    """

    # Get user authentication info
    user_id = str(current_user.user_id)

    # Check if project is opened
    if project.status != "opened":
        log.warning(
            "Chat rejected: project not opened. user_id=%s, project_id=%s, status=%s",
            user_id,
            project.id,
            project.status
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project must be opened to use chat. Current status: {project.status}"
        )

    log.info(
        "Chat request started: user_id=%s, project_id=%s, project_name=%s, session_id=%s",
        user_id,
        project.id,
        project.name,
        request.session_id or "(new)",
    )

    # Get JWT token from Authorization header
    auth_header = http_request.headers.get("Authorization", "")
    jwt_token = auth_header.replace("Bearer ", "") if auth_header else None

    # Get FastAPI app reference (for database access)
    app = http_request.app

    # Get user's LLM config (with decrypted API key)
    from gns3server.db.tasks import get_user_llm_config_full
    llm_config = await get_user_llm_config_full(user_id, app)
    if not llm_config:
        log.warning("LLM config not found for user: %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LLM configuration not found. Please configure your LLM settings first."
        )

    log.debug(
        "LLM config loaded: user_id=%s, provider=%s, model=%s",
        user_id,
        llm_config.get("provider"),
        llm_config.get("model"),
    )

    # TODO: Support runtime temperature override from request.temperature
    # Currently, temperature is loaded from the user's LLM config in the database.
    # To enable runtime override, uncomment the following:
    # if request.temperature is not None:
    #     llm_config["temperature"] = str(request.temperature)

    # Get or create AgentService for this project
    agent_manager = await get_project_agent_manager()
    agent_service = await agent_manager.get_agent(str(project.id), project.path)
    log.debug("AgentService obtained for project: %s", project.id)

    # Generate session_id if not provided
    session_id = request.session_id or str(uuid.uuid4())
    if not request.session_id:
        log.debug("New session created: %s", session_id)

    async def generate():
        """Generator for SSE streaming."""
        try:
            log.debug("Starting stream: session_id=%s", session_id)
            async for chunk in agent_service.stream_chat(
                message=request.message,
                session_id=session_id,
                project_id=str(project.id),
                user_id=user_id,
                jwt_token=jwt_token,
                mode=request.mode,
                llm_config=llm_config
            ):
                try:
                    # Validate and serialize chunk
                    validated = schemas.ChatResponse(**chunk)
                    yield f"data: {json.dumps(validated.model_dump(exclude_none=True), ensure_ascii=False)}\n\n"
                except Exception as e:
                    log.warning("Error serializing chunk: %s", e)
                    # Skip invalid chunks but continue streaming
                    continue

            # Final done message
            log.debug("Stream completed: session_id=%s", session_id)
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

        except Exception as e:
            log.error("Error in stream_chat: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@router.get(
    "/sessions",
    response_model=List[schemas.ChatSession],
    summary="List chat sessions",
    description="List all chat sessions for a project."
)
async def list_sessions(
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
) -> list[schemas.ChatSession]:
    """
    List chat sessions for a project.
    """

    # Check if project is opened
    if project.status != "opened":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project must be opened to access chat sessions. Current status: {project.status}"
        )

    # Get AgentService for this project
    agent_manager = await get_project_agent_manager()
    agent_service = await agent_manager.get_agent(str(project.id), project.path)

    # List sessions
    sessions = await agent_service.list_sessions(user_id=str(current_user.user_id))

    # Convert to schemas
    return [schemas.ChatSession(**s) for s in sessions]


@router.get(
    "/sessions/{session_id}/history",
    response_model=schemas.ConversationHistory,
    summary="Get conversation history",
    description="Retrieve the conversation history for a specific session/thread."
)
async def get_history(
    session_id: str,
    project: Project = Depends(dep_project),
    limit: int = 100,
    current_user: schemas.User = Depends(get_current_active_user),
) -> schemas.ConversationHistory:
    """
    Get conversation history for a session.
    """

    # Check if project is opened
    if project.status != "opened":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project must be opened to access chat history. Current status: {project.status}"
        )

    # Get AgentService for this project
    agent_manager = await get_project_agent_manager()
    agent_service = await agent_manager.get_agent(str(project.id), project.path)

    # Get history
    history = await agent_service.get_history(session_id, limit)

    return schemas.ConversationHistory(**history)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
    description="Delete a specific chat session and its checkpoints."
)
async def delete_session(
    session_id: str,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
):
    """
    Delete a chat session.
    """

    # Check if project is opened
    if project.status != "opened":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project must be opened to delete chat sessions. Current status: {project.status}"
        )

    # Get AgentService for this project
    agent_manager = await get_project_agent_manager()
    agent_service = await agent_manager.get_agent(str(project.id), project.path)

    # Delete session
    deleted = await agent_service.delete_session(session_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found"
        )


@router.post(
    "/sessions/{session_id}/abort",
    status_code=status.HTTP_200_OK,
    summary="Abort a streaming session",
    description="Abort an ongoing streaming session for a specific session."
)
async def abort_session(
    session_id: str,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
):
    """
    Abort a streaming session.

    Sets the abort flag for the session, which will be checked on the next
    conditional edge evaluation. The streaming will stop at that point.
    """

    # Check if project is opened
    if project.status != "opened":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project must be opened to abort chat session. Current status: {project.status}"
        )

    # Get AgentService for this project
    agent_manager = await get_project_agent_manager()
    agent_service = await agent_manager.get_agent(str(project.id), project.path)

    # Abort the session
    agent_service.abort_session(session_id)

    return {"status": "ok", "session_id": session_id}


@router.patch(
    "/sessions/{session_id}",
    response_model=schemas.ChatSession,
    summary="Rename a chat session",
    description="Rename a specific chat session."
)
async def rename_session(
    session_id: str,
    request: schemas.RenameSession,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
) -> schemas.ChatSession:
    """
    Rename a chat session.
    """

    # Check if project is opened
    if project.status != "opened":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project must be opened to rename chat sessions. Current status: {project.status}"
        )

    # Get AgentService for this project
    agent_manager = await get_project_agent_manager()
    agent_service = await agent_manager.get_agent(str(project.id), project.path)

    # Rename session
    session = await agent_service.rename_session(session_id, request.title)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found"
        )

    return schemas.ChatSession(**session)


@router.put(
    "/sessions/{session_id}/pin",
    response_model=schemas.ChatSession,
    summary="Pin a chat session",
    description="Pin a chat session to the top of the list."
)
async def pin_session(
    session_id: str,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
) -> schemas.ChatSession:
    """
    Pin a chat session.
    """

    # Check if project is opened
    if project.status != "opened":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project must be opened to pin chat sessions. Current status: {project.status}"
        )

    # Get AgentService for this project
    agent_manager = await get_project_agent_manager()
    agent_service = await agent_manager.get_agent(str(project.id), project.path)

    # Pin session
    session = await agent_service.pin_session(session_id, pinned=True)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found"
        )

    return schemas.ChatSession(**session)


@router.delete(
    "/sessions/{session_id}/pin",
    response_model=schemas.ChatSession,
    summary="Unpin a chat session",
    description="Unpin a chat session from the top of the list."
)
async def unpin_session(
    session_id: str,
    project: Project = Depends(dep_project),
    current_user: schemas.User = Depends(get_current_active_user),
) -> schemas.ChatSession:
    """
    Unpin a chat session.
    """

    # Check if project is opened
    if project.status != "opened":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Project must be opened to unpin chat sessions. Current status: {project.status}"
        )

    # Get AgentService for this project
    agent_manager = await get_project_agent_manager()
    agent_service = await agent_manager.get_agent(str(project.id), project.path)

    # Unpin session
    session = await agent_service.pin_session(session_id, pinned=False)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found"
        )

    return schemas.ChatSession(**session)
