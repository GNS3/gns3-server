#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import os
import asyncio
import mimetypes
from aiohttp import hdrs

from gns3server.web.route import Route
from gns3server.utils.get_resource import get_resource


class StaticHandler:

    @Route.get(
        r"/static/{type}/{path:.+}",
        description="Serve static content from various locations"
    )
    def get(request, response):
        type = request.match_info["type"]
        # CLeanup the path for security
        path = os.path.normpath(request.match_info["path"]).strip('/.')
        if type == "builtin_symbols":
            try:
                yield from StaticHandler._serve_file(os.path.join(get_resource("symbols"), path), request, response)
            except OSError:
                response.set_status(404)

    @asyncio.coroutine
    def _serve_file(path, request, response):
        ct, encoding = mimetypes.guess_type(path)
        if not ct:
            ct = 'application/octet-stream'
        if encoding:
            response.headers[hdrs.CONTENT_ENCODING] = encoding
        response.content_type = ct

        st = os.stat(path)
        response.last_modified = st.st_mtime
        response.content_length = st.st_size

        with open(path, 'rb') as fobj:
            response.start(request)
            chunk_size = 4096
            chunk = fobj.read(chunk_size)
            while chunk:
                response.write(chunk)
                yield from response.drain()
                chunk = fobj.read(chunk_size)

            if chunk:
                response.write(chunk[:count])
                yield from response.drain()
