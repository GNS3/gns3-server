#!/usr/bin/env python
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

"""
Error response helpers shared by the exception handlers and the OpenAPI schema.
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi.responses import JSONResponse

from gns3server.schemas.common import ErrorMessage

AUTHENTICATED_ERROR_RESPONSES = {
    401: "Authentication is required or the credentials are invalid",
    403: "Not enough privileges to perform this operation",
    422: "Request validation error",
}


def code_for_status(status_code: int) -> str:
    try:
        phrase = HTTPStatus(status_code).phrase
    except ValueError:
        return "error"
    return phrase.lower().replace(" ", "_").replace("-", "_")


def error_response(
    status_code: int,
    message: Any,
    code: str | None = None,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {"message": message, "code": code or code_for_status(status_code)}
    if details:
        content["details"] = details
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def customize_openapi_errors(schema: dict[str, Any]) -> dict[str, Any]:
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)
    if "ErrorMessage" not in components:
        error_schema = ErrorMessage.model_json_schema(ref_template="#/components/schemas/{model}")
        components["ErrorMessage"] = {k: v for k, v in error_schema.items() if k != "$defs"}

    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            responses = operation["responses"]
            wanted = ["422"] if "422" in responses else []
            if operation.get("security"):
                wanted = ["401", "403", "422"]
            for status_code in wanted:
                responses[status_code] = {
                    "description": AUTHENTICATED_ERROR_RESPONSES[int(status_code)],
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorMessage"}}},
                }
    return schema
