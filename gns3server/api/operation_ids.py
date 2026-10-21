#!/usr/bin/env python
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

"""
Readable and unique OpenAPI operationIds.
"""

import re
from typing import Callable

from fastapi import APIRouter
from fastapi.routing import APIRoute

STUB_METHODS = ("GET", "POST", "DELETE", "PATCH", "PUT")


def _slug(value: str) -> str:

    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def generate_operation_id(route: APIRoute) -> str:
    """
    Builds an operationId such as "nodes_get_node" from the first tag and the route name.
    """

    name = _slug(route.name)
    if route.tags:
        tag = _slug(str(route.tags[0]))
        if tag:
            return f"{tag}_{name}"
    return name


def add_stub_routes(router: APIRouter, endpoint: Callable, name: str) -> None:
    """
    Registers a catch-all route per HTTP method so that every method gets its own operationId.
    """

    for method in STUB_METHODS:
        router.add_api_route("/{path:path}", endpoint, methods=[method], name=f"{name}_{method.lower()}")
