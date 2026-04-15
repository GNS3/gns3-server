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
Adapted gns3fy module for GNS3-Copilot

This module is based on the upstream gns3fy project
(https://github.com/davidban77/gns3fy).

Modifications made for GNS3-Copilot:
- Adjusted pydantic usages and dataclass configuration to reduce dependency
  conflicts with langchain (pydantic version/api differences)
- Kept the original API surface where possible but simplified
  validators/config
- Added JWT token authentication support
- Integrated with context-aware connector factory

Note: This file is adapted from upstream gns3fy for compatibility with
GNS3-Copilot's architecture.

Upstream: https://github.com/davidban77/gns3fy
"""

import os
import time
from collections.abc import Callable
from dataclasses import field
from functools import wraps
from math import cos
from math import pi
from math import sin
from typing import Any
from typing import ParamSpec
from typing import TypeVar
from typing import cast
from urllib.parse import urlparse

import jwt
import requests
import urllib3
from pydantic import ConfigDict
from pydantic import field_validator
from pydantic.dataclasses import dataclass
from requests import HTTPError

P = ParamSpec("P")
R = TypeVar("R")
F = TypeVar("F", bound=Callable[..., Any])

config = ConfigDict(validate_assignment=True, extra="ignore")

NODE_TYPES = [
    "cloud",
    "nat",
    "ethernet_hub",
    "ethernet_switch",
    "frame_relay_switch",
    "atm_switch",
    "docker",
    "dynamips",
    "vpcs",
    "traceng",
    "virtualbox",
    "vmware",
    "iou",
    "qemu",
]

CONSOLE_TYPES = [
    "vnc",
    "telnet",
    "http",
    "https",
    "spice",
    "spice+agent",
    "none",
    "null",
]

LINK_TYPES = ["ethernet", "serial"]


class Gns3Connector:
    """
    Connector to be use for interaction against GNS3 server controller API.

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
    >>> print(server.get_version())
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
                # print(f"Successfully authenticated to v3 API, token obtained")
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
            "timeout": 10.0,  # Fixed 10-second timeout for all GNS3 API requests
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

    def get_version(self) -> dict[str, Any]:
        """
        Returns the version information of GNS3 server
        """
        response = self.http_call("get", url=f"{self.base_url}/version")
        return cast(dict[str, Any], response.json())

    def projects_summary(
        self, is_print: bool = True
    ) -> list[tuple[str, str, int, int, str]] | None:
        """
        Returns a summary of the projects in the server. If `is_print` is `False`, it
        will return a list of tuples like:

        `[(name, project_id, total_nodes, total_links, status) ...]`
        """
        _projects_summary = []
        for _p in self.get_projects():
            # Retrieve the project stats
            _stats = self.http_call(
                "get", f"{self.base_url}/projects/{_p['project_id']}/stats"
            ).json()
            if is_print:
                print(
                    f"{_p['name']}: {_p['project_id']} -- Nodes: {_stats['nodes']} -- "
                    f"Links: {_stats['links']} -- Status: {_p['status']}"
                )
            _projects_summary.append(
                (
                    _p["name"],
                    _p["project_id"],
                    _stats["nodes"],
                    _stats["links"],
                    _p["status"],
                )
            )

        return _projects_summary if not is_print else None

    def get_projects(self) -> list[dict[str, Any]]:
        """
        Returns the list of the projects on the server
        """
        response = self.http_call(
            "get", url=f"{self.base_url}/projects"
        ).json()
        return cast(list[dict[str, Any]], response)

    def get_project(
        self, name: str | None = None, project_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Retrieves a project from either a name or ID

        **Required Attributes:**

        - `name` or `project_id`
        """
        if project_id:
            _response = self.http_call(
                "get", url=f"{self.base_url}/projects/{project_id}"
            )
            return cast(dict[str, Any], _response.json())
        elif name:
            try:
                return next(
                    p for p in self.get_projects() if p["name"] == name
                )
            except StopIteration:
                # Project not found
                return None
        else:
            raise ValueError("Must provide either a name or project_id")

    def templates_summary(
        self, is_print: bool = True
    ) -> list[tuple[str, str, str, bool, str, str]] | None:
        """
        Returns a summary of the templates in the server. If `is_print` is `False`, it
        will return a list of tuples like:

        `[(name, template_id, template_type, builtin, console_type, category) ...]`
        """
        _templates_summary = []
        for _t in self.get_templates():
            if "console_type" not in _t:
                _t["console_type"] = "N/A"
            if is_print:
                print(
                    f"{_t['name']}: {_t['template_id']} -- Type: {_t['template_type']}"
                    f" -- Builtin: {_t['builtin']} -- Console: {_t['console_type']} -- "
                    f"Category: {_t['category']}"
                )
            _templates_summary.append(
                (
                    _t["name"],
                    _t["template_id"],
                    _t["template_type"],
                    _t["builtin"],
                    _t["console_type"],
                    _t["category"],
                )
            )

        return _templates_summary if not is_print else None

    def get_templates(self) -> list[dict[str, Any]]:
        """
        Returns the templates defined on the server.
        """
        _response_data = self.http_call(
            "get", url=f"{self.base_url}/templates"
        ).json()
        return cast(list[dict[str, Any]], _response_data)

    def get_template(
        self, name: str | None = None, template_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Retrieves a template from either a name or ID

        **Required Attributes:**

        - `name` or `template_id`
        """
        if template_id:
            _response_json = self.http_call(
                "get", url=f"{self.base_url}/templates/{template_id}"
            ).json()
            return cast(dict[str, Any], _response_json)
        elif name:
            try:
                return next(
                    t for t in self.get_templates() if t["name"] == name
                )
            except StopIteration:
                # Template name not found
                return None
        else:
            raise ValueError("Must provide either a name or template_id")

    def update_template(
        self,
        name: str | None = None,
        template_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Updates a template by giving its name or UUID. For more information [API INFO]
        (http://api.gns3.net/en/2.2/api/v2/controller/template/
        templatestemplateid.html#put-v2-templates-template-id)

        **Required Attributes:**

        - `name` or `template_id`

        **Optional Attributes (can be passed via kwargs):**

        - `tags` (list): List of tags for the template (e.g.,
          ["device_type:cisco_ios_telnet", "platform:cisco_ios"])
        - Any other template attributes supported by GNS3 API
        """
        # Get existing template
        _template = self.get_template(name=name, template_id=template_id)
        # Type check: handle case where get_template might return None
        if _template is None:
            raise ValueError(
                f"Template not found (name={name}, id={template_id})"
            )
        # Update local dictionary and send request
        _template.update(**kwargs)

        response = self.http_call(
            "put",
            url=f"{self.base_url}/templates/{_template['template_id']}",
            json_data=_template,
        )
        # Return JSON and handle Any type errors
        return cast(dict[str, Any], response.json())

    def create_template(self, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a template by giving its attributes. For more information [API INFO]
        (http://api.gns3.net/en/2.2/api/v2/controller/template/
        templates.html#post-v2-templates)

        **Required Attributes:**

        - `name`
        - `compute_id` by default is 'local'
        - `template_type`

        **Optional Attributes (can be passed via kwargs):**

        - `tags` (list): List of tags for the template (e.g.,
          ["device_type:cisco_ios_telnet", "platform:cisco_ios"])
        - Any other template attributes supported by GNS3 API

        **Example:**

        ```python
        >>> connector.create_template(
        ...     name="cisco_router",
        ...     template_type="dynamips",
        ...     tags=["device_type:cisco_ios_telnet", "platform:cisco_ios"]
        ... )
        ```
        """
        # kwargs["name"] might raise KeyError at runtime, for more robust
        # code we can use get first
        template_name = kwargs.get("name")
        if not template_name:
            raise ValueError(
                "Attribute 'name' is required to create a template"
            )

        # Check if template already exists
        _template = self.get_template(name=kwargs["name"])
        if _template:
            raise ValueError(f"Template already used: {kwargs['name']}")

        # Set default values
        if "compute_id" not in kwargs:
            kwargs["compute_id"] = "local"

        # Send request
        response = self.http_call(
            "post", url=f"{self.base_url}/templates", json_data=kwargs
        )
        # Return and convert type
        return cast(dict[str, Any], response.json())

    def delete_template(
        self, name: str | None = None, template_id: str | None = None
    ) -> None:
        """
        Deletes a template by giving its attributes. For more information [API INFO]
        (http://api.gns3.net/en/2.2/api/v2/controller/template/
        templatestemplateid.html#id16)

        **Required Attributes:**

        - `name` or `template_id`
        """
        # Logic handling: if only name is given, need to first get template_id
        if name and not template_id:
            _template = self.get_template(name=name)
            # Type narrowing: check if _template is None
            if _template is None:
                raise ValueError(f"Template with name '{name}' not found.")

            template_id = _template["template_id"]

        # Final check: ensure template_id has a value at this point
        if not template_id:
            raise ValueError(
                "Must provide either a 'name' or 'template_id' to delete a template."
            )

        self.http_call(
            "delete", url=f"{self.base_url}/templates/{template_id}"
        )

    def get_nodes(self, project_id: str) -> list[dict[str, Any]]:
        """
        Retieves the nodes defined on the project

        **Required Attributes:**

        - `project_id`
        """
        _response_data = self.http_call(
            "get", url=f"{self.base_url}/projects/{project_id}/nodes"
        ).json()

        return cast(list[dict[str, Any]], _response_data)

    def get_node(self, project_id: str, node_id: str) -> dict[str, Any]:
        """
        Returns the node by locating its ID.

        **Required Attributes:**

        - `project_id`
        - `node_id`
        """
        _url = f"{self.base_url}/projects/{project_id}/nodes/{node_id}"
        _response_data = self.http_call("get", _url).json()
        return cast(dict[str, Any], _response_data)

    def get_links(self, project_id: str) -> list[dict[str, Any]]:
        """
        Retrieves the links defined in the project.

        **Required Attributes:**

        - `project_id`
        """
        _response_data = self.http_call(
            "get", url=f"{self.base_url}/projects/{project_id}/links"
        ).json()

        return cast(list[dict[str, Any]], _response_data)

    def get_link(self, project_id: str, link_id: str) -> dict[str, Any]:
        """
        Returns the link by locating its ID.

        **Required Attributes:**

        - `project_id`
        - `link_id`
        """
        _url = f"{self.base_url}/projects/{project_id}/links/{link_id}"
        _response_data = self.http_call("get", _url).json()

        return cast(dict[str, Any], _response_data)

    def create_project(self, **kwargs: Any) -> dict[str, Any]:
        """
        Pass a dictionary type object with the project parameters to be created.

        **Required Attributes:**

        - `name`

        **Returns**

        JSON project information
        """
        _url = f"{self.base_url}/projects"
        if "name" not in kwargs:
            raise ValueError("Parameter 'name' is mandatory")
        _response = self.http_call("post", _url, json_data=kwargs)

        return cast(dict[str, Any], _response.json())

    def delete_project(self, project_id: str) -> None:
        """
        Deletes a project from server.

        **Required Attributes:**

        - `project_id`
        """
        _url = f"{self.base_url}/projects/{project_id}"
        self.http_call("delete", _url)
        return None

    def get_computes(self) -> list[dict[str, Any]]:
        """
        Returns a list of computes.

        **Returns:**

        List of dictionaries of the computes attributes like cpu/memory usage
        """
        _url = f"{self.base_url}/computes"
        _response_data = self.http_call("get", _url).json()

        return cast(list[dict[str, Any]], _response_data)

    def get_compute(self, compute_id: str = "local") -> dict[str, Any]:
        """
        Returns a compute.

        **Returns:**

        Dictionary of the compute attributes like cpu/memory usage
        """
        _url = f"{self.base_url}/computes/{compute_id}"
        _response_data = self.http_call("get", _url).json()

        return cast(dict[str, Any], _response_data)

    def get_compute_images(
        self, emulator: str, compute_id: str = "local"
    ) -> list[dict[str, Any]]:
        """
        Returns a list of images available for a compute.

        **Required Attributes:**

        - `emulator`: the likes of 'qemu', 'iou', 'docker' ...
        - `compute_id` By default is 'local'

        **Returns:**

        List of dictionaries with images available for the compute for the specified
        emulator
        """
        _url = f"{self.base_url}/computes/{compute_id}/{emulator}/images"
        _response_data = self.http_call("get", _url).json()

        return cast(list[dict[str, Any]], _response_data)

    def upload_compute_image(
        self, emulator: str, file_path: str, compute_id: str = "local"
    ) -> None:
        """
        uploads an image for use by a compute.

        **Required Attributes:**

        - `emulator`: the likes of 'qemu', 'iou', 'docker' ...
        - `file_path`: path of file to be uploaded
        - `compute_id` By default is 'local'
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Could not find file: {file_path}")

        _filename = os.path.basename(file_path)
        _url = f"{self.base_url}/computes/{compute_id}/{emulator}/images/{_filename}"
        with open(file_path, "rb") as f:
            self.http_call("post", _url, data=f)

        return None

    def get_compute_ports(self, compute_id: str = "local") -> dict[str, Any]:
        """
        Returns ports used and configured by a compute.

        **Required Attributes:**

        - `compute_id` By default is 'local'

        **Returns:**

        Dictionary of `console_ports` used and range, as well as the `udp_ports`
        """
        _url = f"{self.base_url}/computes/{compute_id}/ports"
        _response_data = self.http_call("get", _url).json()

        return cast(dict[str, Any], _response_data)


def verify_connector_and_id(f: F) -> F:
    """
    Main checker for connector object and respective object's ID for their retrieval
    or actions methods.
    """

    @wraps(f)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        _conn = self.connector
        _project_id = self.project_id

        if _conn is None:
            raise ValueError("Gns3Connector not assigned under 'connector'")
        if _project_id is None:
            raise ValueError("Need to submit project_id")

        # Checks for Node
        if self.__class__.__name__ == "Node":
            if not self.node_id:
                if not self.name:
                    raise ValueError("Need to either submit node_id or name")

                # Try to retrieve the node_id
                _url = f"{_conn.base_url}/projects/{_project_id}/nodes"
                _response = _conn.http_call("get", _url)

                extracted = [
                    node
                    for node in _response.json()
                    if node["name"] == self.name
                ]
                if len(extracted) > 1:  # pragma: no cover
                    raise ValueError(
                        "Multiple nodes found with same name. Need to submit node_id"
                    )
                self.node_id = extracted[0]["node_id"]
        # Checks for Link
        if self.__class__.__name__ == "Link":
            if not self.link_id:
                raise ValueError("Need to submit link_id")
        return f(self, *args, **kwargs)

    return cast(F, wrapper)


@dataclass(config=config)
class Link:
    """
    GNS3 Link API object. For more information visit: [Links Endpoint API information](
    http://api.gns3.net/en/2.2/api/v2/controller/link/projectsprojectidlinks.html)

    **Attributes:**

    - `link_id` (str): Link UUID (**required** to be set when using `get` method)
    - `link_type` (enum): Possible values: ethernet, serial
    - `link_style` (dict): Describes the visual style of the link
    - `project_id` (str): Project UUID (**required**)
    - `connector` (object): `Gns3Connector` instance used for interaction (**required**)
    - `suspend` (bool): Suspend the link
    - `nodes` (list): List of the Nodes and ports (**required** when using `create`
    method, see Features/Link creation on the docs)
    - `filters` (dict): Packet filter. This allow to simulate latency and errors
    - `capturing` (bool): Read only property. True if a capture running on the link
    - `capture_file_path` (str): Read only property. The full path of the capture file
    if capture is running
    - `capture_file_name` (str): Read only property. The name of the capture file if
    capture is running

    **Returns:**

    `Link` instance

    **Example:**

    ```python
    >>> link = Link(project_id=<pr_id>, link_id=<link_id> connector=<Gns3Connector
    instance>)
    >>> link.get()
    >>> print(link.link_type)
    'ethernet'
    ```
    """

    link_id: str | None = None
    link_type: str | None = None
    link_style: Any | None = None
    project_id: str | None = None
    suspend: bool | None = None
    nodes: list[Any] | None = None
    filters: dict | None = None
    capturing: bool | None = None
    capture_file_path: str | None = None
    capture_file_name: str | None = None
    capture_compute_id: str | None = None

    connector: Any | None = field(default=None, repr=False)

    @field_validator("link_type")
    @classmethod
    def _valid_link_type(cls, value: str | None) -> str | None:
        if value not in LINK_TYPES and value is not None:
            raise ValueError(f"Not a valid link_type - {value}")
        return value

    @field_validator("suspend")
    @classmethod
    def _valid_suspend(cls, value: bool | None) -> bool | None:
        if type(value) is not bool and value is not None:
            raise ValueError(f"Not a valid suspend - {value}")
        return value

    @field_validator("filters")
    @classmethod
    def _valid_filters(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if type(value) is not dict and value is not None:
            raise ValueError(f"Not a valid filters - {value}")
        return value

    def _update(self, data_dict: dict[str, Any]) -> None:
        for k, v in data_dict.items():
            if k in self.__dict__.keys():
                self.__setattr__(k, v)

    @verify_connector_and_id
    def get(self) -> None:
        """
        Retrieves the information from the link endpoint.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `link_id`
        """
        _conn = self.connector
        _project_id = self.project_id

        if _conn is None:
            raise ValueError("Gns3Connector not assigned under 'connector'")
        if _project_id is None:
            raise ValueError("Need to submit project_id")

        _url = f"{_conn.base_url}/projects/{_project_id}/links/{self.link_id}"
        _response = _conn.http_call("get", _url)

        # Update object
        self._update(_response.json())

    @verify_connector_and_id
    def delete(self) -> None:
        """
        Deletes a link endpoint from the project. It sets to `None` the attributes
        `link_id` when executed sucessfully

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `link_id`
        """
        _conn = self.connector
        _project_id = self.project_id
        _link_id = self.link_id

        if _conn is None:
            raise ValueError("Gns3Connector not assigned under 'connector'")
        if _project_id is None:
            raise ValueError("Need to submit project_id")
        if _link_id is None:
            raise ValueError(
                "Link ID is missing. The link might have already been deleted."
            )

        _url = f"{_conn.base_url}/projects/{_project_id}/links/{self.link_id}"

        _conn.http_call("delete", _url)

        self.project_id = None
        self.link_id = None

    def create(self) -> None:
        """
        Creates a link endpoint

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `nodes`
        """
        if not self.connector:
            raise ValueError("Gns3Connector not assigned under 'connector'")
        if not self.project_id:
            raise ValueError("Need to submit project_id")

        _url = f"{self.connector.base_url}/projects/{self.project_id}/links"

        data = {
            k: v
            for k, v in self.__dict__.items()
            if k not in ("connector", "__initialised__")
            if v is not None
        }

        _response = self.connector.http_call("post", _url, json_data=data)

        # Now update it
        self._update(_response.json())

    @verify_connector_and_id
    def update(self, **kwargs: Any) -> None:
        """
        Updates the link instance by passing the keyword arguments of the attributes
        you want updated

        Example:

        ```python
        link1.update(suspend=True)
        ```

        This will update the link `suspend` attribute to `True`

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `link_id`
        """
        if not self.connector:
            raise ValueError("Gns3Connector not assigned under 'connector'")
        if not self.project_id:
            raise ValueError("Need to submit project_id")

        _url = (
            f"{self.connector.base_url}/projects/{self.project_id}/links/"
            f"{self.link_id}"
        )

        # TODO: Verify that the passed kwargs are supported ones
        _response = self.connector.http_call("put", _url, json_data=kwargs)

        # Update object
        self._update(_response.json())


@dataclass(config=config)
class Node:
    """
    GNS3 Node API object. For more information visit: [Node Endpoint API information](
    http://api.gns3.net/en/2.2/api/v2/controller/node/projectsprojectidnodes.html)

    **Attributes:**

    - `name` (str): Node name (**required** when using `create` method)
    - `project_id` (str): Project UUID (**required**)
    - `node_id` (str): Node UUID (**required** when using `get` method)
    - `compute_id` (str): Compute identifier (**required**, default=local)
    - `node_type` (enum): frame_relay_switch, atm_switch, docker, dynamips, vpcs,
    traceng, virtualbox, vmware, iou, qemu (**required** when using `create` method)
    - `connector` (object): `Gns3Connector` instance used for interaction (**required**)
    - `template_id`: Template UUID from the which the node is from.
    - `template`: Template name from the which the node is from.
    - `node_directory` (str): Working directory of the node. Read only
    - `status` (enum): Possible values: stopped, started, suspended
    - `ports` (list): List of node ports, READ only
    - `port_name_format` (str): Formating for port name {0} will be replace by port
    number
    - `port_segment_size` (int): Size of the port segment
    - `first_port_name` (str): Name of the first port
    - `properties` (dict): Properties specific to an emulator
    - `locked` (bool): Whether the element locked or not
    - `label` (dict): TBC
    - `console` (int): Console TCP port
    - `console_host` (str): Console host
    - `console_auto_start` (bool): Automatically start the console when the node has
    started
    - `command_line` (str): Command line use to start the node
    - `custom_adapters` (list): TBC
    - `height` (int): Height of the node, READ only
    - `width` (int): Width of the node, READ only
    - `symbol` (str): Symbol of the node
    - `x` (int): X position of the node
    - `y` (int): Y position of the node
    - `z (int): Z position of the node

    **Returns:**

    `Node` instance

    **Example:**

    ```python
    >>> alpine = Node(name="alpine1", node_type="docker", template="alpine",
    project_id=<pr_id>, connector=<Gns3Connector instance>)
    >>> alpine.create()
    >>> print(alpine.node_id)
    'SOME-UUID-GENERATED'
    ```
    """

    name: str | None = None
    project_id: str | None = None
    node_id: str | None = None
    compute_id: str = "local"
    node_type: str | None = None
    node_directory: str | None = None
    status: str | None = None
    ports: list | None = None
    port_name_format: str | None = None
    port_segment_size: int | None = None
    first_port_name: str | None = None
    locked: bool | None = None
    label: Any | None = None
    console: int | None = None
    console_host: str | None = None
    console_type: str | None = None
    console_auto_start: bool | None = None
    command_line: str | None = None
    custom_adapters: list[Any] | None = None
    height: int | None = None
    width: int | None = None
    symbol: str | None = None
    x: int | None = None
    y: int | None = None
    z: int | None = None
    template_id: str | None = None
    properties: Any | None = None
    tags: list[str] | None = None

    template: str | None = None
    links: list[Link] = field(default_factory=list, repr=False)
    connector: Any | None = field(default=None, repr=False)

    @field_validator("node_type")
    @classmethod
    def _valid_node_type(cls, value: Any) -> Any:
        if value not in NODE_TYPES and value is not None:
            raise ValueError(f"Not a valid node_type - {value}")
        return value

    @field_validator("console_type")
    @classmethod
    def _valid_console_type(cls, value: Any) -> Any:
        if value not in CONSOLE_TYPES and value is not None:
            raise ValueError(f"Not a valid console_type - {value}")
        return value

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: Any) -> Any:
        if (
            value not in ("stopped", "started", "suspended")
            and value is not None
        ):
            raise ValueError(f"Not a valid status - {value}")
        return value

    def _update(self, data_dict: dict[str, Any]) -> None:
        for k, v in data_dict.items():
            if k in self.__dict__:
                setattr(self, k, v)

    @verify_connector_and_id
    def get(self, get_links: bool = True) -> None:
        """
        Retrieves the node information. When `get_links` is `True` it also retrieves the
        links respective to the node.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `node_id`
        """
        if not self.connector:
            raise ValueError("Gns3Connector not assigned under 'connector'")
        if not self.project_id:
            raise ValueError("Need to submit project_id")

        _url = (
            f"{self.connector.base_url}/projects/{self.project_id}/nodes/"
            f"{self.node_id}"
        )
        _response = self.connector.http_call("get", _url)

        # Update object
        self._update(_response.json())

        if get_links:
            self.get_links()

    @verify_connector_and_id
    def get_links(self) -> None:
        """
        Retrieves the links of the respective node. They will be saved at the `links`
        attribute

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `node_id`
        """
        if not self.connector:
            raise ValueError("Gns3Connector not assigned under 'connector'")
        if not self.project_id:
            raise ValueError("Need to submit project_id")

        _url = (
            f"{self.connector.base_url}/projects/{self.project_id}/nodes"
            f"/{self.node_id}/links"
        )
        _response = self.connector.http_call("get", _url)

        # Create the Link array but cleanup cache if there is one
        if self.links:
            self.links = []
        for _link in _response.json():
            self.links.append(Link(connector=self.connector, **_link))

    @verify_connector_and_id
    def start(self) -> bool | None:
        """
        Starts the node.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `node_id`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/{self.node_id}/start"
        if "v2" in _url.lower():  # api_version 2
            _response = _conn.http_call(
                "post",
                _url,
            )

            # Update object or perform get if change was not reflected
            if _response.json().get("status") == "started":
                self._update(_response.json())
            else:
                self.get()  # pragma: no cover

            return True

        else:
            # api_version 3
            _response = _conn.http_call(
                "post", _url, json_data={"additionalProp1": {}}
            )
            # successful response code 204
            if _response.status_code in (204,):
                self.get()
                return True
            else:
                try:
                    error_detail = _response.json()
                except Exception:
                    error_detail = getattr(
                        _response, "text", "No response body"
                    )

                _msg = (
                    "Failed to start node: "
                    f"{getattr(_response, 'status_code', 'Unknown Status')}, "
                    f"Detail: {error_detail}"
                )
                raise RuntimeError(_msg) from None

    @verify_connector_and_id
    def stop(self) -> bool | None:
        """
        Stops the node.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `node_id`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/{self.node_id}/stop"
        if "v2" in _url.lower():  # api_version 2
            _response = _conn.http_call(
                "post",
                _url,
            )

            # Update object or perform get if change was not reflected
            if _response.json().get("status") == "stopped":
                self._update(_response.json())
            else:
                self.get()  # pragma: no cover

            return True
        else:
            # api_version 3
            _response = _conn.http_call(
                "post", _url, json_data={"additionalProp1": {}}
            )
            # successful response code 204
            if _response.status_code in (204,):
                self.get()
                return True
            else:
                try:
                    error_detail = _response.json()
                except Exception:
                    error_detail = _response.text
                _msg = (
                    f"Failed to stop node: {_response.status_code}, "
                    f"Detail: {error_detail}"
                )
                raise RuntimeError(_msg) from None

    @verify_connector_and_id
    def reload(self) -> bool | None:
        """
        Reloads the node.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `node_id`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None
        _node_id = self.node_id
        assert _node_id is not None

        _url = (
            f"{_conn.base_url}/projects/{_project_id}/nodes/{_node_id}/reload"
        )
        _response = _conn.http_call("post", _url)

        if "v2" in _url.lower():  # api_version 2
            _response = _conn.http_call(
                "post",
                _url,
            )

            # Update object or perform get if change was not reflected
            if _response.json().get("status") == "started":
                self._update(_response.json())
            else:
                self.get()  # pragma: no cover
            return True

        else:
            # api_version 3
            _response = _conn.http_call(
                "post", _url, json_data={"additionalProp1": {}}
            )
            # successful response code 204
            if _response.status_code in (204,):
                self.get()
                return True
            else:
                try:
                    error_detail = _response.json()
                except Exception:
                    error_detail = _response.text
                _msg = (
                    f"Failed to reload node: {_response.status_code}, "
                    f"Detail: {error_detail}"
                )
                raise RuntimeError(_msg) from None

    @verify_connector_and_id
    def suspend(self) -> None:
        """
        Suspends the node.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `node_id`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None
        _node_id = self.node_id
        assert _node_id is not None

        _url = (
            f"{_conn.base_url}/projects/{_project_id}/nodes/{_node_id}/suspend"
        )
        _response = _conn.http_call("post", _url)

        # Update object or perform get if change was not reflected
        if _response.json().get("status") == "suspended":
            self._update(_response.json())
        else:
            self.get()  # pragma: no cover

    @verify_connector_and_id
    def update(self, **kwargs: Any) -> None:
        """
        Updates the node instance by passing the keyword arguments of the attributes
        you want updated

        Example:

        ```python
        router01.update(name="router01-CSX")
        ```

        This will update the project `auto_close` attribute to `True`

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None
        _node_id = self.node_id
        assert _node_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/{_node_id}"

        # TODO: Verify that the passed kwargs are supported ones
        _response = _conn.http_call("put", _url, json_data=kwargs)

        # Update object
        self._update(_response.json())

    def create(self) -> None:
        """
        Creates a node.

        By default it will fetch the nodes properties for creation based on the
        `template` or `template_id` attribute supplied. This can be overriden/updated
        by sending a dictionary of the properties under `extra_properties`.

        **Required Node instance attributes:**

        - `project_id`
        - `connector`
        - `compute_id`: Defaults to "local"
        - `template` or `template_id` - if not passed as arguments
        """
        if self.node_id:
            raise ValueError("Node already created")
        if not self.connector:
            raise ValueError("Gns3Connector not assigned under 'connector'")
        if not self.project_id:
            raise ValueError("Node object needs to have project_id attribute")
        if not self.template_id:
            if self.template:
                _template = self.connector.get_template(name=self.template)
                if _template is None:
                    raise ValueError(f"Template {self.template} not found")
                self.template_id = self.connector.get_template(
                    name=self.template
                ).get("template_id")
            else:
                raise ValueError("Need either 'template' of 'template_id'")

        cached_data = {
            k: v
            for k, v in self.__dict__.items()
            if k
            not in (
                "project_id",
                "template",
                "template_id",
                "links",
                "connector",
                "__initialised__",
            )
            if v is not None
        }

        _url = (
            f"{self.connector.base_url}/projects/{self.project_id}/"
            f"templates/{self.template_id}"
        )

        _response = self.connector.http_call(
            "post",
            _url,
            json_data={"x": 0, "y": 0, "compute_id": self.compute_id},
        )

        self._update(_response.json())

        # Update the node attributes based on cached data
        self.update(**cached_data)

    @verify_connector_and_id
    def delete(self) -> None:
        """
        Deletes the node from the project. It sets to `None` the attributes `node_id`
        and `name` when executed successfully

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `node_id`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None
        _node_id = self.node_id
        assert _node_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/{_node_id}"

        _conn.http_call("delete", _url)

        self.project_id = None
        self.node_id = None
        self.name = None

    @verify_connector_and_id
    def get_file(self, path: str) -> str:
        """
        Retrieve a file in the node directory.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `path`: Node's relative path of the file
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None
        _node_id = self.node_id
        assert _node_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/{_node_id}/files/{path}"

        return cast(str, _conn.http_call("get", _url).text)

    @verify_connector_and_id
    def write_file(self, path: str, data: Any) -> None:
        """
        Places a file content on a specified node file path. Used mainly for docker
        images.

        Example to update an alpine docker network interfaces:

        ```python
        >>> data = '''
            auto eth0
            iface eth0 inet dhcp
            '''

        >>> alpine_node.write_file(path='/etc/network/interfaces', data=data)
        ```

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `path`: Node's relative path of the file
        - `data`: Data to be included in the file
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None
        _node_id = self.node_id
        assert _node_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/{_node_id}/files/{path}"

        _conn.http_call("post", _url, data=data)


@dataclass(config=config)
class Project:
    """
    GNS3 Project API object. For more information visit: [Project Endpoint API
    information](http://api.gns3.net/en/2.2/api/v2/controller/project/projects.html)

    **Attributes:**

    - `name`: Project name (**required** when using `create` method)
    - `project_id` (str): Project UUID (**required**)
    - `connector` (object): `Gns3Connector` instance used for interaction (**required**)
    - `status` (enum): Possible values: opened, closed
    - `path` (str): Path of the project on the server
    - `filename` (str): Project filename
    - `auto_start` (bool): Project start when opened
    - `auto_close` (bool): Project auto close when client cut off the notifications feed
    - `auto_open` (bool): Project open when GNS3 start
    - `drawing_grid_size` (int): Grid size for the drawing area for drawings
    - `grid_size` (int): Grid size for the drawing area for nodes
    - `scene_height` (int): Height of the drawing area
    - `scene_width` (int): Width of the drawing area
    - `show_grid` (bool): Show the grid on the drawing area
    - `show_interface_labels` (bool): Show interface labels on the drawing area
    - `show_layers` (bool): Show layers on the drawing area
    - `snap_to_grid` (bool): Snap to grid on the drawing area
    - `supplier` (dict): Supplier of the project
    - `variables` (list): Variables required to run the project
    - `zoom` (int): Zoom of the drawing area
    - `stats` (dict): Project stats
    -.`drawings` (list): List of drawings present on the project
    - `nodes` (list): List of `Node` instances present on the project
    - `links` (list): List of `Link` instances present on the project

    **Returns:**

    `Project` instance

    **Example:**

    ```python
    >>> lab = Project(name="lab", connector=<Gns3Connector instance>)
    >>> lab.create()
    >>> print(lab.status)
    'opened'
    ```
    """

    name: str | None = None
    project_id: str | None = None
    status: str | None = None
    locked: bool | None = None
    path: str | None = None
    filename: str | None = None
    auto_start: bool | None = None
    auto_close: bool | None = None
    auto_open: bool | None = None
    drawing_grid_size: int | None = None
    grid_size: int | None = None
    scene_height: int | None = None
    scene_width: int | None = None
    show_grid: bool | None = None
    show_interface_labels: bool | None = None
    show_layers: bool | None = None
    snap_to_grid: bool | None = None
    supplier: Any | None = None
    variables: list | None = None
    zoom: int | None = None

    stats: dict[str, Any] | None = None
    snapshots: list[dict] | None = None
    drawings: list[dict] | None = None
    nodes: list[Node] = field(default_factory=list, repr=False)
    links: list[Link] = field(default_factory=list, repr=False)
    connector: Any | None = field(default=None, repr=False)

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: Any) -> Any:
        if value != "opened" and value != "closed" and value is not None:
            raise ValueError("status must be opened or closed")
        return value

    def _update(self, data_dict: dict[str, Any]) -> None:
        for k, v in data_dict.items():
            if k in self.__dict__:
                setattr(self, k, v)

    def get(
        self,
        get_links: bool = True,
        get_nodes: bool = True,
        get_stats: bool = True,
    ) -> None:
        """
        Retrieves the projects information.

        - `get_links`: When true it also queries for the links inside the project
        - `get_nodes`: When true it also queries for the nodes inside the project
        - `get_stats`: When true it also queries for the stats inside the project

        It `get_stats` is set to `True`, it also verifies if snapshots and drawings are
        inside the project and stores them in their respective attributes
        (`snapshots` and `drawings`)

        **Required Attributes:**

        - `connector`
        - `project_id` or `name`
        """
        if not self.connector:
            raise ValueError("Gns3Connector not assigned under 'connector'")

        # Get projects if no ID was provided by the name
        if not self.project_id:
            if not self.name:
                raise ValueError("Need to submit either project_id or name")
            _url = f"{self.connector.base_url}/projects"
            # Get all projects and filter the respective project
            _response = self.connector.http_call("get", _url)

            # Filter the respective project
            for _project in _response.json():
                if _project.get("name") == self.name:
                    self.project_id = _project.get("project_id")

        # Get project
        _url = f"{self.connector.base_url}/projects/{self.project_id}"
        _response = self.connector.http_call("get", _url)

        # Update object
        self._update(_response.json())

        if get_stats:
            self.get_stats()
            if self.stats is not None:
                if self.stats.get("snapshots", 0) > 0:
                    self.get_snapshots()
                if self.stats.get("drawings", 0) > 0:
                    self.get_drawings()
        if get_nodes:
            self.get_nodes()
        if get_links:
            self.get_links()

    def create(self) -> None:
        """
        Creates the project.

        **Required Attributes:**

        - `name`
        - `connector`
        """
        if not self.name:
            raise ValueError("Need to submit project name")
        if not self.connector:
            raise ValueError("Gns3Connector not assigned under 'connector'")

        _url = f"{self.connector.base_url}/projects"

        data = {
            k: v
            for k, v in self.__dict__.items()
            if k
            not in (
                "stats",
                "nodes",
                "links",
                "connector",
                "__initialised__",
            )
            if v is not None
        }

        _response = self.connector.http_call("post", _url, json_data=data)

        # Now update it
        self._update(_response.json())

    @verify_connector_and_id
    def update(self, **kwargs: Any) -> None:
        """
        Updates the project instance by passing the keyword arguments of the attributes
        you want updated

        Example:

        ```python
        lab.update(auto_close=True)
        ```

        This will update the project `auto_close` attribute to `True`

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}"

        # TODO: Verify that the passed kwargs are supported ones
        _response = _conn.http_call("put", _url, json_data=kwargs)

        # Update object
        self._update(_response.json())

    @verify_connector_and_id
    def delete(self) -> None:
        """
        Deletes the project from the server. It sets to `None` the attributes
        `project_id` and `name` when executed successfully

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}"

        _conn.http_call("delete", _url)

        self.project_id = None
        self.name = None

    @verify_connector_and_id
    def close(self) -> None:
        """
        Closes the project on the server.

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/close"

        _response = _conn.http_call("post", _url)

        # Update object
        if _response.status_code == 204:
            self.status = "closed"

    @verify_connector_and_id
    def open(self) -> None:
        """
        Opens the project on the server.

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/open"

        _response = _conn.http_call("post", _url)

        # Update object
        self._update(_response.json())

    @verify_connector_and_id
    def get_stats(self) -> None:
        """
        Retrieve the stats of the project.

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/stats"

        _response = _conn.http_call("get", _url)

        # Update object
        self.stats = _response.json()

    @verify_connector_and_id
    def get_file(self, path: str) -> str:
        """
        Retrieve a file in the project directory. Beware you have warranty to be able to
        access only to file global to the project.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `path`: Project's relative path of the file
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/files/{path}"

        return cast(str, _conn.http_call("get", _url).text)

    @verify_connector_and_id
    def write_file(self, path: str, data: Any) -> None:
        """
        Places a file content on a specified project file path. Beware you have warranty
        to be able to access only to file global to the project.

        Example to create a README.txt for the project:

        ```python
        >>> data = '''
            This is a README description!
            '''

        >>> project.write_file(path='README.txt', data=data)
        ```

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `path`: Project's relative path of the file
        - `data`: Data to be included in the file
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/files/{path}"

        _conn.http_call("post", _url, data=data)

    @verify_connector_and_id
    def get_nodes(self) -> None:
        """
        Retrieve the nodes of the project.

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes"

        _response = _conn.http_call("get", _url)

        # Create the Nodes array but cleanup cache if there is one
        if self.nodes:
            self.nodes = []
        for _node in _response.json():
            _n = Node(connector=self.connector, **_node)
            _n.project_id = self.project_id
            self.nodes.append(_n)

    @verify_connector_and_id
    def get_links(self) -> None:
        """
        Retrieve the links of the project.

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/links"

        _response = _conn.http_call("get", _url)

        # Create the Nodes array but cleanup cache if there is one
        if self.links:
            self.links = []
        for _link in _response.json():
            _l = Link(connector=self.connector, **_link)
            _l.project_id = self.project_id
            self.links.append(_l)

    @verify_connector_and_id
    def start_nodes(self, poll_wait_time: int = 5) -> None:
        """
        Starts all the nodes inside the project.

        - `poll_wait_time` is used as a delay when performing the next query of the
        nodes status.

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/start"

        _conn.http_call("post", _url)

        # Update object
        time.sleep(poll_wait_time)
        self.get_nodes()

    @verify_connector_and_id
    def stop_nodes(self, poll_wait_time: int = 5) -> None:
        """
        Stops all the nodes inside the project.

        - `poll_wait_time` is used as a delay when performing the next query of the
        nodes status.

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/stop"

        _conn.http_call("post", _url)

        # Update object
        time.sleep(poll_wait_time)
        self.get_nodes()

    @verify_connector_and_id
    def reload_nodes(self, poll_wait_time: int = 5) -> None:
        """
        Reloads all the nodes inside the project.

        - `poll_wait_time` is used as a delay when performing the next query of the
        nodes status.

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/reload"

        _conn.http_call("post", _url)

        # Update object
        time.sleep(poll_wait_time)
        self.get_nodes()

    @verify_connector_and_id
    def suspend_nodes(self, poll_wait_time: int = 5) -> None:
        """
        Suspends all the nodes inside the project.

        - `poll_wait_time` is used as a delay when performing the next query of the
        nodes status.

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/nodes/suspend"

        _conn.http_call("post", _url)

        # Update object
        time.sleep(poll_wait_time)
        self.get_nodes()

    def nodes_summary(
        self, is_print: bool = True
    ) -> list[tuple[Any, ...]] | None:
        """
        Returns a summary of the nodes insode the project. If `is_print` is `False`, it
        will return a list of tuples like:

        `[(node_name, node_status, node_console, node_id) ...]`

        **Required Attributes:**

        - `project_id`
        - `connector`
        """

        if not self.nodes:
            self.get_nodes()

        _nodes_summary = []
        for _n in self.nodes:
            if is_print:
                print(
                    f"{_n.name}: {_n.status} -- Console: {_n.console} -- "
                    f"ID: {_n.node_id}"
                )
            _nodes_summary.append((_n.name, _n.status, _n.console, _n.node_id))

        return _nodes_summary if not is_print else None

    def nodes_inventory(self) -> dict[str | None, Any]:
        """
        Returns an inventory-style dictionary of the nodes

        Example:

        `{
            "router01": {
                "server": "127.0.0.1",
                "name": "router01",
                "node_id": uuid,
                "console_port": 5077,
                "type": "vEOS",
                "ports": "[port detila]",
                "x": 100,
                "y": 200
            }
        }`

        **Required Attributes:**

        - `project_id`
        - `connector`
        """

        if not self.nodes:
            self.get_nodes()

        _nodes_inventory = {}
        conn = self.connector
        if not conn:
            raise ValueError(
                "Gns3Connector not assigned. Please set the connector first."
            )

        _server = urlparse(conn.base_url).hostname

        for _n in self.nodes:
            _nodes_inventory.update(
                {
                    _n.name: {
                        "server": _server,
                        "name": _n.name,
                        "node_id": _n.node_id,
                        "console_port": _n.console,
                        "console_type": _n.console_type,
                        "type": _n.node_type,
                        "ports": _n.ports,
                        "status": _n.status,
                        # "template": _n.template,
                        "x": _n.x,
                        "y": _n.y,
                        "tags": _n.tags if _n.tags else [],
                    }
                }
            )

        return _nodes_inventory

    def links_summary(
        self, is_print: bool = True
    ) -> list[dict[str, str]] | None:
        """
        Returns a summary of the links inside the project. If `is_print` is False,
        it will return a list of dicts like:

        `[{"link_id": "xxx", "node_a": "R1", "port_a": "Eth0/0", "node_b": "R2", "port_b": "Eth0/0"}, ...]`

        **Required Attributes:**

        - `project_id`
        - `connector`
        """
        # Ensure data is loaded
        if not self.nodes:
            self.get_nodes()
        if not self.links:
            self.get_links()
        # If None, program errors here instead of continuing
        assert self.links is not None, "Links must be loaded"
        assert self.nodes is not None, "Nodes must be loaded"

        _links_summary: list[dict[str, str]] = []

        for _l in self.links:
            if not _l.nodes:
                continue
            _side_a = _l.nodes[0]
            _side_b = _l.nodes[1]

            try:
                # Add type-safe lookup logic
                _node_a = next(
                    x for x in self.nodes if x.node_id == _side_a["node_id"]
                )
                # Ensure getting str to resolve [return-value] error
                _port_a = str(
                    next(
                        x["name"]
                        for x in (_node_a.ports or [])
                        if x["port_number"] == _side_a["port_number"]
                        and x["adapter_number"] == _side_a["adapter_number"]
                    )
                )

                _node_b = next(
                    x for x in self.nodes if x.node_id == _side_b["node_id"]
                )
                _port_b = str(
                    next(
                        x["name"]
                        for x in (_node_b.ports or [])
                        if x["port_number"] == _side_b["port_number"]
                        and x["adapter_number"] == _side_b["adapter_number"]
                    )
                )

                # Ensure name is not None
                name_a = str(_node_a.name) if _node_a.name else "Unknown"
                name_b = str(_node_b.name) if _node_b.name else "Unknown"

                endpoint_a = f"{name_a}: {_port_a}"
                endpoint_b = f"{name_b}: {_port_b}"

                if is_print:
                    print(f"{endpoint_a} ---- {endpoint_b}")

                _links_summary.append({
                    "link_id": _l.link_id,
                    "node_a": name_a,
                    "port_a": _port_a,
                    "node_b": name_b,
                    "port_b": _port_b
                })

            except (StopIteration, KeyError, AttributeError):
                # Prevent errors when list comprehension can't match data
                continue
        return _links_summary if not is_print else None

    def _search_node(self, key: str, value: Any) -> Any | None:
        "Performs a search based on a key and value"
        # Retrive nodes if neccesary
        if not self.nodes:
            self.get_nodes()

        try:
            return [_p for _p in self.nodes if getattr(_p, key) == value][0]
        except IndexError:
            return None

    def get_node(
        self, name: str | None = None, node_id: str | None = None
    ) -> Any | None:
        """
        Returns the Node object by searching for the `name` or the `node_id`.

        **Required Attributes:**

        - `project_id`
        - `connector`

        **Required keyword arguments:**
        - `name` or `node_id`

        **NOTE:** Run method `get_nodes()` manually to refresh list of nodes if
        necessary
        """
        if node_id:
            return self._search_node(key="node_id", value=node_id)
        elif name:
            return self._search_node(key="name", value=name)
        else:
            raise ValueError("name or node_ide must be provided")

    def _search_link(self, key: str, value: Any) -> Any | None:
        "Performs a search based on a key and value"
        # Retrive links if neccesary
        if not self.links:
            self.get_links()

        try:
            return next(_p for _p in self.links if getattr(_p, key) == value)
        except StopIteration:
            return None

    def get_link(self, link_id: str) -> Any | None:
        """
        Returns the Link object by locating its ID

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `link_id`

        **NOTE:** Run method `get_links()` manually to refresh list of links if
        necessary
        """
        return self._search_link(key="link_id", value=link_id)

    def create_node(self, **kwargs: Any) -> None:
        """
        Creates a node. To know available parameters see `Node` object, specifically
        the `create` method. The most basic example would be:

        ```python
        project.create_node(name='test-switch01', template='Ethernet switch')
        ```

        **Required Project instance attributes:**

        - `project_id`
        - `connector`

        **Required keyword aguments:**

        - `template` or `template_id`
        """
        if not self.nodes:
            self.get_nodes()

        _node = Node(
            project_id=self.project_id, connector=self.connector, **kwargs
        )

        _node.create()
        self.nodes.append(_node)
        print(
            f"Created: {_node.name} -- Type: {_node.node_type} -- "
            f"Console: {_node.console}"
        )

    def create_link(
        self, node_a: str, port_a: str, node_b: str, port_b: str
    ) -> None:
        """
        Creates a link.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `node_a`: Node name of the A side
        - `port_a`: Port name of the A side (must match the `name` attribute of the
        port)
        - `node_b`: Node name of the B side
        - `port_b`: Port name of the B side (must match the `name` attribute of the
        port)
        """
        if not self.nodes:
            self.get_nodes()
        if not self.links:
            self.get_links()

        _node_a = self.get_node(name=node_a)
        if not _node_a:
            raise ValueError(f"node_a: {node_a} not found")
        try:
            _port_a = [_p for _p in _node_a.ports if _p["name"] == port_a][0]
        except IndexError:
            raise ValueError(f"port_a: {port_a} not found") from None

        _node_b = self.get_node(name=node_b)
        if not _node_b:
            raise ValueError(f"node_b: {node_b} not found")
        try:
            _port_b = [_p for _p in _node_b.ports if _p["name"] == port_b][0]
        except IndexError:
            raise ValueError(f"port_b: {port_b} not found") from None

        _matches = []
        for _l in self.links:
            if not _l.nodes:
                continue
            if (
                _l.nodes[0]["node_id"] == _node_a.node_id
                and _l.nodes[0]["adapter_number"] == _port_a["adapter_number"]
                and _l.nodes[0]["port_number"] == _port_a["port_number"]
            ):
                _matches.append(_l)
            elif (
                _l.nodes[1]["node_id"] == _node_b.node_id
                and _l.nodes[1]["adapter_number"] == _port_b["adapter_number"]
                and _l.nodes[1]["port_number"] == _port_b["port_number"]
            ):
                _matches.append(_l)  # pragma: no cover
        if _matches:
            raise ValueError(
                f"At least one port is used, ID: {_matches[0].link_id}"
            )

        # Now create the link!
        _link = Link(
            project_id=self.project_id,
            connector=self.connector,
            nodes=[
                {
                    "node_id": _node_a.node_id,
                    "adapter_number": _port_a["adapter_number"],
                    "port_number": _port_a["port_number"],
                    "label": {"text": _port_a["name"]},
                },
                {
                    "node_id": _node_b.node_id,
                    "adapter_number": _port_b["adapter_number"],
                    "port_number": _port_b["port_number"],
                    "label": {"text": _port_b["name"]},
                },
            ],
        )

        _link.create()
        self.links.append(_link)
        print(f"Created Link-ID: {_link.link_id} -- Type: {_link.link_type}")

    def delete_link(
        self, node_a: str, port_a: str, node_b: str, port_b: str
    ) -> None:
        """
        Deletes  a link.

        **Required Attributes:**

        - `project_id`
        - `connector`
        - `node_a`: Node name of the A side
        - `port_a`: Port name of the A side (must match the `name` attribute of the
        port)
        - `node_b`: Node name of the B side
        - `port_b`: Port name of the B side (must match the `name` attribute of the
        port)
        """
        if not self.nodes:
            self.get_nodes()  # pragma: no cover
        if not self.links:
            self.get_links()  # pragma: no cover

        # checking link info
        _node_a = self.get_node(name=node_a)
        if not _node_a:
            raise ValueError(f"node_a: {node_a} not found")
        try:
            _port_a = [_p for _p in _node_a.ports if _p["name"] == port_a][0]
        except IndexError:
            raise ValueError(f"port_a: {port_a} not found") from None

        _node_b = self.get_node(name=node_b)
        if not _node_b:
            raise ValueError(f"node_b: {node_b} not found")
        try:
            _port_b = [_p for _p in _node_b.ports if _p["name"] == port_b][0]
        except IndexError:
            raise ValueError(f"port_b: {port_b} not found") from None

        _matches = []
        for _l in self.links:
            if not _l.nodes:
                continue
            if (
                _l.nodes[0]["node_id"] == _node_a.node_id
                and _l.nodes[0]["adapter_number"] == _port_a["adapter_number"]
                and _l.nodes[0]["port_number"] == _port_a["port_number"]
            ):
                _matches.append(_l)
            elif (
                _l.nodes[1]["node_id"] == _node_b.node_id
                and _l.nodes[1]["adapter_number"] == _port_b["adapter_number"]
                and _l.nodes[1]["port_number"] == _port_b["port_number"]
            ):
                _matches.append(_l)
        if not _matches:
            raise ValueError(
                f"Link not found: {node_a, port_a, node_b, port_b}"
            )  # pragma: no cover

            # now to delete the link via GNS3_api
        _link = _matches[0]
        self.links.remove(_link)
        _link_id = _link.link_id
        _link.delete()
        print(
            f"Deleted Link-ID: {_link_id} From node {node_a}, port: {port_a} <-->  "
            f"to node {node_b}, port: {port_b}"
        )

    @verify_connector_and_id
    def get_snapshots(self) -> None:
        """
        Retrieves list of snapshots of the project

        **Required Project instance attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/snapshots"

        _response = _conn.http_call("get", _url)
        self.snapshots = _response.json()

    def _search_snapshot(self, key: str, value: Any) -> dict[str, Any] | None:
        "Performs a search based on a key and value"
        if not self.snapshots:
            self.get_snapshots()

        try:
            return next(
                _p for _p in (self.snapshots or []) if _p[key] == value
            )
        except StopIteration:
            return None

    def get_snapshot(
        self, name: str | None = None, snapshot_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Returns the Snapshot by searching for the `name` or the `snapshot_id`.

        **Required Attributes:**

        - `project_id`
        - `connector`

        **Required keyword arguments:**
        - `name` or `snapshot_id`
        """
        if snapshot_id:
            return self._search_snapshot(key="snapshot_id", value=snapshot_id)
        elif name:
            return self._search_snapshot(key="name", value=name)
        else:
            raise ValueError("name or snapshot_id must be provided")

    @verify_connector_and_id
    def create_snapshot(self, name: str) -> None:
        """
        Creates a snapshot of the project

        **Required Project instance attributes:**

        - `project_id`
        - `connector`

        **Required keyword aguments:**

        - `name`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        self.get_snapshots()

        _snapshot = self.get_snapshot(name=name)
        if _snapshot:
            raise ValueError("Snapshot already created")

        _url = f"{_conn.nector.base_url}/projects/{_project_id}/snapshots"

        _response = _conn.http_call("post", _url, json_data={"name": name})

        _snapshot = _response.json()

        if self.snapshots is None:
            self.snapshots = []

        self.snapshots.append(_snapshot)
        print(f"Created snapshot: {_snapshot['name']}")

    @verify_connector_and_id
    def delete_snapshot(
        self, name: str | None = None, snapshot_id: str | None = None
    ) -> None:
        """
        Deletes a snapshot of the project

        **Required Project instance attributes:**

        - `project_id`
        - `connector`

        **Required keyword aguments:**

        - `name` or `snapshot_id`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        self.get_snapshots()

        _snapshot = self.get_snapshot(name=name, snapshot_id=snapshot_id)
        if not _snapshot:
            raise ValueError("Snapshot not found")

        _url = (
            f"{_conn.base_url}/projects/{_project_id}/snapshots/"
            f"{_snapshot['snapshot_id']}"
        )

        _conn.http_call("delete", _url)

        self.get_snapshots()

    @verify_connector_and_id
    def restore_snapshot(
        self, name: str | None = None, snapshot_id: str | None = None
    ) -> None:
        """
        Restore a snapshot from disk

        **Required Project instance attributes:**

        - `project_id`
        - `connector`

        **Required keyword aguments:**

        - `name` or `snapshot_id`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        self.get_snapshots()

        _snapshot = self.get_snapshot(name=name, snapshot_id=snapshot_id)
        if not _snapshot:
            raise ValueError("Snapshot not found")

        _url = (
            f"{_conn.base_url}/projects/{_project_id}/snapshots/"
            f"{_snapshot['snapshot_id']}/restore"
        )

        _conn.http_call("post", _url)

        # Update the whole project
        self.get()

    def arrange_nodes_circular(self, radius: int = 120) -> None:
        """
        Re-arrgange the existing nodes
        in a circular fashion

        **Attributes:**

        - project instance created

        **Example**

        ```python
        >>> proj = Project(name='project_name', connector=Gns3connector)
        >>> proj.arrange_nodes()
        ```
        """

        self.get()
        if self.status != "opened":
            self.open()  # pragma: no cover

        _angle = (2 * pi) / len(self.nodes)
        # The Y Axis is inverted in GNS3, so the -Y is UP
        for index, n in enumerate(self.nodes):
            _x = int(radius * (sin(_angle * index)))
            _y = int(radius * (-cos(_angle * index)))
            n.update(x=_x, y=_y)

    def get_drawing(
        self, drawing_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Returns the drawing by searching for the `svg` or the `drawing_id`.

        **Required Attributes:**

        - `project_id`
        - `connector`

        **Required keyword arguments:**
        - `svg` or `drawing_id`
        """
        if not self.drawings:
            self.get_drawings()

        try:
            return next(
                _drawing
                for _drawing in (self.drawings or [])
                if _drawing["drawing_id"] == drawing_id
            )
        except (StopIteration, KeyError, TypeError):
            return None

    @verify_connector_and_id
    def get_drawings(self) -> None:
        """
        Retrieves list of drawings  of the project

        **Required Project instance attributes:**

        - `project_id`
        - `connector`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/drawings"

        _response = _conn.http_call("get", _url)
        self.drawings = _response.json()

    @verify_connector_and_id
    def create_drawing(
        self,
        svg: str,
        x: int = 0,
        y: int = 0,
        z: int = 0,
        locked: bool = False,
        rotation: int = 0,
    ) -> dict[str, Any]:
        """
        Creates a new drawing in the project

        API: POST /v2/projects/{project_id}/drawings

        Required Project instance attributes:

        - `project_id`
        - `connector`

        Required parameters:

        - `svg`: SVG content string

        Optional parameters:

        - `x`: X coordinate (default: 0)
        - `y`: Y coordinate (default: 0)
        - `z`: Z layer (default: 0)
        - `locked`: Whether to lock the drawing (default: False)
        - `rotation`: Rotation angle in degrees, range -359 to 359 (default: 0)
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/drawings"

        # Prepare request body
        request_body = {
            "svg": svg,
            "x": x,
            "y": y,
            "z": z,
            "locked": locked,
            "rotation": rotation,
        }

        # Send POST request to create drawing
        _response = _conn.http_call("post", _url, json_data=request_body)

        # Refresh drawings list
        self.get_drawings()

        return cast(dict[str, Any], _response.json())

    @verify_connector_and_id
    def update_drawing(
        self,
        drawing_id: str,
        svg: str | None = None,
        locked: bool | None = None,
        x: int | None = None,
        y: int | None = None,
        z: int | None = None,
    ) -> dict[str, Any]:
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        _url = f"{_conn.base_url}/projects/{_project_id}/drawings/{drawing_id}"

        # Ensure data exists
        if not self.drawings:
            self.get_drawings()

        # Type guard: inform Mypy that self.drawings is now an iterable list
        # Use or [] with next to find target object
        current_drawing = next(
            (
                d
                for d in (self.drawings or [])
                if d.get("drawing_id") == drawing_id
            ),
            None,
        )

        if current_drawing is None:
            raise ValueError(
                f"Drawing with ID {drawing_id} not found in project."
            )

        # If parameter is None, get original value from current object
        # This way, Mypy won't report errors for list comprehensions of each field
        final_svg = svg if svg is not None else current_drawing.get("svg")
        final_locked = (
            locked if locked is not None else current_drawing.get("locked")
        )
        final_x = x if x is not None else current_drawing.get("x")
        final_y = y if y is not None else current_drawing.get("y")
        final_z = z if z is not None else current_drawing.get("z")

        # Execute update
        response = _conn.http_call(
            "put",
            _url,
            json_data={
                "svg": final_svg,
                "locked": final_locked,
                "x": final_x,
                "y": final_y,
                "z": final_z,
            },
        )

        # Update local cache
        self.get_drawings()

        return cast(dict[str, Any], response.json())

    @verify_connector_and_id
    def delete_drawing(self, drawing_id: str | None = None) -> None:
        """
        Deletes a drawing of the project

        **Required Project instance attributes:**

        - `project_id`
        - `connector`

        **Required keyword aguments:**

        - `drawing_id`
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        self.get_drawings()

        _drawing = self.get_drawing(drawing_id=drawing_id)
        if not _drawing:
            raise ValueError("drawing not found")

        _url = (
            f"{_conn.base_url}/projects/{_project_id}/drawings/"
            f"{_drawing['drawing_id']}"
        )

        _conn.http_call("delete", _url)

        self.get_drawings()

    @verify_connector_and_id
    def get_locked(self) -> bool:
        """
        Retrieve locked status of the project.

        Returns whether the project is locked or not.

        API: GET /v3/projects/{project_id}/locked

        Required Attributes:

        - `project_id`
        - `connector`

        Returns:
            bool: True if project is locked, False otherwise

        Raises:
            ValueError: If called with GNS3 API v2 (not supported)

        Note:
            This method is only available in GNS3 v3 API
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        # Check API version - only v3 supports lock operations
        if _conn.api_version != 3:
            raise ValueError(
                "Project lock/unlock operations are only supported in GNS3 API v3. "
                f"Current API version: v{_conn.api_version}"
            )

        _url = f"{_conn.base_url}/projects/{_project_id}/locked"

        _response = _conn.http_call("get", _url)
        locked_status = cast(bool, _response.json())

        # Update the locked attribute
        self.locked = locked_status

        return locked_status

    @verify_connector_and_id
    def lock_project(self) -> None:
        """
        Lock all drawings and nodes in the project.

        API: POST /v3/projects/{project_id}/lock

        Required Attributes:

        - `project_id`
        - `connector`

        Raises:
            ValueError: If called with GNS3 API v2 (not supported)

        Note:
            This method is only available in GNS3 v3 API
            Returns 204 on success (no content)
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        # Check API version - only v3 supports lock operations
        if _conn.api_version != 3:
            raise ValueError(
                "Project lock/unlock operations are only supported in GNS3 API v3. "
                f"Current API version: v{_conn.api_version}"
            )

        _url = f"{_conn.base_url}/projects/{_project_id}/lock"

        _conn.http_call("post", _url)

        # Update the locked attribute
        self.locked = True

    @verify_connector_and_id
    def unlock_project(self) -> None:
        """
        Unlock all drawings and nodes in the project.

        API: POST /v3/projects/{project_id}/unlock

        Required Attributes:

        - `project_id`
        - `connector`

        Raises:
            ValueError: If called with GNS3 API v2 (not supported)

        Note:
            This method is only available in GNS3 v3 API
            Returns 204 on success (no content)
        """
        _conn = self.connector
        assert _conn is not None
        _project_id = self.project_id
        assert _project_id is not None

        # Check API version - only v3 supports lock operations
        if _conn.api_version != 3:
            raise ValueError(
                "Project lock/unlock operations are only supported in GNS3 API v3. "
                f"Current API version: v{_conn.api_version}"
            )

        _url = f"{_conn.base_url}/projects/{_project_id}/unlock"

        _conn.http_call("post", _url)

        # Update the locked attribute
        self.locked = False
