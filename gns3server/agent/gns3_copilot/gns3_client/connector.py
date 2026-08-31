# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# This file is part of GNS3-Copilot project.
#
# GNS3-Copilot is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# GNS3-Copilot is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
GNS3 REST API connector.

A minimal authenticated HTTP session for the GNS3 controller API: URL/base
URL handling, v2 basic / v3 JWT authentication and token refresh, plus GNS3
error extraction. Callers make requests through ``http_call`` — the
endpoint-specific logic lives in ``api_handlers``.

The class is adapted from the upstream gns3fy project
(https://github.com/davidban77/gns3fy) Gns3Connector.

⚠️ WARNING: This module is shared with the MCP (Model Context Protocol)
service. Modifications must be tested with BOTH gns3-copilot AND MCP.
"""

import time
from typing import Any

import jwt
import requests
import urllib3
from requests import HTTPError


class Gns3Connector:
    """
    Connector to be used for interaction against the GNS3 server controller API.

    **Attributes:**

    - `url` (str): URL of the GNS3 server (**required**)
    - `user` (str): User used for authentication
    - `cred` (str): Password used for authentication
    - `jwt_token` (str): JWT token for direct authentication (API v3)
    - `verify` (bool): Whether or not to verify SSL
    - `api_version` (int): GNS3 server REST API version
    - `api_calls`: Counter of amount of `http_calls` has been performed
    - `base_url`: url passed + api_version
    - `session`: Requests Session object

    **Returns:**

    `Gns3Connector` instance

    **Example:**

    ```python
    >>> # API v2 with basic auth
    >>> server = Gns3Connector(
    ...     url="http://<address>:3080", user="admin", cred="password",
    ...     api_version=2
    ... )
    >>> # API v3 with username/password (auto-fetches JWT token)
    >>> server = Gns3Connector(
    ...     url="http://<address>:3080", user="admin", cred="password",
    ...     api_version=3
    ... )
    >>> # API v3 with direct JWT token
    >>> server = Gns3Connector(
    ...     url="http://<address>:3080",
    ...     jwt_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    ...     api_version=3
    ... )
    >>> print(server.http_call("get", f"{server.base_url}/version").json())
    {'local': False, 'version': '2.2.0b4'}
    ```
    """

    access_token: str | None
    token_expiry: float | None

    def __init__(
        self,
        url: str | None = None,
        user: str | None = None,
        cred: str | None = None,
        jwt_token: str | None = None,
        verify: bool = False,
        api_version: int = 2,
    ) -> None:
        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if url is None:
            raise ValueError("URL is required for Gns3Connector")
        self.url = url.strip("/")  # Store original URL for reference
        self.base_url = f"{self.url}/v{api_version}"
        self.user = user
        self.cred = cred
        self.headers = {"Content-Type": "application/json"}
        self.verify = verify
        self.api_calls = 0

        # v3 authentication attributes
        # If jwt_token is provided directly, use it; otherwise will be
        # fetched via username/password
        self.access_token = jwt_token
        self.token_expiry = None
        self.auth_type = "basic" if api_version == 2 else "jwt"
        self.api_version = api_version

        # Create session object
        self._create_session()

    def _create_session(self) -> None:
        """
        Creates the requests.Session object and applies the necessary parameters
        """
        self.session = requests.Session()  # pragma: no cover
        # Increase connection pool size to support concurrent MCP batch operations
        adapter = requests.adapters.HTTPAdapter(pool_connections=500, pool_maxsize=1000)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers["Accept"] = "application/json"  # pragma: no cover

        # Set authentication based on API version
        if (
            self.auth_type == "basic"
            and self.user is not None
            and self.cred is not None
        ):
            self.session.auth = (self.user, self.cred)  # pragma: no cover

        elif self.auth_type == "jwt" and self.access_token:
            self.session.headers["Authorization"] = (
                f"Bearer {self.access_token}"
            )

    def _authenticate_v3(self) -> None:
        """
        Performs v3 API authentication using username and password to get JWT token.
        Skips authentication if a JWT token is already provided.
        """
        # If token is already provided, skip authentication
        if self.access_token:
            return

        if not self.user or not self.cred:
            raise ValueError(
                "Username and password are required for v3 authentication "
                "when no JWT token is provided"
            )

        # Construct authentication URL (v3 API uses different base URL)
        auth_url = (
            f"{self.base_url.replace('/v3', '')}/v3/access/users/authenticate"
        )
        auth_data = {"username": self.user, "password": self.cred}

        # Use temporary session for authentication
        temp_session = requests.Session()
        temp_session.headers["Content-Type"] = "application/json"

        try:
            response = temp_session.post(
                auth_url, json=auth_data, verify=self.verify, timeout=10.0
            )
            if response.status_code == 200:
                auth_result = response.json()
                self.access_token = auth_result["access_token"]
                # Update session with new token
                self.session.headers["Authorization"] = (
                    f"Bearer {self.access_token}"
                )
            else:
                raise HTTPError(
                    f"v3 API authentication failed: {response.status_code} - "
                    f"{response.text}"
                )
        except Exception as e:
            raise HTTPError(f"v3 API authentication error: {str(e)}") from e

    def _is_token_expired(self) -> bool:
        """
        Check if the JWT token is expired (basic implementation)
        """
        token = self.access_token
        if not token:
            return True

        try:
            # Decode token without verification to check expiry
            decoded: dict[str, Any] = jwt.decode(
                token, options={"verify_signature": False}
            )
            exp = decoded.get("exp")
            if exp is not None:
                return time.time() > float(exp)
            return False
        except (jwt.PyJWTError, ValueError, TypeError):
            return True

    def _refresh_token(self) -> None:
        """
        Refresh the JWT token (for now, just re-authenticate)
        """
        print("Refreshing v3 API token...")
        self._authenticate_v3()

    def http_call(
        self,
        method: str,
        url: str,
        data: Any | None = None,
        json_data: dict[str, Any] | list[Any] | None = None,
        headers: dict[str, str] | None = None,
        verify: bool = False,
        params: dict[str, Any] | None = None,
    ) -> requests.Response:
        """
        Executes HTTP operations and handles GNS3-specific error logic.
        """

        # Handle JWT authentication
        if (
            self.auth_type == "jwt"
            and not self.access_token
            and self.user
            and self.cred
        ):
            self._authenticate_v3()

        # Get request function (e.g., session.get, session.post)
        caller = getattr(self.session, method.lower())

        # Prepare request parameters, avoiding multiple repeated calls to caller
        kwargs: dict[str, Any] = {
            "headers": headers,
            "params": params,
            "verify": verify,
            "timeout": 30.0,  # Main request timeout (auth call uses 10s)
        }
        if data is not None:
            kwargs["data"] = data
        elif json_data is not None:
            kwargs["json"] = json_data

        # Execute request
        _response: requests.Response = caller(url, **kwargs)

        self.api_calls += 1

        try:
            _response.raise_for_status()
        except HTTPError as e:
            # Throw enhanced error
            raise self._extract_gns3_error(e) from e

        return _response

    def _extract_gns3_error(self, e: HTTPError) -> HTTPError:
        """
        Extract GNS3-specific JSON error information from HTTPError.
        If parsing fails, return the original error.
        """
        # e.response might be None, need explicit check
        response = e.response
        if response is None:
            return e

        try:
            # Only attempt parsing when Content-Type is JSON
            if (
                "application/json"
                in response.headers.get("Content-Type", "").lower()
            ):
                error_json = response.json()
                status = error_json.get("status", "Unknown Status")
                message = error_json.get(
                    "message", "No message provided in JSON."
                )
                # Construct a more descriptive new error
                new_err = HTTPError(
                    f"{status}: {message} (Original {response.status_code} Error)",
                    response=response,
                )
                return new_err
        except Exception:
            # If JSON parsing fails, return error with original text
            return HTTPError(
                f"Original Error: {str(e)}. GNS3 response text: {response.text}",
                response=response,
            )
        return e
