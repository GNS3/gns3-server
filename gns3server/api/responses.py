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

from typing import Any

from fastapi.responses import JSONResponse

from gns3server import schemas

NDJSON_MEDIA_TYPE = "application/x-ndjson"


class NDJSONResponse(JSONResponse):
    """
    Only used as the response_class of streaming routes to publish the application/x-ndjson media type
    and the schema of the streamed objects in the OpenAPI document.
    """

    media_type = NDJSON_MEDIA_TYPE


NOTIFICATION_STREAM_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "model": schemas.Notification,
        "description": "Stream of notifications, one JSON object per line. "
        "Each line is a Notification, the first one is a ping and then a ping is sent at least every 5 seconds.",
    }
}
