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

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, SecretStr, ConfigDict
from uuid import UUID

from .base import DateTimeModelMixin


class CopilotConfigBase(BaseModel):
    """
    Common copilot configuration properties.
    """

    provider: str = Field(default="openai", description="AI model provider")
    model_name: str = Field(default="gpt-4o", description="Model name")
    base_url: Optional[str] = Field(None, description="Custom base URL for API")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Max tokens limit")
    enabled: bool = Field(default=True, description="Whether copilot is enabled")


class CopilotConfigCreate(CopilotConfigBase):
    """
    Properties to create a copilot configuration.
    """

    api_key: str = Field(..., min_length=1, description="API key for the provider")


class CopilotConfigUpdate(BaseModel):
    """
    Properties to update a copilot configuration.
    """

    provider: Optional[str] = Field(None, description="AI model provider")
    model_name: Optional[str] = Field(None, description="Model name")
    api_key: Optional[str] = Field(None, min_length=1, description="API key for the provider")
    base_url: Optional[str] = Field(None, description="Custom base URL for API")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Max tokens limit")
    enabled: Optional[bool] = Field(None, description="Whether copilot is enabled")


class CopilotConfig(DateTimeModelMixin, CopilotConfigBase):
    """
    Copilot configuration response.
    """

    config_id: UUID
    user_id: UUID
    model_config = ConfigDict(from_attributes=True)


class ChatMessage(BaseModel):
    """
    Chat message from user or agent.
    """

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """
    Request to send a chat message to the copilot.
    """

    message: str = Field(..., min_length=1, description="User message")
    conversation_id: Optional[str] = Field(None, description="Conversation/thread ID for context")
    stream: bool = Field(default=False, description="Whether to stream the response")


class ChatResponse(BaseModel):
    """
    Response from the copilot.
    """

    response: str = Field(..., description="Agent response")
    conversation_id: str = Field(..., description="Conversation/thread ID")
    tools_used: list[str] = Field(default_factory=list, description="List of tools used by the agent")


class OpenAIToolCall(BaseModel):
    """OpenAI-compatible tool call information"""
    id: str
    type: str = "function"
    function: Dict[str, Any] = Field(
        default_factory=lambda: {"name": "", "arguments": ""},
        description="Function call details with name and arguments"
    )


class ChatStreamEvent(BaseModel):
    """
    Server-Sent Event for streaming chat responses.

    Uses flat structure compatible with OpenAI format for better frontend integration.
    All event data is in flat fields, not nested JSON strings.
    """
    type: str = Field(
        ...,
        description="Event type: 'content', 'tool_call', 'tool_start', 'tool_end', 'done', 'error', 'heartbeat'"
    )
    content: Optional[str] = Field(None, description="Text content for 'content' events")
    message_id: Optional[str] = Field(None, description="Message ID")
    tool_call: Optional[OpenAIToolCall] = Field(None, description="Tool call info for 'tool_call' events")
    tool_name: Optional[str] = Field(None, description="Tool name for 'tool_start' events")
    tool_output: Optional[str] = Field(None, description="Tool output for 'tool_end' events")
    error: Optional[str] = Field(None, description="Error message for 'error' events")
    conversation_id: Optional[str] = Field(None, description="Conversation/thread ID")
    timestamp: Optional[int] = Field(None, description="Timestamp for 'heartbeat' events")
