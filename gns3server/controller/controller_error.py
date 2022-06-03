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


class ControllerError(Exception):
    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def __repr__(self):
        return self._message

    def __str__(self):
        return self._message


class ControllerNotFoundError(ControllerError):
    def __init__(self, message: str):
        super().__init__(message)


class ControllerBadRequestError(ControllerError):
    def __init__(self, message: str):
        super().__init__(message)


class ControllerUnauthorizedError(ControllerError):
    def __init__(self, message: str):
        super().__init__(message)


class ControllerForbiddenError(ControllerError):
    def __init__(self, message: str):
        super().__init__(message)


class ControllerTimeoutError(ControllerError):
    def __init__(self, message: str):
        super().__init__(message)


class ComputeError(ControllerError):
    pass


class ComputeConflictError(ComputeError):
    """
    Raise when the compute sends a 409 that we can handle

    :param request URL: compute URL used for the request
    :param response: compute JSON response
    """

    def __init__(self, url, response):
        super().__init__(response["message"])
        self._url = url
        self._response = response

    def url(self):
        return self._url

    def response(self):
        return self._response
