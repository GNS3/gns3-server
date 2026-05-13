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
Public module for parsing tool execution results

This module is specifically designed to parse and format results returned by tools_v2
after tool execution, supporting multiple formats and providing unified error handling.
Mainly used for result display in UI interfaces.

Supported formats:
- JSON strings
- Python literal strings
- Dictionary objects
- List objects (JSON arrays)
- Primitive types (int, float, bool, str)
- Error message strings
- Plain text output

Standard Tool Response Format:
    All tools should follow this standardized format for consistency:

    {
        "success": bool,           # Whether the overall operation succeeded
        "total": int,              # Total number of items processed
        "successful": int,         # Number of successful operations
        "failed": int,             # Number of failed operations
        "data": list[dict],       # Detailed results (one entry per item)
        "error": str,             # Global error message (if operation failed entirely)
        "metadata": dict          # Optional metadata (timestamp, execution_time, etc.)
    }

    Single item format (for data array items):
    {
        "id": str,                 # Device/node/link ID
        "name": str,               # Human-readable name
        "status": "success" | "failed",  # Item status
        "result": str,             # Success result or output
        "error": str               # Error message (if failed)
    }

Author: Yue Guobin (岳国宾)
"""

import ast
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def parse_tool_content(
    content: str | dict | list | int | float | bool | None,
    fallback_to_raw: bool = True,
    strict_mode: bool = False,
) -> dict[str, Any] | list[Any] | Any:
    """
    Parse tool execution results into structured data, specifically for UI display.

    This function can handle various input types including strings, dictionaries, lists,
    and primitive types. It ensures the returned data can be properly serialized
    by json.dumps.

    Args:
        content: Content returned by tools (can be str, dict, list, int, float, bool,
                 or None)
        fallback_to_raw: Whether to return raw content when parsing fails, default True
        strict_mode: Strict mode, raises exceptions when parsing fails, default False

    Returns:
        Union[Dict[str, Any], List[Any], Any]: Parsed data that can be serialized by
        json.dumps:
        - Successfully parsed JSON/Python literal data
        - Original dict/list objects (passed through)
        - Primitive types (int, float, bool, str)
        - {"raw": content} when unable to parse but fallback_to_raw=True
        - {"error": "error_message"} when parsing fails and fallback_to_raw=False
        - {} for None input

    Raises:
        ValueError: When strict_mode=True and parsing fails
        TypeError: When content type is unsupported and strict_mode=True

    Examples:
        >>> parse_tool_content('{"status": "success", "data": [1, 2, 3]}')
        {'status': 'success', 'data': [1, 2, 3]}

        >>> parse_tool_content({"status": "success"})
        {'status': 'success'}

        >>> parse_tool_content([1, 2, 3])
        [1, 2, 3]

        >>> parse_tool_content(42)
        42

        >>> parse_tool_content("{'name': 'PC1', 'status': 'ok'}")
        {'name': 'PC1', 'status': 'ok'}

        >>> parse_tool_content("Invalid JSON input: ...")
        {'raw': 'Invalid JSON input: ...'}

        >>> parse_tool_content("{}")
        {}

        >>> parse_tool_content(None)
        {}
    """
    # Log received input parameters
    logger.info(
        "Received parameters: fallback_to_raw=%s, strict_mode=%s, content=%s",
        fallback_to_raw,
        strict_mode,
        content,
    )

    # Handle None input
    if content is None:
        result: dict[str, Any] = {}
        logger.info("Content is None, returning: %s", result)
        return result

    # Handle dictionary objects (already parsed)
    if isinstance(content, dict):
        logger.info("Content is already a dictionary, returning: %s", content)
        return content

    # Handle list objects (JSON arrays)
    if isinstance(content, list):
        logger.info("Content is already a list, returning: %s", content)
        return content

    # Handle primitive types that are JSON serializable
    if isinstance(content, (str, int, float, bool)):
        # For strings, we need to try parsing them
        if isinstance(content, str):
            # Empty string handling
            if not content.strip():
                result = {}
                logger.info(
                    "Content is empty or whitespace, returning: %s", result
                )
                return result

            s = content.strip()

            # Handle empty dictionary case
            if s == "{}":
                result = {}
                logger.info(
                    "Content is empty dictionary, returning: %s", result
                )
                return result

            # Try to parse as Python literal
            # (higher priority as many tools return Python format strings)
            try:
                result = ast.literal_eval(s)
                logger.info(
                    "Successfully parsed as Python literal, returning: %s",
                    result,
                )
                return result
            except (ValueError, SyntaxError):
                pass

            # Try to parse as JSON
            try:
                result = json.loads(s)
                logger.info(
                    "Successfully parsed as JSON, returning: %s", result
                )
                return result
            except json.JSONDecodeError:
                pass

            # Handle parsing failure for strings
            error_msg = "Unable to parse content as JSON or Python literal"
            logger.warning("%s: %s", error_msg, s)

            if strict_mode:
                raise ValueError("%s. Content: %s", error_msg, s)

            if fallback_to_raw:
                result = {"raw": s}
                logger.info("Returning raw content as fallback: %s", result)
                return result
            result = {"error": error_msg}
            logger.info("Returning error: %s", result)
            return result
        # For non-string primitives (int, float, bool), return as-is
        logger.info(
            "Content is a primitive type %s, returning: %s",
            type(content).__name__,
            content,
        )
        return content

    # Handle unsupported types
    error_msg = (  # type: ignore[unreachable]
        "Content must be str, dict, list, int, float, bool, or None, got "
        f"{type(content).__name__}"
    )
    logger.error(error_msg)

    if strict_mode:
        raise TypeError(error_msg)

    if fallback_to_raw:
        result = {"raw": str(content)}
        logger.info("Returning raw content as fallback: %s", result)
        return result
    result = {"error": error_msg}
    logger.info("Returning error: %s", result)
    return result


def format_tool_response(
    content: str | dict | list | int | float | bool | None, indent: int = 2
) -> str:
    """
    Format tool response as a beautiful JSON string for UI display.

    This function ensures that the output is always a valid JSON string that can be
    properly displayed in UI interfaces.

    Args:
        content: Content returned by tools (can be str, dict, list, int, float, bool,
                 or None)
        indent: JSON indentation spaces, default 2

    Returns:
        str: Formatted JSON string, always valid JSON
    """
    logger.info("format_tool_response received input content: %s", content)
    logger.info("format_tool_response parameter indent: %s", indent)

    try:
        parsed = parse_tool_content(
            content, fallback_to_raw=True, strict_mode=False
        )
        # Ensure the result can be serialized to JSON
        result = json.dumps(parsed, ensure_ascii=False, indent=indent)
        logger.info("format_tool_response returning: %s", result)
        return result
    except (TypeError, ValueError) as e:
        # If the parsed result cannot be serialized, convert to string and wrap
        logger.error("Cannot serialize parsed result to JSON: %s", e)
        try:
            result = json.dumps(
                {"raw": str(content)}, ensure_ascii=False, indent=indent
            )
            logger.info("format_tool_response returning fallback: %s", result)
            return result
        except Exception:
            # Last resort: return a simple error message
            result = json.dumps(
                {"error": "Unable to format response"},
                ensure_ascii=False,
                indent=indent,
            )
            logger.info("format_tool_response returning error: %s", result)
            return result
    except Exception as e:
        logger.error("Error formatting tool response: %s", e)
        result = json.dumps(
            {"error": str(e)}, ensure_ascii=False, indent=indent
        )
        logger.info("format_tool_response returning error: %s", result)
        return result


def normalize_tool_response(
    response: dict | list | str, tool_name: str = "unknown"
) -> dict:
    """
    Normalize tool response to standard format for consistent frontend display.

    This function converts various tool response formats into a standardized structure
    that frontend code can rely on. It handles both legacy formats and new formats,
    ensuring backward compatibility.

    Args:
        response: Raw tool response (dict, list, or string)
        tool_name: Name of the tool (for error messages)

    Returns:
        dict: Normalized response in standard format:
            {
                "success": bool,
                "total": int,
                "successful": int,
                "failed": int,
                "data": list[dict],
                "error": str (optional),
                "metadata": dict
            }

    Examples:
        >>> normalize_tool_response({"status": "success", "output": "OK"})
        {'success': True, 'total': 1, 'successful': 1, 'failed': 0,
         'data': [{'status': 'success', 'result': 'OK'}], 'metadata': {}}

        >>> normalize_tool_response([{"device_name": "R1", "status": "success"}])
        {'success': True, 'total': 1, 'successful': 1, 'failed': 0,
         'data': [...], 'metadata': {}}
    """
    metadata = {
        "tool_name": tool_name,
        "normalized_at": datetime.utcnow().isoformat(),
    }

    # Handle error responses
    if (
        isinstance(response, dict)
        and "error" in response
        and len(response) == 1
    ):
        return {
            "success": False,
            "total": 0,
            "successful": 0,
            "failed": 0,
            "data": [],
            "error": str(response["error"]),
            "metadata": metadata,
        }

    # Handle empty responses
    if not response:
        return {
            "success": True,
            "total": 0,
            "successful": 0,
            "failed": 0,
            "data": [],
            "metadata": metadata,
        }

    # Handle list responses (most tools return list of device results)
    if isinstance(response, list):
        successful = sum(
            1
            for item in response
            if isinstance(item, dict) and item.get("status") == "success"
        )
        failed = len(response) - successful

        normalized_data = []
        for item in response:
            if isinstance(item, dict):
                normalized_item = {
                    "id": item.get("device_id")
                    or item.get("node_id")
                    or item.get("id")
                    or "",
                    "name": item.get("device_name") or item.get("name") or "",
                    "status": item.get("status", "unknown"),
                }
                if normalized_item["status"] == "success":
                    normalized_item["result"] = (
                        item.get("output") or item.get("result") or ""
                    )
                else:
                    normalized_item["error"] = (
                        item.get("error")
                        or item.get("output")
                        or "Unknown error"
                    )
                normalized_data.append(normalized_item)
            else:
                # Non-dict items in list
                normalized_data.append(
                    {
                        "id": "",
                        "name": "",
                        "status": "unknown",
                        "result": str(item),
                    }
                )

        return {
            "success": failed == 0,
            "total": len(response),
            "successful": successful,
            "failed": failed,
            "data": normalized_data,
            "metadata": metadata,
        }

    # Handle dict responses (some tools return summary + results)
    if isinstance(response, dict):
        # Check if already in standard format
        if "success" in response and "data" in response:
            return {
                "success": response.get("success", True),
                "total": response.get("total", len(response.get("data", []))),
                "successful": response.get("successful", 0),
                "failed": response.get("failed", 0),
                "data": response.get("data", []),
                "error": response.get("error"),
                "metadata": {**metadata, **response.get("metadata", {})},
            }

        # Legacy format: extract common fields
        total = (
            response.get("total_nodes")
            or response.get("total")
            or response.get("count", 1)
        )
        successful = (
            response.get("successful_nodes") or response.get("successful") or 0
        )
        failed = response.get("failed_nodes") or response.get("failed") or 0

        # Extract data from various possible locations
        data = []
        if "nodes" in response:
            data = response["nodes"]
        elif "results" in response:
            data = response["results"]
        elif "data" in response:
            data = response["data"]
        elif "output" in response:
            # Single device response
            data = [
                {
                    "name": response.get("device_name", ""),
                    "status": response.get("status", "success"),
                    "result": response["output"],
                }
            ]

        # If no data found but have status, create single item
        if not data and "status" in response:
            data = [
                {
                    "name": response.get("device_name")
                    or response.get("name")
                    or "",
                    "status": response["status"],
                    "result": response.get("output")
                    or response.get("result")
                    or "",
                    "error": response.get("error") or "",
                }
            ]

        # Recursively normalize data items
        if data and isinstance(data, list):
            return normalize_tool_response(data, tool_name)
        else:
            # No data array, return empty but preserve counts
            return {
                "success": failed == 0,
                "total": total,
                "successful": successful,
                "failed": failed,
                "data": [],
                "metadata": metadata,
            }

    # Handle string responses (parse first)
    if isinstance(response, str):
        parsed = parse_tool_content(response, fallback_to_raw=True)
        return normalize_tool_response(parsed, tool_name)

    # Fallback for unknown types
    return {
        "success": True,
        "total": 1,
        "successful": 1,
        "failed": 0,
        "data": [
            {
                "id": "",
                "name": "",
                "status": "unknown",
                "result": str(response),
            }
        ],
        "metadata": metadata,
    }


# Test function to verify the implementation
def _test_parse_tool_content() -> None:
    """Test function to verify parse_tool_content works correctly with all input
    types
    """
    test_cases: list[tuple[Any, Any]] = [
        # String inputs
        (
            '{"status": "success", "data": [1, 2, 3]}',
            {"status": "success", "data": [1, 2, 3]},
        ),
        ("{'name': 'PC1', 'status': 'ok'}", {"name": "PC1", "status": "ok"}),
        ("[1, 2, 3]", [1, 2, 3]),
        ('"hello"', "hello"),
        ("42", 42),
        ("true", True),
        ("3.14", 3.14),
        ("{}", {}),
        ("  {}  ", {}),
        ("", {}),
        ("   ", {}),
        ("Invalid JSON input", {"raw": "Invalid JSON input"}),
        # Direct object inputs
        ({"status": "success"}, {"status": "success"}),
        ([1, 2, 3], [1, 2, 3]),
        ("hello", "hello"),
        (42, 42),
        (True, True),
        (3.14, 3.14),
        (None, {}),
    ]

    print("Testing parse_tool_content function:")
    for i, (input_data, expected) in enumerate(test_cases):
        result = parse_tool_content(input_data)
        status = "✓" if result == expected else "✗"
        print(f"Test {i + 1}: {status} Input: {repr(input_data)} -> {result}")

    print("\nTesting format_tool_response function:")
    format_tests = [
        '{"status": "success"}',
        "{}",
        None,
        "Invalid input",
        {"direct": "dict"},
        [1, 2, 3],
        42,
        True,
    ]

    for i, input_data in enumerate(format_tests):
        result = format_tool_response(input_data)
        # Verify it's valid JSON
        try:
            json.loads(result)
            valid = "✓"
        except Exception:
            valid = "✗"
        print(
            f"Format Test {i + 1}: {valid} Input: {repr(input_data)} -> {result}"
        )


if __name__ == "__main__":
    _test_parse_tool_content()
