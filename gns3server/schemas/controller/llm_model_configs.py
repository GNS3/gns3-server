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

from typing import Optional, Literal, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator
from uuid import UUID

from .base import DateTimeModelMixin


# Valid model types
ModelType = Literal['text', 'vision', 'stt', 'tts', 'multimodal', 'embedding', 'reranking', 'other']


# Core model config schema (stored in config JSONB field)
class LLMModelConfigData(BaseModel):
    """
    LLM model configuration data.
    Stored in the config JSONB column (provider, base_url, model, etc.).

    IMPORTANT: context_limit is REQUIRED to ensure proper context window management.
    Model providers frequently update context limits, so users must configure this value.

    NOTE: context_limit unit is K tokens (1 K = 1000 tokens).
    Example: 128 means 128K tokens (128,000 tokens).
    """

    provider: str = Field(..., description="LLM provider (e.g., 'openai', 'anthropic', 'ollama')")
    base_url: str = Field(..., description="API base URL")
    model: str = Field(..., description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature parameter")
    api_key: Optional[str] = Field(None, description="API key (will be encrypted)")
    max_tokens: Optional[int] = Field(None, gt=0, description="Max tokens for generation")
    context_limit: int = Field(
        ..., gt=0, description="Model context window limit in K tokens (e.g., 128 = 128K tokens)"
    )
    context_strategy: Literal["conservative", "balanced", "aggressive"] = Field(
        "balanced", description="Context trimming strategy: conservative (60%), balanced (75%), aggressive (85%)"
    )
    copilot_mode: Optional[str] = Field(
        None,
        description="GNS3-Copilot mode: 'teaching_assistant' or 'lab_automation_assistant'"
    )

    # Allow extra fields for extensibility
    # Ensure all fields are included in serialization, even if None
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# Request schemas
class LLMModelConfigCreate(BaseModel):
    """Request to create a new LLM model configuration."""

    name: str = Field(..., min_length=1, max_length=100, description="Configuration name")
    model_type: ModelType = Field(..., description="Model type")
    is_default: Optional[bool] = Field(False, description="Set as default configuration")
    # Config fields
    provider: str = Field(..., description="LLM provider")
    base_url: str = Field(..., description="API base URL")
    model: str = Field(..., description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    api_key: Optional[str] = None
    max_tokens: Optional[int] = Field(None, gt=0)
    context_limit: int = Field(
        ..., gt=0, description="Model context window limit in K tokens (e.g., 128 = 128K tokens)"
    )
    context_strategy: Literal["conservative", "balanced", "aggressive"] = Field(
        "balanced", description="Context trimming strategy"
    )
    copilot_mode: Optional[str] = Field(
        None,
        description="GNS3-Copilot mode: 'teaching_assistant' or 'lab_automation_assistant'"
    )

    # Allow extra config fields
    model_config = ConfigDict(extra="allow")


class LLMModelConfigUpdate(BaseModel):
    """Request to update an existing LLM model configuration."""

    # Table-level fields
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    model_type: Optional[ModelType] = None
    is_default: Optional[bool] = None
    expected_version: Optional[int] = Field(None, description="Expected version for optimistic locking")

    # Config fields
    provider: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    api_key: Optional[str] = None
    max_tokens: Optional[Union[int, str]] = Field(None, description="Max tokens for generation (can be null)")
    context_limit: Optional[int] = Field(
        None, gt=0, description="Model context window limit in K tokens (e.g., 128 = 128K tokens)"
    )
    context_strategy: Optional[Literal["conservative", "balanced", "aggressive"]] = Field(
        None, description="Context trimming strategy"
    )
    copilot_mode: Optional[str] = Field(
        None,
        description="GNS3-Copilot mode: 'teaching_assistant' or 'lab_automation_assistant'"
    )

    # Allow extra config fields
    model_config = ConfigDict(extra="allow")

    @field_validator('max_tokens', mode='before')
    @classmethod
    def validate_max_tokens(cls, v):
        """Handle string 'null' values for max_tokens."""
        if v == "null" or v == "":
            return None
        if v is None:
            return None
        # Convert to int if it's a valid integer string
        if isinstance(v, str) and v.isdigit():
            return int(v)
        return v


# Response schema without API key (for security)
class LLMModelConfigDataWithoutSecret(BaseModel):
    """LLM model configuration data WITHOUT sensitive information."""

    provider: str = Field(..., description="LLM provider (e.g., 'openai', 'anthropic', 'ollama')")
    base_url: str = Field(..., description="API base URL")
    model: str = Field(..., description="Model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature parameter")
    api_key: Optional[str] = Field(None, description="API key (always hidden in API responses)")
    max_tokens: Optional[int] = Field(None, gt=0, description="Max tokens for generation")
    context_limit: int = Field(
        ..., gt=0, description="Model context window limit in K tokens (e.g., 128 = 128K tokens)"
    )
    context_strategy: Literal["conservative", "balanced", "aggressive"] = Field(
        "balanced", description="Context trimming strategy: conservative (60%), balanced (75%), aggressive (85%)"
    )
    copilot_mode: Optional[str] = Field(
        None,
        description="GNS3-Copilot mode: 'teaching_assistant' or 'lab_automation_assistant'"
    )

    # Allow extra fields for extensibility
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# Response schemas
class LLMModelConfigResponse(DateTimeModelMixin):
    """LLM model configuration response (without API key for security)."""

    config_id: UUID
    name: str
    model_type: ModelType
    config: LLMModelConfigDataWithoutSecret
    user_id: Optional[UUID] = None
    group_id: Optional[UUID] = None
    is_default: bool
    version: int = Field(..., description="Optimistic locking version")

    model_config = ConfigDict(from_attributes=True)


class LLMModelConfigWithSource(DateTimeModelMixin):
    """Model configuration with source information (for inheritance, without API key for security)."""

    config_id: UUID
    name: str
    model_type: ModelType
    config: LLMModelConfigDataWithoutSecret
    user_id: Optional[UUID] = None
    group_id: Optional[UUID] = None
    is_default: bool
    version: int
    source: str = Field(..., description="Source: 'user' or 'group'")
    group_name: Optional[str] = Field(None, description="Group name if source is 'group'")

    model_config = ConfigDict(from_attributes=True, extra="allow")


class LLMModelConfigInheritedResponse(BaseModel):
    """Response containing user's effective configs (own + inherited from groups)."""

    configs: list[LLMModelConfigWithSource]
    default_config: Optional[LLMModelConfigWithSource] = None
    total: int


class LLMModelConfigListResponse(BaseModel):
    """Response containing a list of model configurations with default."""

    configs: list[LLMModelConfigResponse]
    default_config: Optional[LLMModelConfigResponse] = None
    total: int
