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

GNS3 Copilot Agent Service

Provides project-level Agent instances with SQLite checkpoint management.
Each project has its own AgentService with a dedicated checkpoint database
in the project directory.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any
from typing import AsyncGenerator
from typing import Dict
from typing import List
from typing import Optional
from uuid import uuid4

import aiosqlite
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from gns3server.agent.gns3_copilot.agent.gns3_copilot import agent_builder
from gns3server.agent.gns3_copilot.chat_sessions_repository import (
    ChatSessionsRepository,
)
from gns3server.agent.gns3_copilot.gns3_client.context_helpers import (
    set_current_jwt_token,
)
from gns3server.agent.gns3_copilot.gns3_client.context_helpers import (
    set_current_llm_config,
)
from gns3server.agent.gns3_copilot.utils.error_handler import format_error_message
from gns3server.agent.gns3_copilot.utils.message_converters import (
    convert_langchain_to_openai,
)
from gns3server.agent.gns3_copilot.utils.tool_call_stream import (
    ToolCallStreamAccumulator,
)

log = logging.getLogger(__name__)


class AgentService:
    """
    Project-level Agent Service with async checkpoint management.

    Manages a LangGraph agent instance with SQLite-based state persistence
    for a single GNS3 project.
    """

    def __init__(self, project_path: str):
        """
        Initialize AgentService for a project.

        Args:
            project_path: Path to the GNS3 project directory
        """
        self.project_path = project_path
        self._checkpointer: Optional[AsyncSqliteSaver] = None
        self._checkpointer_conn: Optional[aiosqlite.Connection] = None
        self._checkpointer_path: Optional[str] = None
        self._graph = None
        self._init_lock = asyncio.Lock()
        self._initialized = False

    def _get_checkpoint_dir(self) -> str:
        """Get or create the checkpoint directory for this project."""
        checkpoint_dir = os.path.join(self.project_path, "gns3-copilot")
        os.makedirs(checkpoint_dir, exist_ok=True)
        return checkpoint_dir

    async def _get_checkpointer(self) -> AsyncSqliteSaver:
        """
        Get or create the SQLite checkpointer for this project.

        Returns:
            AsyncSqliteSaver instance
        """
        async with self._init_lock:
            if self._checkpointer is not None:
                return self._checkpointer

            checkpoint_dir = self._get_checkpoint_dir()
            checkpointer_path = os.path.join(
                checkpoint_dir, "copilot_checkpoints.db"
            )

            log.debug("Creating checkpointer at: %s", checkpointer_path)

            # Close existing connection if switching projects
            if self._checkpointer_conn:
                try:
                    await self._checkpointer_conn.close()
                    log.debug("Closed previous checkpointer connection")
                except Exception as e:
                    log.warning(
                        "Error closing old checkpointer connection: %s", e
                    )

            # Create new connection
            conn = await aiosqlite.connect(checkpointer_path)
            # Enable WAL mode for better concurrent performance
            await conn.execute("PRAGMA journal_mode=WAL;")
            self._checkpointer_conn = (
                conn  # Save connection reference to prevent GC
            )
            self._checkpointer = AsyncSqliteSaver(conn)

            # CRITICAL: Initialize database schema
            await self._checkpointer.setup()

            # Create chat_sessions table in the same database
            await self._create_chat_sessions_table(conn)

            self._checkpointer_path = checkpointer_path
            self._initialized = True

            log.info("Project checkpointer created at: %s", checkpointer_path)
            return self._checkpointer

    async def _create_chat_sessions_table(self, conn: aiosqlite.Connection):
        """
        Create the chat_sessions table in the checkpoint database.

        Args:
            conn: aiosqlite connection
        """
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                title TEXT DEFAULT 'New Conversation',

                -- Statistics
                message_count INTEGER DEFAULT 0,
                llm_calls_count INTEGER DEFAULT 0,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,

                -- Timestamps
                last_message_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- Reserved fields (JSON strings)
                metadata TEXT DEFAULT '{}',
                stats TEXT DEFAULT '{}',

                -- Pin feature
                pinned BOOLEAN DEFAULT FALSE
            )
        """)

        # Create indexes
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_thread_id ON "
            "chat_sessions(thread_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_project ON "
            "chat_sessions(user_id, project_id)"
        )

        # Check if pinned column exists, add it if not (migration for existing
        # databases)
        cursor = await conn.execute("PRAGMA table_info(chat_sessions)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "pinned" not in column_names:
            log.debug("Adding pinned column to existing chat_sessions table")
            await conn.execute(
                "ALTER TABLE chat_sessions ADD COLUMN pinned BOOLEAN DEFAULT "
                "FALSE"
            )
            await conn.commit()

        # Create pinned index (after column is guaranteed to exist)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pinned_updated ON "
            "chat_sessions(pinned DESC, updated_at DESC)"
        )

        await conn.commit()
        log.debug("chat_sessions table created in checkpoint database")

    async def _get_graph(self):
        """Get or compile the LangGraph agent."""
        if self._graph is None:
            checkpointer = await self._get_checkpointer()
            self._graph = agent_builder.compile(checkpointer=checkpointer)
            log.info(
                "LangGraph agent compiled for project: %s", self.project_path
            )
        return self._graph

    async def stream_chat(
        self,
        message: str,
        session_id: str,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        jwt_token: Optional[str] = None,
        mode: str = "text",
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat responses from the agent.

        Args:
            message: User message
            session_id: Session/thread ID for conversation continuity
            project_id: GNS3 project ID (optional, for context)
            user_id: User ID for metadata tracking
            jwt_token: JWT token for API authentication (optional)
            mode: Interaction mode (default: "text")
            llm_config: LLM configuration dict (provider, model, api_key,
                       etc.)

        Yields:
            Dict containing SSE-compatible response chunks
        """
        log.info(
            "Stream chat started: project_id=%s, user_id=%s, session_id=%s, "
            "mode=%s",
            project_id,
            user_id,
            session_id,
            mode,
        )

        # Ensure checkpointer is initialized
        if not self._checkpointer_conn:
            await self._get_checkpointer()

        # Get or create chat session
        repo = ChatSessionsRepository(self._checkpointer_conn)
        session = await repo.get_session_by_thread(session_id)
        is_new_session = session is None

        if is_new_session:
            # Create new session
            session = await repo.create_session(
                thread_id=session_id,
                user_id=user_id or "",
                project_id=project_id or "",
                title="New Conversation",
            )
            log.debug("Created new chat session: thread_id=%s", session_id)

        # Set request-scoped context variables (memory-only, not persisted)
        if jwt_token:
            set_current_jwt_token(jwt_token)
            log.debug("JWT token set in context")
        if llm_config:
            set_current_llm_config(llm_config)
            log.debug(
                "LLM config set in context: provider=%s, model=%s",
                llm_config.get("provider"),
                llm_config.get("model"),
            )

        # Build config - only thread-safe identifiers
        config = {
            "configurable": {
                "thread_id": session_id,
                "project_id": project_id,
            },
            "metadata": {
                "user_id": user_id,
            },
        }

        # Build inputs
        inputs = {
            "messages": [
                HumanMessage(
                    content=message,
                    id=str(uuid4()),
                    metadata={"created_at": datetime.utcnow().isoformat()},
                )
            ],
            "llm_calls": 0,
            "remaining_steps": 20,
            "mode": mode,
        }

        # Get the compiled graph
        graph = await self._get_graph()
        log.debug("LangGraph graph obtained, starting stream")

        # Track statistics for session update
        message_count = 1  # User message
        llm_calls_count = 0
        input_tokens = 0
        output_tokens = 0
        last_message_at = datetime.utcnow().isoformat()

        # Track if we've counted the AI response for this turn
        ai_response_counted = False
        tool_messages_counted = 0

        # Initialize tool call stream accumulator for handling progressive
        # tool call arguments
        tool_call_accumulator = ToolCallStreamAccumulator()

        # Stream events
        try:
            async for event in graph.astream_events(
                inputs, config=config, version="v2"
            ):
                event_type = event.get("event", "")
                data = event.get("data", {})

                # Track LLM calls and tokens
                if event_type == "on_chat_model_start":
                    # Filter out title_generator_node from statistics
                    langgraph_node = event.get("metadata", {}).get(
                        "langgraph_node", ""
                    )
                    if langgraph_node != "title_generator_node":
                        llm_calls_count += 1
                        log.debug(
                            "LLM call started, count=%d", llm_calls_count
                        )
                    else:
                        log.debug(
                            "Skipping LLM call count for internal node: "
                            "title_generator_node"
                        )

                elif event_type == "on_chat_model_end":
                    # Filter out title_generator_node from token counting
                    langgraph_node = event.get("metadata", {}).get(
                        "langgraph_node", ""
                    )
                    if langgraph_node == "title_generator_node":
                        log.debug(
                            "Skipping token counting for internal node: "
                            "title_generator_node"
                        )
                    else:
                        # Extract token usage from response metadata
                        # Try multiple possible locations where token usage
                        # might be stored
                        token_info_found = False

                        # Method 1: response.usage_metadata
                        response = data.get("response", {})
                        if hasattr(response, "usage_metadata"):
                            usage = response.usage_metadata
                            if usage:
                                input_tokens += usage.get("input_tokens", 0)
                                output_tokens += usage.get("output_tokens", 0)
                                token_info_found = True

                        # Method 2: output.usage_metadata
                        if not token_info_found:
                            output_msg = data.get("output", {})
                            if hasattr(output_msg, "usage_metadata"):
                                usage = output_msg.usage_metadata
                                if usage:
                                    input_tokens += usage.get(
                                        "input_tokens", 0
                                    )
                                    output_tokens += usage.get(
                                        "output_tokens", 0
                                    )
                                    token_info_found = True

                        # Method 3: Check data directly for token usage fields
                        if not token_info_found:
                            if "input_tokens" in data:
                                input_tokens += data.get("input_tokens", 0)
                            if "output_tokens" in data:
                                output_tokens += data.get("output_tokens", 0)
                            if (
                                "input_tokens" in data
                                or "output_tokens" in data
                            ):
                                token_info_found = True

                        # Count AI response as one message (only once per turn)
                        if not ai_response_counted:
                            message_count += 1
                            ai_response_counted = True

                # Track tool messages
                elif event_type == "on_tool_end":
                    message_count += 1  # Tool result message
                    tool_messages_counted += 1
                    log.debug(
                        "Tool message counted, message_count=%d", message_count
                    )

                # Convert event to chunk for SSE streaming
                # Use accumulator for on_chat_model_stream events to handle
                # progressive tool calls

                # Filter out internal nodes (title_generator_node) from
                # streaming to frontend
                langgraph_node = event.get("metadata", {}).get(
                    "langgraph_node", ""
                )
                if langgraph_node == "title_generator_node":
                    # Skip all events from the title_generator_node (internal
                    # use only)
                    log.debug(
                        "Skipping event from internal node: "
                        "title_generator_node"
                    )
                    continue

                if event_type == "on_chat_model_stream":
                    chunks = tool_call_accumulator.process_event(event)
                    for chunk in chunks:
                        # Add session_id to each chunk
                        chunk["session_id"] = session_id
                        log.debug(
                            "Yielding accumulated chunk: type=%s",
                            chunk.get("type"),
                        )
                        yield chunk
                else:
                    # Use stateless converter for other events
                    chunk = self._convert_event_to_chunk(event, session_id)
                    if chunk:
                        log.debug("Yielding chunk: type=%s", chunk.get("type"))
                        yield chunk

            # Update session statistics after successful stream
            await repo.update_session(
                thread_id=session_id,
                message_count=message_count,
                llm_calls_count=llm_calls_count,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                last_message_at=last_message_at,
            )
            log.info(
                "Session statistics updated: thread_id=%s, messages=%d, "
                "llm_calls=%d, tokens=%d+%d=%d",
                session_id,
                message_count,
                llm_calls_count,
                input_tokens,
                output_tokens,
                input_tokens + output_tokens,
            )

            # Sync auto-generated title from checkpoint state
            final_state = await graph.aget_state(config)
            if final_state and "conversation_title" in final_state.values:
                generated_title = final_state.values["conversation_title"]
                current_session = await repo.get_session_by_thread(session_id)
                if (
                    current_session
                    and current_session.title != generated_title
                ):
                    await repo.update_session(
                        thread_id=session_id, title=generated_title
                    )
                    log.info(
                        "Auto-generated title synced: thread_id=%s, title=%s",
                        session_id,
                        generated_title,
                    )

        except Exception as e:
            log.error("Error in stream_chat: %s", e, exc_info=True)
            yield {
                "type": "error",
                "error": format_error_message(e),
                "session_id": session_id,
            }

    def _convert_event_to_chunk(
        self, event: Dict[str, Any], session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Convert LangGraph event to API response chunk.

        Args:
            event: LangGraph event from astream_events
            session_id: Session ID for the response

        Returns:
            Dict for SSE response or None if event should be filtered

        Note:
            on_chat_model_stream events are handled by
            ToolCallStreamAccumulator before calling this method, so they are
            not processed here.
        """
        event_type = event.get("event", "")
        data = event.get("data", {})

        if event_type == "on_tool_start":
            # Tool execution started
            # Extract tool_call_id from event metadata to associate with
            # tool_call event
            tool_call_id = event.get("metadata", {}).get("tool_call_id", "")
            return {
                "type": "tool_start",
                "tool_name": event.get("name", ""),
                "tool_call_id": tool_call_id,
                "session_id": session_id,
            }

        elif event_type == "on_tool_end":
            # Tool execution completed
            # Extract tool output and convert to JSON string
            output = data.get("output", "")
            # Convert output to JSON string if it's not already a string
            # This ensures dict/list outputs are properly serialized for
            # frontend parsing
            if not isinstance(output, str):
                output = json.dumps(output, ensure_ascii=False, indent=2)
            return {
                "type": "tool_end",
                "tool_name": event.get("name", ""),
                "tool_output": output,
                "session_id": session_id,
            }

        return None

    async def get_history(
        self, session_id: str, limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session/thread ID
            limit: Maximum number of messages to retrieve

        Returns:
            Dict containing thread_id, title, and messages
        """
        config = {"configurable": {"thread_id": session_id}}

        try:
            graph = await self._get_graph()
            state = await graph.aget_state(config)

            if state and "messages" in state.values:
                messages = []
                for msg in state.values["messages"][-limit:]:
                    messages.append(self._convert_message_to_dict(msg))

                title = state.values.get(
                    "conversation_title", "New Conversation"
                )

                return {
                    "thread_id": session_id,
                    "title": title,
                    "messages": messages,
                }
        except Exception as e:
            log.error("Error getting history: %s", e, exc_info=True)

        return {
            "thread_id": session_id,
            "title": "New Conversation",
            "messages": [],
        }

    def _convert_message_to_dict(self, msg) -> Dict[str, Any]:
        """Convert a LangChain message to OpenAI-compatible dict format."""
        return convert_langchain_to_openai(msg)

    async def list_sessions(
        self, user_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List chat sessions for this project.

        Args:
            user_id: Filter by user ID (optional)
            limit: Maximum number of sessions to return

        Returns:
            List of session dictionaries
        """
        if not self._checkpointer_conn:
            await self._get_checkpointer()

        repo = ChatSessionsRepository(self._checkpointer_conn)
        sessions = await repo.list_sessions(user_id=user_id, limit=limit)
        return [s.to_dict() for s in sessions]

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a chat session and its checkpoints.

        Args:
            session_id: Thread ID to delete

        Returns:
            True if deleted, False if not found
        """
        if not self._checkpointer_conn:
            await self._get_checkpointer()

        repo = ChatSessionsRepository(self._checkpointer_conn)
        return await repo.delete_session(session_id)

    async def rename_session(
        self, session_id: str, new_title: str
    ) -> Optional[Dict[str, Any]]:
        """
        Rename a chat session.

        Args:
            session_id: Thread ID
            new_title: New title

        Returns:
            Updated session dictionary or None
        """
        if not self._checkpointer_conn:
            await self._get_checkpointer()

        repo = ChatSessionsRepository(self._checkpointer_conn)
        session = await repo.update_session(
            thread_id=session_id, title=new_title
        )
        return session.to_dict() if session else None

    async def pin_session(
        self, session_id: str, pinned: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Pin or unpin a chat session.

        Args:
            session_id: Thread ID
            pinned: True to pin, False to unpin

        Returns:
            Updated session dictionary or None
        """
        if not self._checkpointer_conn:
            await self._get_checkpointer()

        repo = ChatSessionsRepository(self._checkpointer_conn)
        session = await repo.pin_session(thread_id=session_id, pinned=pinned)
        return session.to_dict() if session else None

    async def close(self):
        """
        Close the checkpointer connection and cleanup resources.
        """
        async with self._init_lock:
            if self._checkpointer_conn:
                try:
                    # Add timeout to prevent blocking on database close
                    await asyncio.wait_for(
                        self._checkpointer_conn.close(),
                        timeout=5.0
                    )
                    log.debug(
                        "Checkpointer connection closed for: %s",
                        self.project_path,
                    )
                except asyncio.TimeoutError:
                    log.warning(
                        "Checkpointer connection close timeout for: %s (forcing cleanup)",
                        self.project_path,
                    )
                except Exception as e:
                    log.warning("Error closing checkpointer connection: %s", e)
                finally:
                    self._checkpointer_conn = None
                    self._checkpointer = None
                    self._graph = None
                    self._initialized = False
