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
import urllib
import asyncio
import aiohttp
import logging
import traceback
import jsonschema


log = logging.getLogger(__name__)

from ..compute.error import NodeError, ImageMissingError
from ..controller.controller_error import ControllerError
from ..ubridge.ubridge_error import UbridgeError
from ..controller.gns3vm.gns3_vm_error import GNS3VMError
from .response import Response
from ..crash_report import CrashReport
from ..config import Config


@asyncio.coroutine
def parse_request(request, input_schema, raw):
    """Parse body of request and raise HTTP errors in case of problems"""

    request.json = {}
    if not raw:
        body = yield from request.read()
        if body:
            try:
                request.json = json.loads(body.decode('utf-8'))
            except ValueError as e:
                request.json = {"malformed_json": body.decode('utf-8')}
                raise aiohttp.web.HTTPBadRequest(text="Invalid JSON {}".format(e))

    # Parse the query string
    if len(request.query_string) > 0:
        for (k, v) in urllib.parse.parse_qs(request.query_string).items():
            request.json[k] = v[0]

    if input_schema:
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

    _node_locks = {}

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
            if request.headers["AUTHORIZATION"] == aiohttp.helpers.BasicAuth(user, password, "utf-8").encode():
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
        api_version = kw.get("api_version", 2)
        raw = kw.get("raw", False)

        def register(func):
            # Add the type of server to the route
            if "controller" in func.__module__:
                route = "/v{version}{path}".format(path=path, version=api_version)
            elif "compute" in func.__module__:
                route = "/v{version}/compute{path}".format(path=path, version=api_version)
            else:
                route = path

            # Compute metadata for the documentation
            if api_version:
                handler = func.__module__.replace("_handler", "").replace("gns3server.handlers.api.", "")
                cls._documentation.setdefault(handler, {})
                cls._documentation[handler].setdefault(route, {"api_version": api_version,
                                                               "controller": kw.get("controller", False),
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

                try:
                    # Non API call
                    if api_version is None or raw is True:
                        response = Response(request=request, route=route, output_schema=output_schema)

                        request = yield from parse_request(request, None, raw)
                        yield from func(request, response)
                        return response

                    # API call
                    request = yield from parse_request(request, input_schema, raw)
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
                    response.json({"message": e.text, "status": e.status, "path": route, "request": request.json, "method": request.method})
                except aiohttp.web.HTTPException as e:
                    response = Response(request=request, route=route)
                    response.set_status(e.status)
                    response.json({"message": e.text, "status": e.status})
                except (ControllerError, GNS3VMError) as e:
                    log.error("Controller error detected: {type}".format(type=type(e)), exc_info=1)
                    response = Response(request=request, route=route)
                    response.set_status(409)
                    response.json({"message": str(e), "status": 409})
                except (NodeError, UbridgeError) as e:
                    log.error("Node error detected: {type}".format(type=e.__class__.__name__), exc_info=1)
                    response = Response(request=request, route=route)
                    response.set_status(409)
                    response.json({"message": str(e), "status": 409, "exception": e.__class__.__name__})
                except (ImageMissingError) as e:
                    log.error("Image missing error detected: {}".format(e.image))
                    response = Response(request=request, route=route)
                    response.set_status(409)
                    response.json({"message": str(e), "status": 409, "image": e.image, "exception": e.__class__.__name__})
                except asyncio.futures.CancelledError as e:
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
            def node_concurrency(request):
                """
                To avoid strange effect we prevent concurrency
                between the same instance of the node
                """

                if "node_id" in request.match_info:
                    node_id = request.match_info.get("node_id")

                    if "compute" in request.path:
                        type = "compute"
                    else:
                        type = "controller"
                    lock_key = "{}:{}:{}".format(type, request.match_info["project_id"], node_id)
                    cls._node_locks.setdefault(lock_key, {"lock": asyncio.Lock(), "concurrency": 0})
                    cls._node_locks[lock_key]["concurrency"] += 1

                    with (yield from cls._node_locks[lock_key]["lock"]):
                        response = yield from control_schema(request)
                    cls._node_locks[lock_key]["concurrency"] -= 1

                    # No more waiting requests, garbage collect the lock
                    if cls._node_locks[lock_key]["concurrency"] <= 0:
                        del cls._node_locks[lock_key]
                else:
                    response = yield from control_schema(request)
                return response

            cls._routes.append((method, route, node_concurrency))

            return node_concurrency
        return register

    @classmethod
    def get_routes(cls):
        return cls._routes

    @classmethod
    def get_documentation(cls):
        return cls._documentation
