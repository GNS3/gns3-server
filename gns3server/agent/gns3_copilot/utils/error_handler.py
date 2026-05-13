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
# You should have have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Error Handler for GNS3-Copilot Agent

This module provides utilities for formatting and handling errors from
the LLM API client layer (LangChain), particularly HTTP errors that
may return HTML or other unhelpful content.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Patterns to detect HTML in error messages
HTML_PATTERNS = [
    r"<!DOCTYPE html",
    r"<html",
    r"<head>",
    r"<body",
    r"<div",
]


def format_error_message(error: Exception) -> str:
    """
    Format an error message for user display, cleaning up HTML and
    extracting meaningful error information.

    Args:
        error: The exception to format

    Returns:
        A formatted, user-friendly error message
    """
    error_str = str(error)

    # Check if error message contains HTML
    if _contains_html(error_str):
        logger.warning(
            "Detected HTML in error message, likely due to incorrect API "
            "configuration or base URL"
        )
        return (
            "API request failed. The error response indicates an issue with "
            "your API configuration. Please check:\n"
            "1. Base URL is correct (e.g., https://api.openai.com/v1 for OpenAI)\n"
            "2. API key is valid\n"
            "3. Provider is correctly configured"
        )

    # For other errors, return the original message
    return error_str


def _contains_html(text: str) -> bool:
    """Check if text contains HTML tags."""
    text_lower = text.lower()
    for pattern in HTML_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False
