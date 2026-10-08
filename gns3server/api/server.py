#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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
FastAPI app
"""

from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from uvicorn.main import Server as UvicornServer

# MCP is an optional feature — import only if dependencies are installed
from gns3server.agent import MCP_AVAILABLE
from gns3server.api.errors import customize_openapi_errors, error_response
from gns3server.api.routes import controller, index
from gns3server.api.routes.compute import compute_api
from gns3server.controller.controller_error import (
    ComputeConflictError,
    ControllerBadRequestError,
    ControllerError,
    ControllerForbiddenError,
    ControllerNotFoundError,
    ControllerTimeoutError,
    ControllerUnauthorizedError,
)
from gns3server.core import tasks

if MCP_AVAILABLE:
    from gns3server.agent import mcp

    _mcp_router = mcp.router
else:
    from fastapi import APIRouter

    _mcp_router = APIRouter(prefix="/mcp", tags=["MCP"])

    @_mcp_router.api_route("/{path:path}", methods=["GET", "POST", "DELETE", "PATCH", "PUT"])
    async def mcp_not_available(path: str = ""):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="MCP is not available. Install AI dependencies with: pip install gns3-server[ai-features]",
        )


import logging

log = logging.getLogger(__name__)


class ControllerAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        if self.openapi_schema is None:
            customize_openapi_errors(super().openapi())
        return cast(dict[str, Any], self.openapi_schema)


def get_application() -> FastAPI:

    application = ControllerAPI(
        lifespan=tasks.lifespan,
        title="GNS3 controller API",
        description="This page describes the public controller API for GNS3.\n\n"
        "## Notification streams\n\n"
        "Notifications are available as HTTP streams of newline delimited JSON objects (`GET /v3/notifications` and "
        "`GET /v3/projects/{project_id}/notifications`) and as WebSockets sending one JSON object per text frame "
        "(`/v3/notifications/ws`, `/v3/projects/{project_id}/notifications/ws` and "
        "`/v3/projects/{project_id}/notifications/markers/ws`). "
        "OpenAPI cannot describe WebSocket routes, they carry the same `Notification` messages as the HTTP streams. "
        "Marker events (`marker.match`) are only sent on the markers WebSocket.",
        version="3.0.0",
        docs_url=None,
        redoc_url=None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http(s)?://(localhost|127.0.0.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(index.router, tags=["Index"])
    application.include_router(controller.router, prefix="/v3")
    application.mount("/static", StaticFiles(packages=[("gns3server", "static")], html=True), name="static")
    application.mount("/v3/compute", compute_api, name="compute")

    # Register MCP routes (stub returns 501 if MCP dependencies are not installed)
    application.include_router(_mcp_router, prefix="/v3", tags=["MCP"])

    return application


app = get_application()

# Register MCP SSE transport routes (Starlette-level, for raw ASGI access)
if MCP_AVAILABLE:
    mcp.register_starlette_routes(app)

# Monkey Patch uvicorn signal handler to detect the application is shutting down
app.state.exiting = False
unicorn_exit_handler = UvicornServer.handle_exit


def handle_exit(*args, **kwargs):
    app.state.exiting = True
    unicorn_exit_handler(*args, **kwargs)


UvicornServer.handle_exit = handle_exit  # type: ignore[method-assign]


# Configure self-hosting JavaScript and CSS for docs
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
        swagger_favicon_url="/static/favicon.ico",
    )


@app.get(cast(str, app.swagger_ui_oauth2_redirect_url), include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
        redoc_favicon_url="/static/favicon.ico",
    )


@app.exception_handler(ControllerError)
async def controller_error_handler(request: Request, exc: ControllerError):
    log.error(f"Controller error in {request.url.path} ({request.method}): {exc}")
    return error_response(status.HTTP_409_CONFLICT, str(exc), exc.code, exc.details)


@app.exception_handler(ControllerTimeoutError)
async def controller_timeout_error_handler(request: Request, exc: ControllerTimeoutError):
    log.error(f"Controller timeout error in {request.url.path} ({request.method}): {exc}")
    return error_response(status.HTTP_408_REQUEST_TIMEOUT, str(exc), exc.code, exc.details)


@app.exception_handler(ControllerUnauthorizedError)
async def controller_unauthorized_error_handler(request: Request, exc: ControllerUnauthorizedError):
    log.error(f"Controller unauthorized error in {request.url.path} ({request.method}): {exc}")
    return error_response(status.HTTP_401_UNAUTHORIZED, str(exc), exc.code, exc.details)


@app.exception_handler(ControllerForbiddenError)
async def controller_forbidden_error_handler(request: Request, exc: ControllerForbiddenError):
    log.error(f"Controller forbidden error in {request.url.path} ({request.method}): {exc}")
    return error_response(status.HTTP_403_FORBIDDEN, str(exc), exc.code, exc.details)


@app.exception_handler(ControllerNotFoundError)
async def controller_not_found_error_handler(request: Request, exc: ControllerNotFoundError):
    log.error(f"Controller not found error in {request.url.path} ({request.method}): {exc}")
    return error_response(status.HTTP_404_NOT_FOUND, str(exc), exc.code, exc.details)


@app.exception_handler(ControllerBadRequestError)
async def controller_bad_request_error_handler(request: Request, exc: ControllerBadRequestError):
    log.error(f"Controller bad request error in {request.url.path} ({request.method}): {exc}")
    return error_response(status.HTTP_400_BAD_REQUEST, str(exc), exc.code, exc.details)


@app.exception_handler(ComputeConflictError)
async def compute_conflict_error_handler(request: Request, exc: ComputeConflictError):
    log.error(f"Controller received error from compute for request '{exc.url()}': {exc}")
    return error_response(status.HTTP_409_CONFLICT, str(exc), exc.code, exc.details)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return error_response(exc.status_code, exc.detail, headers=exc.headers)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    log.error(f"Controller database error in {request.url.path} ({request.method}): {exc}")
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Database error detected, please check logs to find details",
        "database_error",
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    log.error(f"Request validation error in {request.url.path} ({request.method}): {exc}")
    errors = [
        {"loc": list(error.get("loc", ())), "msg": error.get("msg"), "type": error.get("type")}
        for error in exc.errors()
    ]
    return error_response(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc), "validation_error", {"errors": errors})
