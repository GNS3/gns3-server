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
import asyncio
import aiohttp

from .response import Response


@asyncio.coroutine
def parse_request(request, input_schema):
    """Parse body of request and raise HTTP errors in case of problems"""
    content_length = request.content_length
    if content_length is not None and content_length > 0:
        body = yield from request.read()
        try:
            request.json = json.loads(body.decode('utf-8'))
        except ValueError as e:
            raise aiohttp.web.HTTPBadRequest(text="Invalid JSON {}".format(e))
    try:
        jsonschema.validate(request.json, input_schema)
    except jsonschema.ValidationError as e:
        raise aiohttp.web.HTTPBadRequest(text="Request is not {} '{}' in schema: {}".format(
            e.validator,
            e.validator_value,
            json.dumps(e.schema)))
    return request


class Route(object):
    """ Decorator adding:
        * json schema verification
        * routing inside handlers
        * documentation information about endpoints
    """

    _routes = []
    _documentation = {}

    @classmethod
    def get(cls, path, *args, **kw):
        return cls._route('GET', path, *args, **kw)

    @classmethod
    def post(cls, path, *args, **kw):
        return cls._route('POST', path, *args, **kw)

    @classmethod
    def put(cls, path, *args, **kw):
        return cls._route('PUT', path, *args, **kw)

    @classmethod
    def _route(cls, method, path, *args, **kw):
        # This block is executed only the first time
        output_schema = kw.get("output", {})
        input_schema = kw.get("input", {})
        cls._path = path
        cls._documentation.setdefault(cls._path, {"methods": []})

        def register(func):
            route = cls._path

            cls._documentation[route]["methods"].append({
                "method": method,
                "status_codes": kw.get("status_codes", {200: "OK"}),
                "parameters": kw.get("parameters", {}),
                "output_schema": output_schema,
                "input_schema": input_schema,
                "description": kw.get("description", "")
            })
            func = asyncio.coroutine(func)

            @asyncio.coroutine
            def control_schema(request):
                # This block is executed at each method call
                try:
                    request = yield from parse_request(request, input_schema)
                    response = Response(route=route, output_schema=output_schema)
                    yield from func(request, response)
                except aiohttp.web.HTTPException as e:
                    response = Response(route=route)
                    response.set_status(e.status)
                    response.json({"message": e.text, "status": e.status})
                return response

            cls._routes.append((method, cls._path, control_schema))

            return control_schema
        return register

    @classmethod
    def get_routes(cls):
        return cls._routes

    @classmethod
    def get_documentation(cls):
        return cls._documentation
