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

import sys
import json
import jsonschema
import asyncio
import aiohttp
import logging
import traceback

log = logging.getLogger(__name__)

from ..modules.vm_error import VMError
from ..ubridge.ubridge_error import UbridgeError
from .response import Response
from ..crash_report import CrashReport
from ..config import Config


@asyncio.coroutine
def parse_request(request, input_schema):
    """Parse body of request and raise HTTP errors in case of problems"""
    content_length = request.content_length
    if content_length is not None and content_length > 0:
        body = yield from request.read()
        try:
            request.json = json.loads(body.decode('utf-8'))
        except ValueError as e:
            request.json = {"malformed_json": body.decode('utf-8')}
            raise aiohttp.web.HTTPBadRequest(text="Invalid JSON {}".format(e))
    else:
        request.json = {}
    try:
        jsonschema.validate(request.json, input_schema)
    except jsonschema.ValidationError as e:
        log.error("Invalid input query. JSON schema error: {}".format(e.message))
        raise aiohttp.web.HTTPBadRequest(text="Invalid JSON: {} in schema: {}".format(
            e.message,
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

    _vm_locks = {}

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
    def delete(cls, path, *args, **kw):
        return cls._route('DELETE', path, *args, **kw)

    @classmethod
    def authenticate(cls, request, route, server_config):
        """
        Ask user for authentication

        :returns: Response if you need to auth the user otherwise None
        """
        if not server_config.getboolean("auth", False):
            return

        user = server_config.get("user", "").strip()
        password = server_config.get("password", "").strip()

        if len(user) == 0:
            return

        if "AUTHORIZATION" in request.headers:
            if request.headers["AUTHORIZATION"] == aiohttp.helpers.BasicAuth(user, password).encode():
                return

        log.error("Invalid auth. Username should %s", user)

        response = Response(request=request, route=route)
        response.set_status(401)
        response.headers["WWW-Authenticate"] = 'Basic realm="GNS3 server"'
        # Force close the keep alive. Work around a Qt issue where Qt timeout instead of handling the 401
        # this happen only for the first query send by the client.
        response.force_close()
        return response

    @classmethod
    def _route(cls, method, path, *args, **kw):
        # This block is executed only the first time
        output_schema = kw.get("output", {})
        input_schema = kw.get("input", {})
        api_version = kw.get("api_version", 1)
        raw = kw.get("raw", False)

        # If it's a JSON api endpoint just register the endpoint an do nothing
        if api_version is None:
            cls._path = path
        else:
            cls._path = "/v{version}{path}".format(path=path, version=api_version)

        def register(func):
            route = cls._path

            handler = func.__module__.replace("_handler", "").replace("gns3server.handlers.api.", "")
            cls._documentation.setdefault(handler, {})
            cls._documentation[handler].setdefault(route, {"api_version": api_version,
                                                           "methods": []})

            cls._documentation[handler][route]["methods"].append({
                "method": method,
                "status_codes": kw.get("status_codes", {200: "OK"}),
                "parameters": kw.get("parameters", {}),
                "output_schema": output_schema,
                "input_schema": input_schema,
                "description": kw.get("description", ""),
            })
            func = asyncio.coroutine(func)

            @asyncio.coroutine
            def control_schema(request):
                # This block is executed at each method call

                server_config = Config.instance().get_section_config("Server")

                # Authenticate
                response = cls.authenticate(request, route, server_config)
                if response:
                    return response

                # Non API call
                if api_version is None or raw is True:
                    response = Response(request=request, route=route, output_schema=output_schema)

                    yield from func(request, response)
                    return response

                # API call
                try:
                    request = yield from parse_request(request, input_schema)
                    record_file = server_config.get("record")
                    if record_file:
                        try:
                            with open(record_file, "a", encoding="utf-8") as f:
                                f.write("curl -X {} 'http://{}{}' -d '{}'".format(request.method, request.host, request.path_qs, json.dumps(request.json)))
                                f.write("\n")
                        except OSError as e:
                            log.warn("Could not write to the record file {}: {}".format(record_file, e))
                    response = Response(request=request, route=route, output_schema=output_schema)
                    yield from func(request, response)
                except aiohttp.web.HTTPBadRequest as e:
                    response = Response(request=request, route=route)
                    response.set_status(e.status)
                    response.json({"message": e.text, "status": e.status, "path": route, "request": request.json})
                except aiohttp.web.HTTPException as e:
                    response = Response(request=request, route=route)
                    response.set_status(e.status)
                    response.json({"message": e.text, "status": e.status})
                except (VMError, UbridgeError) as e:
                    log.error("VM error detected: {type}".format(type=type(e)), exc_info=1)
                    response = Response(request=request, route=route)
                    response.set_status(409)
                    response.json({"message": str(e), "status": 409})
                except asyncio.futures.CancelledError as e:
                    log.error("Request canceled")
                    response = Response(request=request, route=route)
                    response.set_status(408)
                    response.json({"message": "Request canceled", "status": 408})
                except aiohttp.ClientDisconnectedError:
                    log.warn("Client disconnected")
                    response = Response(request=request, route=route)
                    response.set_status(408)
                    response.json({"message": "Client disconnected", "status": 408})
                except ConnectionResetError:
                    log.error("Client connection reset")
                    response = Response(request=request, route=route)
                    response.set_status(408)
                    response.json({"message": "Connection reset", "status": 408})
                except Exception as e:
                    log.error("Uncaught exception detected: {type}".format(type=type(e)), exc_info=1)
                    response = Response(request=request, route=route)
                    response.set_status(500)
                    CrashReport.instance().capture_exception(request)
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    lines = traceback.format_exception(exc_type, exc_value, exc_tb)
                    if api_version is not None:
                        tb = "".join(lines)
                        response.json({"message": tb, "status": 500})
                    else:
                        tb = "\n".join(lines)
                        response.html("<h1>Internal error</h1><pre>{}</pre>".format(tb))

                return response

            @asyncio.coroutine
            def vm_concurrency(request):
                """
                To avoid strange effect we prevent concurrency
                between the same instance of the vm
                """

                if "vm_id" in request.match_info or "device_id" in request.match_info:
                    vm_id = request.match_info.get("vm_id")
                    if vm_id is None:
                        vm_id = request.match_info["device_id"]
                    cls._vm_locks.setdefault(vm_id, {"lock": asyncio.Lock(), "concurrency": 0})
                    cls._vm_locks[vm_id]["concurrency"] += 1

                    with (yield from cls._vm_locks[vm_id]["lock"]):
                        response = yield from control_schema(request)
                    cls._vm_locks[vm_id]["concurrency"] -= 1

                    # No more waiting requests, garbage collect the lock
                    if cls._vm_locks[vm_id]["concurrency"] <= 0:
                        del cls._vm_locks[vm_id]
                else:
                    response = yield from control_schema(request)
                return response

            cls._routes.append((method, cls._path, vm_concurrency))

            return vm_concurrency
        return register

    @classmethod
    def get_routes(cls):
        return cls._routes

    @classmethod
    def get_documentation(cls):
        return cls._documentation
