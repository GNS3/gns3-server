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

import time

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from uvicorn.main import Server as UvicornServer

from gns3server.controller.controller_error import (
    ControllerError,
    ControllerNotFoundError,
    ControllerBadRequestError,
    ControllerTimeoutError,
    ControllerForbiddenError,
    ControllerUnauthorizedError,
    ComputeConflictError
)

from gns3server.api.routes import controller, index
from gns3server.api.routes.compute import compute_api
from gns3server.core import tasks
from gns3server.version import __version__

import logging

log = logging.getLogger(__name__)


def get_application() -> FastAPI:

    application = FastAPI(
        title="GNS3 controller API", description="This page describes the public controller API for GNS3", version="v3"
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http(s)?://(localhost|127.0.0.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.add_event_handler("startup", tasks.create_startup_handler(application))
    application.add_event_handler("shutdown", tasks.create_shutdown_handler(application))
    application.include_router(index.router, tags=["Index"])
    application.include_router(controller.router, prefix="/v3")
    application.mount("/v3/compute", compute_api, name="compute")

    return application


app = get_application()

# Monkey Patch uvicorn signal handler to detect the application is shutting down
app.state.exiting = False
unicorn_exit_handler = UvicornServer.handle_exit


def handle_exit(*args, **kwargs):
    app.state.exiting = True
    unicorn_exit_handler(*args, **kwargs)


UvicornServer.handle_exit = handle_exit


@app.exception_handler(ControllerError)
async def controller_error_handler(request: Request, exc: ControllerError):
    log.error(f"Controller error in {request.url.path} ({request.method}): {exc}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerTimeoutError)
async def controller_timeout_error_handler(request: Request, exc: ControllerTimeoutError):
    log.error(f"Controller timeout error in {request.url.path} ({request.method}): {exc}")
    return JSONResponse(
        status_code=status.HTTP_408_REQUEST_TIMEOUT,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerUnauthorizedError)
async def controller_unauthorized_error_handler(request: Request, exc: ControllerUnauthorizedError):
    log.error(f"Controller unauthorized error in {request.url.path} ({request.method}): {exc}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerForbiddenError)
async def controller_forbidden_error_handler(request: Request, exc: ControllerForbiddenError):
    log.error(f"Controller forbidden error in {request.url.path} ({request.method}): {exc}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerNotFoundError)
async def controller_not_found_error_handler(request: Request, exc: ControllerNotFoundError):
    log.error(f"Controller not found error in {request.url.path} ({request.method}): {exc}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerBadRequestError)
async def controller_bad_request_error_handler(request: Request, exc: ControllerBadRequestError):
    log.error(f"Controller bad request error in {request.url.path} ({request.method}): {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": str(exc)},
    )


@app.exception_handler(ComputeConflictError)
async def compute_conflict_error_handler(request: Request, exc: ComputeConflictError):
    log.error(f"Controller received error from compute for request '{exc.url()}': {exc}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": str(exc)},
    )


# make sure the content key is "message", not "detail" per default
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
        headers=exc.headers
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemry_error_handler(request: Request, exc: SQLAlchemyError):
    log.error(f"Controller database error in {request.url.path} ({request.method}): {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Database error detected, please check logs to find details"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    log.error(f"Request validation error in {request.url.path} ({request.method}): {exc}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"message": str(exc)}
    )

# FIXME: do not use this middleware since it creates issue when using StreamingResponse
# see https://starlette-context.readthedocs.io/en/latest/middleware.html#why-are-there-two-middlewares-that-do-the-same-thing

# @app.middleware("http")
# async def add_extra_headers(request: Request, call_next):
#     start_time = time.time()
#     response = await call_next(request)
#     process_time = time.time() - start_time
#     response.headers["X-Process-Time"] = str(process_time)
#     response.headers["X-GNS3-Server-Version"] = f"{__version__}"
#     return response
