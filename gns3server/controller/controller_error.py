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

from typing import Any


class ControllerError(Exception):
    default_code = "conflict"

    def __init__(self, message: str, code: str | None = None, details: dict[str, Any] | None = None):
        super().__init__()
        self._message = message
        self._code = code or self.default_code
        self._details = details

    def __repr__(self):
        return self._message

    def __str__(self):
        return self._message

    @property
    def code(self) -> str:
        return self._code

    @property
    def details(self) -> dict[str, Any] | None:
        return self._details


class ControllerNotFoundError(ControllerError):
    default_code = "not_found"


class ControllerBadRequestError(ControllerError):
    default_code = "bad_request"


class ControllerUnauthorizedError(ControllerError):
    default_code = "unauthorized"


class ControllerForbiddenError(ControllerError):
    default_code = "forbidden"


class ControllerTimeoutError(ControllerError):
    default_code = "timeout"


class ComputeError(ControllerError):
    pass


class ComputeConflictError(ComputeError):
    """
    Raise when the compute sends a 409 that we can handle

    :param request URL: compute URL used for the request
    :param response: compute JSON response
    """

    default_code = "compute_conflict"

    def __init__(self, url, response):
        super().__init__(response["message"], code=response.get("code"), details=response.get("details"))
        self._url = url
        self._response = response

    def url(self):
        return self._url

    def response(self):
        return self._response


def controller_error_status_code(error: ControllerError) -> int:
    """
    HTTP status code returned by the API for a controller error.
    """

    if isinstance(error, ControllerTimeoutError):
        return 408
    if isinstance(error, ControllerUnauthorizedError):
        return 401
    if isinstance(error, ControllerForbiddenError):
        return 403
    if isinstance(error, ControllerNotFoundError):
        return 404
    if isinstance(error, ControllerBadRequestError):
        return 400
    return 409
