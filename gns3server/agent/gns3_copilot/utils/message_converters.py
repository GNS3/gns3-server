# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
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
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""

Message format converters for OpenAI-compatible message format.
Converts between LangChain messages and OpenAI-compatible format.
"""

import json
import uuid
from typing import Any
from typing import Dict

from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import ToolMessage


def _ensure_string(content: Any) -> str:
    """Ensure content is a string, converting dicts/lists to JSON if needed."""
    if isinstance(content, str):
        return content
    elif isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False, indent=2)
    else:
        return str(content)


def convert_langchain_to_openai(lc_message) -> Dict[str, Any]:
    """
    Convert LangChain message to OpenAI-compatible format.

    Args:
        lc_message: LangChain message (HumanMessage, AIMessage, SystemMessage,
                    ToolMessage)

    Returns:
        Dictionary in OpenAI-compatible format
    """
    # Generate message ID
    msg_id = getattr(lc_message, "id", None)
    if msg_id is None:
        msg_id = str(uuid.uuid4())

    # Get metadata from message (including created_at)
    metadata = getattr(lc_message, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    # Base message structure (no top-level created_at, only metadata)
    base_msg = {"id": msg_id, "metadata": metadata}

    # Convert based on message type
    if isinstance(lc_message, HumanMessage):
        return {**base_msg, "role": "user", "content": lc_message.content}

    elif isinstance(lc_message, AIMessage):
        msg = {**base_msg, "role": "assistant", "content": lc_message.content}

        # Handle tool calls - convert to OpenAI format
        if hasattr(lc_message, "tool_calls") and lc_message.tool_calls:
            tool_calls = []
            for tc in lc_message.tool_calls:
                # Convert to dict if it's an object
                tc_dict = tc if isinstance(tc, dict) else tc.model_dump()
                tool_calls.append(
                    {
                        "id": tc_dict.get("id", str(uuid.uuid4())),
                        "type": "function",
                        "function": {
                            "name": tc_dict.get("name", ""),
                            "arguments": tc_dict.get("args", {}),
                        },
                    }
                )
            msg["tool_calls"] = tool_calls

        return msg

    elif isinstance(lc_message, ToolMessage):
        return {
            **base_msg,
            "role": "tool",
            "content": _ensure_string(lc_message.content),
            "name": getattr(lc_message, "name", ""),
            "tool_call_id": getattr(lc_message, "tool_call_id", ""),
        }

    elif isinstance(lc_message, SystemMessage):
        return {**base_msg, "role": "system", "content": lc_message.content}

    else:
        # Fallback for unknown message types
        return {**base_msg, "role": "unknown", "content": str(lc_message)}


def convert_openai_to_langchain(msg: Dict[str, Any]):
    """
    Convert OpenAI-compatible format to LangChain message.

    Args:
        msg: Dictionary in OpenAI-compatible format

    Returns:
        LangChain message
    """
    role = msg.get("role", "user")
    content = msg.get("content", "")

    if role == "user":
        return HumanMessage(content=content, id=msg.get("id"))

    elif role == "assistant":
        ai_msg = AIMessage(content=content, id=msg.get("id"))

        # Restore tool calls if present
        if "tool_calls" in msg and msg["tool_calls"]:
            tool_calls = []
            for tc in msg["tool_calls"]:
                tool_calls.append(
                    {
                        "id": tc.get("id", str(uuid.uuid4())),
                        "name": tc.get("function", {}).get("name", ""),
                        "args": tc.get("function", {}).get("arguments", {}),
                    }
                )
            ai_msg.tool_calls = tool_calls

        return ai_msg

    elif role == "tool":
        return ToolMessage(
            content=content,
            name=msg.get("name", ""),
            tool_call_id=msg.get("tool_call_id", ""),
        )

    elif role == "system":
        return SystemMessage(content=content)

    else:
        # Fallback to HumanMessage for unknown roles
        return HumanMessage(content=content)


def convert_stream_event_to_openai(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert LangGraph streaming event to OpenAI-compatible format.

    Args:
        event: LangGraph streaming event

    Returns:
        Dictionary in OpenAI-compatible streaming response format
    """
    event_type = event.get("event", "")

    if event_type == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk", {})
        content = getattr(chunk, "content", "")

        if content:
            return {
                "type": "content",
                "content": content,
                "message_id": event.get("metadata", {}).get("msg_id"),
            }

        # Check for tool call chunks
        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
            for tc_chunk in chunk.tool_call_chunks:
                tc_id = getattr(tc_chunk, "id", None)
                tc_name = getattr(tc_chunk, "name", None)
                tc_args = getattr(tc_chunk, "args", None)

                if tc_id:
                    return {
                        "type": "tool_call",
                        "tool_call": {
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc_name or "",
                                "arguments": tc_args or "",
                            },
                        },
                    }

    elif event_type == "on_tool_start":
        return {
            "type": "tool_start",
            "tool_name": event.get("name", ""),
            "metadata": event.get("metadata", {}),
        }

    elif event_type == "on_tool_end":
        tool_output = event.get("data", {}).get("output", "")
        # Convert dict or list output to JSON string for serialization
        if isinstance(tool_output, (dict, list)):
            tool_output = json.dumps(tool_output, ensure_ascii=False, indent=2)

        return {
            "type": "tool_end",
            "tool_output": tool_output,
            "tool_name": event.get("name", ""),
            "metadata": event.get("metadata", {}),
        }

    # Default empty response
    return {"type": "unknown"}
