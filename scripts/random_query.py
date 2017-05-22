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
import random

import coloredlogs
import logging

coloredlogs.install(fmt=" %(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PROJECT_ID = "9e26e37d-4962-4921-8c0e-136d3b04ba9c"
HOST = "192.168.84.151:3080"

# Use for node names uniqueness
node_i = 1


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


class HTTPNotFound(HTTPError):
    pass


async def query(method, path, body=None, **kwargs):
    global session

    if body:
        kwargs["data"] = json.dumps(body)

    async with session.request(method, "http://" + HOST + "/v2" + path, **kwargs) as response:
        if response.status == 409:
            raise HTTPConflict(method, path, response)
        elif response.status == 404:
            raise HTTPNotFound(method, path, response)
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
        if project["name"] == "random" and project["project_id"] != PROJECT_ID:
            await delete("/projects/" + project["project_id"])
        elif project["project_id"] == PROJECT_ID:
            project_exists = True
            tasks = []
            for node in await get("/projects/" + PROJECT_ID + "/nodes"):
                tasks.append(delete_node(project, node))
            await asyncio.gather(*tasks)
    if project_exists:
        response = await post("/projects/" + PROJECT_ID + "/open")
    else:
        response = await post("/projects", body={"name": "random", "project_id": PROJECT_ID, "auto_close": False})
    return response


async def create_node(project):
    global node_i

    r = random.randint(0, 1)

    if r == 0:
        node_type = "ethernet_switch"
        symbol = ":/symbols/ethernet_switch.svg"
    elif r == 1:
        node_type = "vpcs"
        symbol = ":/symbols/vpcs_guest.svg"
    response = await post("/projects/{}/nodes".format(project["project_id"]), body={
        "node_type": node_type,
        "compute_id": "local",
        "symbol": symbol,
        "name": "Node{}".format(node_i),
        "x": (math.floor((node_i - 1) % 12.0) * 100) - 500,
        "y": (math.ceil((node_i) / 12.0) * 100) - 300
    })
    node_i += 1
    return response


async def delete_node(project, node):
    await delete("/projects/{}/nodes/{}".format(project["project_id"], node["node_id"]))


async def create_link(project, nodes):
    """
    Create all possible link of a node
    """
    node1 = random.choice(list(nodes.values()))

    for port in range(0, 8):
        node2 = random.choice(list(nodes.values()))

        if node1 == node2:
            continue

        data = {"nodes":
                [
                    {
                        "adapter_number": 0,
                        "node_id": node1["node_id"],
                        "port_number": port
                    },
                    {
                        "adapter_number": 0,
                        "node_id": node2["node_id"],
                        "port_number": port
                    }
                ]
                }
        try:
            await post("/projects/{}/links".format(project["project_id"]), body=data)
        except (HTTPConflict, HTTPNotFound):
            pass


async def build_topology():
    global node_i

    nodes = {}
    project = await create_project()
    while True:
        rand = random.randint(0, 1000)
        if rand < 500:  # chance to create a new node
            if len(nodes.keys()) < 255:  # Limit of VPCS:
                node = await create_node(project)
                nodes[node["node_id"]] = node
        elif rand < 600:  # start all nodes
            await post("/projects/{}/nodes/start".format(project["project_id"]))
        elif rand < 700:  # stop all nodes
            await post("/projects/{}/nodes/stop".format(project["project_id"]))
        elif rand < 950:  # create a link
            if len(nodes.keys()) >= 2:
                await create_link(project, nodes)
        elif rand < 999:  # chance to delete a node
            continue
            if len(nodes.keys()) > 0:
                node = random.choice(list(nodes.values()))
                await delete_node(project, node)
                del nodes[node["node_id"]]
        elif len(nodes.keys()) > 0:  # % chance to delete all nodes
            continue
            node_i = 1
            tasks = []
            for node in nodes.values():
                tasks.append(delete_node(project, node))
            await asyncio.gather(*tasks)
            nodes = {}
        await asyncio.sleep(0.2)

async def main(loop):
    global session
    async with aiohttp.ClientSession() as session:
        try:
            await build_topology()
        except HTTPError as error:
            try:
                j = await error.response.json()
                die("%s %s invalid status %d:\n%s", error.method, error.path, error.response.status, json.dumps(j, indent=4))
            except (ValueError, aiohttp.ServerDisconnectedError):
                die("%s %s invalid status %d", error.method, error.path, error.response.status)


loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop))

if session:
    session.close()
