# -*- coding: utf-8 -*-
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

import json
import jsonschema
import aiohttp
import aiohttp.web
import mimetypes
import asyncio
import logging
import jinja2
import sys
import os

from ..utils.get_resource import get_resource
from ..version import __version__

log = logging.getLogger(__name__)
renderer = jinja2.Environment(loader=jinja2.FileSystemLoader(get_resource('templates')))


class Response(aiohttp.web.Response):

    def __init__(self, request=None, route=None, output_schema=None, headers={}, **kwargs):
        self._route = route
        self._output_schema = output_schema
        self._request = request
        headers['Connection'] = "close"  # Disable keep alive because create trouble with old Qt (5.2, 5.3 and 5.4)
        headers['X-Route'] = self._route
        headers['Server'] = "Python/{0[0]}.{0[1]} GNS3/{1}".format(sys.version_info, __version__)
        super().__init__(headers=headers, **kwargs)

    @asyncio.coroutine
    def prepare(self, request):
        if log.getEffectiveLevel() == logging.DEBUG:
            log.info("%s %s", request.method, request.path_qs)
            log.debug("%s", dict(request.headers))
            if isinstance(request.json, dict):
                log.debug("%s", request.json)
            log.info("Response: %d %s", self.status, self.reason)
            log.debug(dict(self.headers))
            if hasattr(self, 'body') and self.body is not None and self.headers["CONTENT-TYPE"] == "application/json":
                log.debug(json.loads(self.body.decode('utf-8')))
        return (yield from super().prepare(request))

    def html(self, answer):
        """
        Set the response content type to text/html and serialize
        the content.

        :param anwser The response as a Python object
        """

        self.content_type = "text/html"
        self.body = answer.encode('utf-8')

    def template(self, template_filename, **kwargs):
        """
        Render a template

        :params template: Template name
        :params kwargs: Template parameters
        """
        template = renderer.get_template(template_filename)
        kwargs["gns3_version"] = __version__
        kwargs["gns3_host"] = self._request.host
        self.html(template.render(**kwargs))

    def json(self, answer):
        """
        Set the response content type to application/json and serialize
        the content.

        :param anwser The response as a Python object
        """

        self.content_type = "application/json"
        if hasattr(answer, '__json__'):
            answer = answer.__json__()
        elif isinstance(answer, list):
            newanswer = []
            for elem in answer:
                if hasattr(elem, '__json__'):
                    elem = elem.__json__()
                newanswer.append(elem)
            answer = newanswer
        if self._output_schema is not None:
            try:
                jsonschema.validate(answer, self._output_schema)
            except jsonschema.ValidationError as e:
                log.error("Invalid output query. JSON schema error: {}".format(e.message))
                raise aiohttp.web.HTTPBadRequest(text="{}".format(e))
        self.body = json.dumps(answer, indent=4, sort_keys=True).encode('utf-8')

    @asyncio.coroutine
    def file(self, path):
        """
        Return a file as a response
        """
        ct, encoding = mimetypes.guess_type(path)
        if not ct:
            ct = 'application/octet-stream'
        if encoding:
            self.headers[aiohttp.hdrs.CONTENT_ENCODING] = encoding
        self.content_type = ct

        st = os.stat(path)
        self.last_modified = st.st_mtime
        self.content_length = st.st_size

        with open(path, 'rb') as fobj:
            self.start(self._request)
            chunk_size = 4096
            chunk = fobj.read(chunk_size)
            while chunk:
                self.write(chunk)
                yield from self.drain()
                chunk = fobj.read(chunk_size)

            if chunk:
                self.write(chunk[:count])
                yield from self.drain()

    def redirect(self, url):
        """
        Redirect to url

        :params url: Redirection URL
        """
        raise aiohttp.web.HTTPFound(url)
