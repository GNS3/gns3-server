#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

import asyncio
import aiohttp

from ...web.route import Route
from ...schemas.file import FILE_STREAM_SCHEMA


class FileHandler:

    @classmethod
    @Route.get(
        r"/files/stream",
        description="Stream a file from the server",
        status_codes={
            200: "File retrieved",
            404: "File doesn't exist",
            409: "Can't access to file"
        },
        input=FILE_STREAM_SCHEMA
    )
    def read(request, response):
        response.enable_chunked_encoding()

        if not request.json.get("location").endswith(".pcap"):
            raise aiohttp.web.HTTPForbidden(text="Only .pcap file are allowed")

        try:
            with open(request.json.get("location"), "rb") as f:
                loop = asyncio.get_event_loop()
                response.content_type = "application/octet-stream"
                response.set_status(200)
                # Very important: do not send a content lenght otherwise QT close the connection but curl can consume the Feed
                response.content_length = None

                response.start(request)

                while True:
                    data = yield from loop.run_in_executor(None, f.read, 16)
                    if len(data) == 0:
                        yield from asyncio.sleep(0.1)
                    else:
                        response.write(data)
        except FileNotFoundError:
            raise aiohttp.web.HTTPNotFound()
        except OSError as e:
            raise aiohttp.web.HTTPConflict(text=str(e))
