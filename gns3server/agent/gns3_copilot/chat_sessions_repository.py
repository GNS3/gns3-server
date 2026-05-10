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

Chat Sessions Repository for managing chat session data.

Provides CRUD operations for the chat_sessions table in the project's
checkpoint database.
"""

import json
import logging
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import aiosqlite

log = logging.getLogger(__name__)


class ChatSession:
    """Chat session model."""

    def __init__(
        self,
        id: Optional[int] = None,
        thread_id: str = "",
        user_id: str = "",
        project_id: str = "",
        title: str = "New Conversation",
        message_count: int = 0,
        llm_calls_count: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        last_message_at: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        metadata: str = "{}",
        stats: str = "{}",
        pinned: bool = False,
    ):
        self.id = id
        self.thread_id = thread_id
        self.user_id = user_id
        self.project_id = project_id
        self.title = title
        self.message_count = message_count
        self.llm_calls_count = llm_calls_count
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens
        self.last_message_at = last_message_at
        self.created_at = created_at
        self.updated_at = updated_at
        self.metadata = metadata
        self.stats = stats
        self.pinned = pinned

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "title": self.title,
            "message_count": self.message_count,
            "llm_calls_count": self.llm_calls_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "last_message_at": self.last_message_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": json.loads(self.metadata) if self.metadata else {},
            "stats": json.loads(self.stats) if self.stats else {},
            "pinned": self.pinned,
        }


class ChatSessionsRepository:
    """
    Repository for managing chat sessions in the checkpoint database.
    """

    def __init__(self, conn: aiosqlite.Connection):
        """
        Initialize repository with a database connection.

        Args:
            conn: aiosqlite connection to the checkpoint database
        """
        self.conn = conn

    async def create_session(
        self,
        thread_id: str,
        user_id: str,
        project_id: str,
        title: str = "New Conversation",
        copilot_mode: Optional[str] = None,
    ) -> ChatSession:
        """
        Create a new chat session.

        Args:
            thread_id: Unique thread identifier
            user_id: User ID
            project_id: Project ID
            title: Session title
            copilot_mode: Copilot mode (optional)

        Returns:
            Created ChatSession
        """
        now = datetime.utcnow().isoformat()
        # Build metadata JSON
        metadata = {"copilot_mode": copilot_mode} if copilot_mode else {}
        metadata_json = json.dumps(metadata)

        cursor = await self.conn.execute(
            """
            INSERT INTO chat_sessions (
                thread_id, user_id, project_id, title,
                metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (thread_id, user_id, project_id, title, metadata_json, now, now),
        )
        await self.conn.commit()

        session_id = cursor.lastrowid
        log.info(
            "Created chat session: id=%s, thread_id=%s, copilot_mode=%s",
            session_id, thread_id, copilot_mode
        )

        return await self.get_session_by_id(session_id)

    async def get_session_by_id(
        self, session_id: int
    ) -> Optional[ChatSession]:
        """
        Get a session by its database ID.

        Args:
            session_id: Database row ID

        Returns:
            ChatSession or None
        """
        cursor = await self.conn.execute(
            "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()

        if row:
            return self._row_to_session(row)
        return None

    async def get_session_by_thread(
        self, thread_id: str
    ) -> Optional[ChatSession]:
        """
        Get a session by thread_id.

        Args:
            thread_id: Thread identifier

        Returns:
            ChatSession or None
        """
        cursor = await self.conn.execute(
            "SELECT * FROM chat_sessions WHERE thread_id = ?", (thread_id,)
        )
        row = await cursor.fetchone()

        if row:
            return self._row_to_session(row)
        return None

    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        copilot_mode: Optional[str] = None,
        limit: int = 100,
    ) -> List[ChatSession]:
        """
        List sessions with optional filters.

        Args:
            user_id: Filter by user ID
            project_id: Filter by project ID
            copilot_mode: Filter by copilot mode (metadata field)
            limit: Maximum number of sessions to return

        Returns:
            List of ChatSession
        """
        query = "SELECT * FROM chat_sessions"
        params = []

        conditions = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if project_id:
            conditions.append("project_id = ?")
            params.append(project_id)
        if copilot_mode:
            # Filter by JSON metadata field
            conditions.append("json_extract(metadata, '$.copilot_mode') = ?")
            params.append(copilot_mode)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        # Sort by pinned status first, then by updated_at
        query += " ORDER BY pinned DESC, updated_at DESC LIMIT ?"
        params.append(limit)

        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()

        return [self._row_to_session(row) for row in rows]

    async def update_session(
        self,
        thread_id: str,
        title: Optional[str] = None,
        message_count: Optional[int] = None,
        llm_calls_count: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        last_message_at: Optional[str] = None,
    ) -> Optional[ChatSession]:
        """
        Update a session.

        Args:
            thread_id: Thread identifier
            title: New title
            message_count: Increment message count
            llm_calls_count: Increment LLM call count
            input_tokens: Add to input tokens
            output_tokens: Add to output tokens
            total_tokens: Add to total tokens
            last_message_at: Last message timestamp

        Returns:
            Updated ChatSession or None
        """
        updates = []
        params = []

        now = datetime.utcnow().isoformat()

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if message_count is not None:
            updates.append("message_count = message_count + ?")
            params.append(message_count)

        if llm_calls_count is not None:
            updates.append("llm_calls_count = llm_calls_count + ?")
            params.append(llm_calls_count)

        if input_tokens is not None:
            updates.append("input_tokens = input_tokens + ?")
            params.append(input_tokens)

        if output_tokens is not None:
            updates.append("output_tokens = output_tokens + ?")
            params.append(output_tokens)

        if total_tokens is not None:
            updates.append("total_tokens = total_tokens + ?")
            params.append(total_tokens)

        if last_message_at is not None:
            updates.append("last_message_at = ?")
            params.append(last_message_at)

        if not updates:
            return await self.get_session_by_thread(thread_id)

        updates.append("updated_at = ?")
        params.append(now)
        params.append(thread_id)

        query = (
            f"UPDATE chat_sessions SET {', '.join(updates)} WHERE thread_id "
            f"= ?"
        )

        await self.conn.execute(query, params)
        await self.conn.commit()

        log.debug("Updated chat session: thread_id=%s", thread_id)
        return await self.get_session_by_thread(thread_id)

    async def delete_session(self, thread_id: str) -> bool:
        """
        Delete a session by thread_id.

        Args:
            thread_id: Thread identifier

        Returns:
            True if deleted, False if not found
        """
        # First, delete the checkpoint data
        await self.conn.execute(
            "DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,)
        )

        # Then delete the session
        cursor = await self.conn.execute(
            "DELETE FROM chat_sessions WHERE thread_id = ?", (thread_id,)
        )
        await self.conn.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            log.info(
                "Deleted chat session and checkpoints: thread_id=%s", thread_id
            )

        return deleted

    async def delete_all_sessions(self, project_id: str) -> int:
        """
        Delete all sessions for a project.

        Args:
            project_id: Project ID

        Returns:
            Number of sessions deleted
        """
        # Get all thread_ids for this project
        cursor = await self.conn.execute(
            "SELECT thread_id FROM chat_sessions WHERE project_id = ?",
            (project_id,),
        )
        rows = await cursor.fetchall()
        thread_ids = [row[0] for row in rows]

        # Delete checkpoints and sessions
        for thread_id in thread_ids:
            await self.conn.execute(
                "DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,)
            )

        cursor = await self.conn.execute(
            "DELETE FROM chat_sessions WHERE project_id = ?", (project_id,)
        )
        await self.conn.commit()

        deleted_count = cursor.rowcount
        if deleted_count > 0:
            log.info(
                "Deleted %d sessions for project: %s",
                deleted_count,
                project_id,
            )

        return deleted_count

    async def pin_session(
        self, thread_id: str, pinned: bool = True
    ) -> Optional[ChatSession]:
        """
        Pin or unpin a session.

        Args:
            thread_id: Thread identifier
            pinned: True to pin, False to unpin

        Returns:
            Updated ChatSession or None
        """
        now = datetime.utcnow().isoformat()
        await self.conn.execute(
            "UPDATE chat_sessions SET pinned = ?, updated_at = ? WHERE "
            "thread_id = ?",
            (1 if pinned else 0, now, thread_id),
        )
        await self.conn.commit()

        log.debug(
            "Session pin status updated: thread_id=%s, pinned=%s",
            thread_id,
            pinned,
        )
        return await self.get_session_by_thread(thread_id)

    def _row_to_session(self, row) -> ChatSession:
        """Convert database row to ChatSession object."""
        return ChatSession(
            id=row[0],
            thread_id=row[1],
            user_id=row[2],
            project_id=row[3],
            title=row[4],
            message_count=row[5],
            llm_calls_count=row[6],
            input_tokens=row[7],
            output_tokens=row[8],
            total_tokens=row[9],
            last_message_at=row[10],
            created_at=row[11],
            updated_at=row[12],
            metadata=row[13],
            stats=row[14],
            pinned=bool(row[15]) if len(row) > 15 else False,
        )
