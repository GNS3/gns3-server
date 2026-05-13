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
Tool call streaming accumulator for handling progressive tool call arguments
Maintains state for streaming tool call chunks
Based on FlowNet-Lab implementation
"""

from typing import Any, Dict, List, Optional


class ToolCallStreamAccumulator:
    """
    Accumulates tool call information from streaming events
    Handles the progressive build-up of tool call arguments

    This class processes LangGraph streaming events and accumulates
    tool call arguments that come in chunks, emitting progressive
    tool_call events to the frontend.
    """

    def __init__(self) -> None:
        # Current active tool call being accumulated
        # Format: {"id": str, "name": str, "args_string": str}
        self._current_tool_call: Optional[Dict[str, str]] = None

    def process_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process a streaming event and return one or more response chunks

        Args:
            event: LangGraph streaming event (on_chat_model_stream)

        Returns:
            List of response chunks to send to frontend

        Processing phases:
        1. Initialize: Extract tool ID and name from tool_calls
        2. Accumulate: Concatenate argument strings from tool_call_chunks
        3. Complete: Mark as complete when finish_reason is "tool_calls" or "stop"
        """
        event_type = event.get("event", "")
        chunks = []

        if event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk", {})

            # ========== Phase 1: Initialize tool call from tool_calls ==========
            # Get metadata (ID and name) from tool_calls
            if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                for tool_call in chunk.tool_calls:
                    if isinstance(tool_call, dict):
                        tc_id = tool_call.get("id")
                        tc_name = tool_call.get("name", "")
                    else:
                        tc_id = getattr(tool_call, "id", None)
                        tc_name = getattr(tool_call, "name", "")

                    # Only when ID is not empty, consider it as the start of a new
                    # tool call
                    if tc_id:
                        # Initialize current tool state (this is the only time to
                        # get ID). Note: only one tool can be called at a time
                        self._current_tool_call = {
                            "id": tc_id,
                            "name": tc_name if tc_name else "UNKNOWN_TOOL",
                            "args_string": "",
                        }

                        # Send initial tool_call event with empty args
                        chunks.append(
                            {
                                "type": "tool_call",
                                "tool_call": {
                                    "id": tc_id,
                                    "type": "function",
                                    "function": {
                                        "name": self._current_tool_call[
                                            "name"
                                        ],
                                        "arguments": "",
                                    },
                                },
                            }
                        )

            # ========== Phase 2: Concatenate parameter strings from
            # tool_call_chunks ==========
            # Concatenate parameter strings from tool_call_chunk
            if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                if self._current_tool_call:
                    tool_data = self._current_tool_call
                    for tc_chunk in chunk.tool_call_chunks:
                        # Default to "" instead of None
                        if isinstance(tc_chunk, dict):
                            args_chunk = tc_chunk.get("args", "")
                        else:
                            args_chunk = getattr(tc_chunk, "args", "")

                        # Core: string concatenation
                        if isinstance(args_chunk, str):
                            tool_data[
                                "args_string"
                            ] += args_chunk

                            # Send updated tool_call event with accumulated args
                            chunks.append(
                                {
                                    "type": "tool_call",
                                    "tool_call": {
                                        "id": tool_data["id"],
                                        "type": "function",
                                        "function": {
                                            "name": tool_data["name"],
                                            "arguments": tool_data[
                                                "args_string"
                                            ],
                                        },
                                    },
                                }
                            )

            # ========== Phase 3: Determine if tool_calls_chunks output is
            # complete ==========
            # Check finish_reason == "tool_calls" or "STOP"
            response_metadata = getattr(chunk, "response_metadata", {})
            finish_reason = (
                response_metadata.get("finish_reason")
                if isinstance(response_metadata, dict)
                else None
            )

            if (finish_reason == "tool_calls") or (
                finish_reason == "stop" and self._current_tool_call is not None
            ):
                if self._current_tool_call:
                    tool_data = self._current_tool_call

                    # Send final complete tool_call event
                    chunks.append(
                        {
                            "type": "tool_call",
                            "tool_call": {
                                "id": tool_data["id"],
                                "type": "function",
                                "function": {
                                    "name": tool_data["name"],
                                    "arguments": tool_data["args_string"],
                                    "complete": True,  # Mark as complete
                                },
                            },
                        }
                    )

                    # Clear the current tool call state
                    self._current_tool_call = None

            # Also handle regular content (when not in tool call mode)
            content = getattr(chunk, "content", "")
            if content and not self._current_tool_call:
                chunks.append(
                    {
                        "type": "content",
                        "content": content,
                        "message_id": event.get("metadata", {}).get("msg_id"),
                    }
                )

        return chunks

    def reset(self) -> None:
        """Reset the accumulator state"""
        self._current_tool_call = None
