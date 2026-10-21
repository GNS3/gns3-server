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

import re
import warnings
from collections import Counter

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi

from gns3server.api.operation_ids import STUB_METHODS, add_stub_routes, generate_operation_id
from gns3server.api.routes.compute import compute_api
from gns3server.api.server import app as controller_app

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def build_operation_ids(application: FastAPI) -> list[str]:

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        spec = get_openapi(title="test", version="0", routes=application.routes)
    return [
        operation["operationId"]
        for path_item in spec["paths"].values()
        for method, operation in path_item.items()
        if method in HTTP_METHODS
    ]


@pytest.mark.parametrize("application", [controller_app, compute_api], ids=["controller", "compute"])
def test_operation_ids_are_unique_and_readable(application: FastAPI) -> None:

    operation_ids = build_operation_ids(application)
    assert operation_ids
    duplicates = [operation_id for operation_id, count in Counter(operation_ids).items() if count > 1]
    assert duplicates == []
    invalid = [operation_id for operation_id in operation_ids if not re.fullmatch(r"[a-z0-9_]+", operation_id)]
    assert invalid == []


def test_operation_id_uses_first_tag_and_function_name() -> None:

    router = APIRouter()

    @router.get("/nodes/{node_id}", tags=["Compute nodes", "Other"])
    async def get_node(node_id: str):
        return {}

    @router.get("/untagged")
    async def list_untagged():
        return {}

    assert generate_operation_id(router.routes[0]) == "compute_nodes_get_node"
    assert generate_operation_id(router.routes[1]) == "list_untagged"


def test_stub_routes_get_one_operation_id_per_method() -> None:

    async def not_available(path: str = ""):
        return {}

    application = FastAPI(generate_unique_id_function=generate_operation_id)
    router = APIRouter(tags=["Stub"])
    add_stub_routes(router, not_available, "stub")
    application.include_router(router, prefix="/stub")

    assert sorted(build_operation_ids(application)) == sorted(f"stub_stub_{method.lower()}" for method in STUB_METHODS)
