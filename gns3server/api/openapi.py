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

from typing import Any, Dict

BINARY_SCHEMA: Dict[str, Any] = {"type": "string", "format": "binary"}

NOTIFICATION_LINE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "description": "One notification event per line",
    "properties": {
        "action": {"type": "string"},
        "event": {"description": "Event payload, its shape depends on the action"},
    },
    "required": ["action", "event"],
    "additionalProperties": True,
}

PCAP_MEDIA_TYPE = "application/vnd.tcpdump.pcap"
NDJSON_MEDIA_TYPE = "application/x-ndjson"
OCTET_STREAM_MEDIA_TYPE = "application/octet-stream"
ZIP_MEDIA_TYPE = "application/zip"


def binary_response(media_type: str = OCTET_STREAM_MEDIA_TYPE, description: str = "Binary content") -> Dict[str, Any]:
    return {"description": description, "content": {media_type: {"schema": BINARY_SCHEMA}}}


def ndjson_response(description: str = "Stream of newline-delimited JSON notifications") -> Dict[str, Any]:
    return {"description": description, "content": {NDJSON_MEDIA_TYPE: {"schema": NOTIFICATION_LINE_SCHEMA}}}


def binary_request_body(media_type: str = OCTET_STREAM_MEDIA_TYPE) -> Dict[str, Any]:
    return {"requestBody": {"required": True, "content": {media_type: {"schema": BINARY_SCHEMA}}}}
