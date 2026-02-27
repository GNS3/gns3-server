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

from sqlalchemy import Column, String, Boolean, Float, ForeignKey, Integer
from sqlalchemy.orm import relationship

from .base import BaseTable, generate_uuid, GUID


class CopilotConfig(BaseTable):
    """
    Copilot configuration for a user.
    Stores the AI model settings and API credentials.
    """

    __tablename__ = "copilot_configs"

    config_id = Column(GUID, primary_key=True, default=generate_uuid)
    user_id = Column(GUID, ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, index=True)

    # Model provider settings
    provider = Column(String, default="openai")  # openai, anthropic, google, aws, ollama, deepseek, xai
    model_name = Column(String, default="gpt-4o")
    api_key = Column(String)  # Encrypted API key
    base_url = Column(String, nullable=True)  # Optional custom base URL

    # Model parameters
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, nullable=True)  # Optional max tokens limit

    # Feature flags
    enabled = Column(Boolean, default=True)

    # Relationship to user
    user = relationship("User", back_populates="copilot_config")
