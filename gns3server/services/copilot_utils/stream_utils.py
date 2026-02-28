# -*- coding: utf-8 -*-
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
Streaming utilities for LangGraph events to SSE conversion.

Converts LangGraph astream_events output to OpenAI-compatible streaming format.
Based on FlowNet-Lab implementation.
"""

import json
import logging
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)


class ToolCallStreamAccumulator:
    """
    Accumulates tool call information from streaming events.
    Handles the progressive build-up of tool call arguments.

    This implements stateful accumulation for tool calls that stream
    their arguments incrementally, matching OpenAI's streaming format.
    """

    def __init__(self):
        # Current active tool call being accumulated
        # Format: {"id": str, "name": str, "args_string": str}
        self._current_tool_call: Optional[Dict[str, str]] = None

    def process_event(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process a streaming event and return one or more response chunks.

        Args:
            event: LangGraph streaming event from astream_events()

        Returns:
            List of response chunks to send to frontend
        """
        event_type = event.get("event", "")
        chunks = []

        if event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk", {})

            # Phase 1: Initialize tool call from tool_calls
            # Get metadata (ID and name) from tool_calls
            if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                for tool_call in chunk.tool_calls:
                    if isinstance(tool_call, dict):
                        tc_id = tool_call.get('id')
                        tc_name = tool_call.get('name', '')
                    else:
                        tc_id = getattr(tool_call, 'id', None)
                        tc_name = getattr(tool_call, 'name', '')

                    # Only when ID is not empty, consider it as the start of a new tool call
                    if tc_id:
                        # Initialize current tool state (this is the only time to get ID)
                        self._current_tool_call = {
                            "id": tc_id,
                            "name": tc_name if tc_name else "UNKNOWN_TOOL",
                            "args_string": "",
                        }

                        log.debug("Tool call started: %s", self._current_tool_call["name"])

                        # Send initial tool_call event with empty args
                        chunks.append({
                            "type": "tool_call",
                            "tool_call": {
                                "id": tc_id,
                                "type": "function",
                                "function": {
                                    "name": self._current_tool_call["name"],
                                    "arguments": ""
                                }
                            }
                        })

            # Phase 2: Concatenate parameter strings from tool_call_chunks
            if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
                if self._current_tool_call:
                    tool_data = self._current_tool_call
                    for tc_chunk in chunk.tool_call_chunks:
                        # Default to "" instead of None
                        if isinstance(tc_chunk, dict):
                            args_chunk = tc_chunk.get("args", "")
                        else:
                            args_chunk = getattr(tc_chunk, 'args', "")

                        # String concatenation
                        if isinstance(args_chunk, str):
                            tool_data["args_string"] += args_chunk

                            # Send updated tool_call event with accumulated args
                            chunks.append({
                                "type": "tool_call",
                                "tool_call": {
                                    "id": tool_data["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tool_data["name"],
                                        "arguments": tool_data["args_string"]
                                    }
                                }
                            })

            # Phase 3: Determine if tool_calls_chunks output is complete
            response_metadata = getattr(chunk, 'response_metadata', {})
            finish_reason = response_metadata.get('finish_reason') if isinstance(response_metadata, dict) else None

            if (finish_reason == "tool_calls") or (
                finish_reason == "stop" and self._current_tool_call is not None
            ):
                if self._current_tool_call:
                    tool_data = self._current_tool_call

                    log.debug("Tool call completed: %s", tool_data["name"])

                    # Send final complete tool_call event
                    chunks.append({
                        "type": "tool_call",
                        "tool_call": {
                            "id": tool_data["id"],
                            "type": "function",
                            "function": {
                                "name": tool_data["name"],
                                "arguments": tool_data["args_string"],
                                "complete": True
                            }
                        }
                    })

                    # Clear the current tool call state
                    self._current_tool_call = None

            # Also handle regular content (when not in tool call mode)
            content = getattr(chunk, 'content', '')
            if content and not self._current_tool_call:
                chunks.append({
                    "type": "content",
                    "content": content,
                    "message_id": event.get("metadata", {}).get("msg_id")
                })

        return chunks

    def reset(self):
        """Reset the accumulator state"""
        self._current_tool_call = None


def convert_stream_event_to_sse(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert LangGraph streaming event to SSE format.

    Args:
        event: LangGraph streaming event from astream_events()

    Returns:
        Dictionary in SSE response format with keys:
        - type: 'content', 'tool_call', 'tool_start', 'tool_end', 'unknown'
        - content: Token content (for type='content')
        - tool_call: Tool call info (for type='tool_call')
        - tool_name: Tool name (for type='tool_start')
        - tool_output: Tool output (for type='tool_end')
    """
    event_type = event.get("event", "")

    if event_type == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk", {})
        content = getattr(chunk, 'content', '')

        if content:
            return {
                "type": "content",
                "content": content,
                "message_id": event.get("metadata", {}).get("msg_id")
            }

        # Check for tool call chunks
        if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
            for tc_chunk in chunk.tool_call_chunks:
                tc_id = getattr(tc_chunk, 'id', None)
                tc_name = getattr(tc_chunk, 'name', None)
                tc_args = getattr(tc_chunk, 'args', None)

                if tc_id:
                    return {
                        "type": "tool_call",
                        "tool_call": {
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc_name or "",
                                "arguments": tc_args or ""
                            }
                        }
                    }

    elif event_type == "on_tool_start":
        return {
            "type": "tool_start",
            "tool_name": event.get("name", ""),
            "metadata": event.get("metadata", {})
        }

    elif event_type == "on_tool_end":
        tool_output = event.get("data", {}).get("output", "")
        # Convert dict or list output to JSON string for serialization
        if isinstance(tool_output, (dict, list)):
            tool_output = json.dumps(tool_output, ensure_ascii=False, indent=2)

        # Try to get tool_call_id from the event data
        event_data = event.get("data", {})
        tool_call_id = None
        if hasattr(event_data, 'get'):
            tool_call_id = event_data.get("id")
        if not tool_call_id and isinstance(event_data, dict):
            tool_call_id = event_data.get("tool_call_id")

        return {
            "type": "tool_end",
            "tool_output": tool_output,
            "tool_name": event.get("name", ""),
            "tool_call_id": tool_call_id,
            "metadata": event.get("metadata", {})
        }

    # Default empty response for unknown event types
    return {"type": "unknown"}
