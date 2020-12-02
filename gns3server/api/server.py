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

from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from gns3server.controller.controller_error import (
    ControllerError,
    ControllerNotFoundError,
    ControllerBadRequestError,
    ControllerTimeoutError,
    ControllerForbiddenError,
    ControllerUnauthorizedError
)

from gns3server.api.routes import controller, index
from gns3server.api.routes.compute import compute_api
from gns3server.core import tasks
from gns3server.version import __version__

import logging
log = logging.getLogger(__name__)


app = FastAPI(title="GNS3 controller API",
              description="This page describes the public controller API for GNS3",
              version="v3")

origins = [
    "http://127.0.0.1",
    "http://localhost",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:3080",
    "http://localhost:3080",
    "http://gns3.github.io",
    "https://gns3.github.io"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_event_handler("startup", tasks.create_startup_handler(app))
app.add_event_handler("shutdown", tasks.create_shutdown_handler(app))
app.include_router(index.router, tags=["Index"])
app.include_router(controller.router, prefix="/v3")
app.mount("/v3/compute", compute_api)


@app.exception_handler(ControllerError)
async def controller_error_handler(request: Request, exc: ControllerError):
    log.error(f"Controller error: {exc}")
    return JSONResponse(
        status_code=409,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerTimeoutError)
async def controller_timeout_error_handler(request: Request, exc: ControllerTimeoutError):
    log.error(f"Controller timeout error: {exc}")
    return JSONResponse(
        status_code=408,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerUnauthorizedError)
async def controller_unauthorized_error_handler(request: Request, exc: ControllerUnauthorizedError):
    log.error(f"Controller unauthorized error: {exc}")
    return JSONResponse(
        status_code=401,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerForbiddenError)
async def controller_forbidden_error_handler(request: Request, exc: ControllerForbiddenError):
    log.error(f"Controller forbidden error: {exc}")
    return JSONResponse(
        status_code=403,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerNotFoundError)
async def controller_not_found_error_handler(request: Request, exc: ControllerNotFoundError):
    log.error(f"Controller not found error: {exc}")
    return JSONResponse(
        status_code=404,
        content={"message": str(exc)},
    )


@app.exception_handler(ControllerBadRequestError)
async def controller_bad_request_error_handler(request: Request, exc: ControllerBadRequestError):
    log.error(f"Controller bad request error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"message": str(exc)},
    )


# make sure the content key is "message", not "detail" per default
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )


@app.middleware("http")
async def add_extra_headers(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-GNS3-Server-Version"] = "{}".format(__version__)
    return response
