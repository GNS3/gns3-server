#!/usr/bin/env python
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

"""
This script connect to the local GNS3 server and will create a random topology
"""

import sys
import json
import math
import aiohttp
import aiohttp.web
import asyncio
import async_timeout

import coloredlogs
import logging

coloredlogs.install(fmt=" %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PROJECT_ID = "9e26e37d-4962-4921-8c0e-136d3b04ba9c"


def die(*args):
    log.error(*args)
    sys.exit(1)


class HTTPError(Exception):

    def __init__(self, method, path, response):
        self._method = method
        self._path = path
        self._response = response

    @property
    def response(self):
        return self._response

    @property
    def path(self):
        return self._path

    @property
    def method(self):
        return self._method


class HTTPConflict(HTTPError):
    pass


async def query(method, path, body=None, **kwargs):
    global session

    if body:
        kwargs["data"] = json.dumps(body)

    with async_timeout.timeout(10):
        async with session.request(method, "http://localhost:3080/v2" + path, **kwargs) as response:
            if response.status == 409:
                raise HTTPConflict(method, path, response)
            elif response.status >= 300:
                raise HTTPError(method, path, response)
            log.info("%s %s %d", method, path, response.status)
            if response.headers["content-type"] == "application/json":
                return await response.json()
            else:
                return "{}"


async def post(path, **kwargs):
    return await query("POST", path, **kwargs)


async def get(path, **kwargs):
    return await query("GET", path, **kwargs)


async def delete(path, **kwargs):
    return await query("DELETE", path, **kwargs)


async def create_project():
    # Delete project if already exists
    response = await get("/projects")
    project_exists = False
    for project in response:
        if project["name"] == "random":
            await delete("/projects/" + project["project_id"])
        elif project["project_id"] == PROJECT_ID:
            project_exists = True
            for node in await get("/projects/" + PROJECT_ID + "/nodes"):
                delete("/projects/" + PROJECT_ID + "/nodes/" + node["node_id"])
    if project_exists:
        response = await post("/projects/" + PROJECT_ID + "/open")
    return response


async def create_node(project):
    global node_i
    response = await post("/projects/{}/nodes".format(project["project_id"]), body={
        "node_type": "vpcs",
        "compute_id": "local",
        "name": "Node{}".format(node_i),
        "x": (math.floor(node_i / 10) * 100) - 300,
        "y": (math.ceil(node_i / 10) * 100) - 200
    })
    node_i += 1
    return response


async def build_topology():
    global node_i

    # Use for node names uniqueness
    node_i = 1
    nodes = {}
    project = await create_project()
    while True:
        node = await create_node(project)
        nodes[node["node_id"]] = node
        await asyncio.sleep(1)

async def main(loop):
    global session
    async with aiohttp.ClientSession() as session:
        try:
            await build_topology()
        except HTTPError as error:
            try:
                j = await error.response.json()
                die("%s %s invalid status %d:\n%s", error.method, error.path, error.response.status, json.dumps(j, indent=4))
            except json.decoder.JSONDecodeError:
                die("%s %s invalid status %d", error.method, error.path, error.response.status)


loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop))

if session:
    session.close()
