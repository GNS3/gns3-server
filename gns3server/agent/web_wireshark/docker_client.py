# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2026 YueGuobin
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
Web Wireshark - Docker HTTP API client

This module handles Docker API operations via aiohttp Unix socket.
"""

import asyncio
import logging

import aiohttp

from gns3server.utils import parse_version

logger = logging.getLogger(__name__)

# Docker API configuration
DOCKER_SOCKET = "/var/run/docker.sock"
DOCKER_MINIMUM_API_VERSION = "1.40"
DOCKER_PREFERRED_API_VERSION = "1.44"


class DockerHTTPClient:
    """Docker HTTP API client using aiohttp with Unix socket connection."""

    # API request timeout (seconds)
    REQUEST_TIMEOUT = 10

    def __init__(self):
        self._connector = None
        self._session = None
        self._connected = False
        self._api_version = DOCKER_MINIMUM_API_VERSION

    async def _get_connector(self):
        """Get or create Unix socket connector."""
        if self._connector is None or self._connector.closed:
            try:
                self._connector = aiohttp.connector.UnixConnector(DOCKER_SOCKET, limit=None)
            except (aiohttp.ClientError, FileNotFoundError):
                raise RuntimeError(f"Can't connect to Docker daemon at {DOCKER_SOCKET}")
        return self._connector

    async def _get_session(self):
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            connector = await self._get_connector()
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self):
        """Close connections."""
        if self._session and not self._session.closed:
            await self._session.close()
        if self._connector and not self._connector.closed:
            await self._connector.close()
        self._connected = False

    async def _check_connection(self):
        """Check Docker connection and detect API version."""
        if not self._connected:
            try:
                # Get Docker version info
                docker_info = await self._request("GET", "version", check_connection=False)
                self._connected = True

                # Parse API version
                api_version = parse_version(docker_info['ApiVersion'])
                docker_version = docker_info["Version"]

                logger.info(f"Connected to Docker {docker_version}, API {api_version}")

                # Check minimum version requirement
                if api_version < parse_version(DOCKER_MINIMUM_API_VERSION):
                    raise RuntimeError(
                        f"Docker version is {docker_version}. "
                        f"GNS3 requires a minimum API version of {DOCKER_MINIMUM_API_VERSION}"
                    )

                # Use preferred API version if supported
                preferred_api_version = parse_version(DOCKER_PREFERRED_API_VERSION)
                if api_version >= preferred_api_version:
                    self._api_version = DOCKER_PREFERRED_API_VERSION
                    logger.info(f"Using Docker API version {self._api_version}")
                else:
                    # Use Docker daemon's actual API version
                    self._api_version = docker_info['ApiVersion']
                    logger.info(f"Using Docker API version {self._api_version} (daemon native)")

            except (aiohttp.ClientError, FileNotFoundError) as e:
                self._connected = False
                raise RuntimeError(f"Can't connect to Docker daemon: {e}") from e
            except KeyError as e:
                raise RuntimeError(f"Unexpected Docker API response: missing {e}") from e

    async def _request(self, method: str, endpoint: str, **kwargs):
        """
        Send request to Docker API.

        Args:
            method: HTTP method
            endpoint: API endpoint (without version prefix)
            **kwargs: Other parameters for aiohttp.request

        Returns:
            Response JSON data
        """
        # Check connection and version on first request
        check_connection = kwargs.pop('check_connection', True)
        if check_connection and not self._connected:
            await self._check_connection()

        session = await self._get_session()
        url = f"http://docker/v{self._api_version}/{endpoint}"

        try:
            async with asyncio.timeout(self.REQUEST_TIMEOUT):
                async with session.request(method, url, **kwargs) as response:
                    if response.status >= 300:
                        error_text = await response.text()
                        raise RuntimeError(f"Docker API error {response.status}: {error_text}")
                    if response.status == 204:  # No Content
                        return None
                    return await response.json()
        except asyncio.TimeoutError:
            raise RuntimeError(f"Docker API timeout after {self.REQUEST_TIMEOUT}s for {endpoint}")
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Docker connection error: {e}") from e

    async def create_network(self, name: str, driver: str = "bridge", subnet: str = None):
        """Create Docker network."""
        data = {
            "Name": name,
            "Driver": driver
        }
        if subnet:
            data["IPAM"] = {
                "Config": [{"Subnet": subnet}]
            }
        await self._request("POST", "networks/create", json=data)

    async def get_network(self, name: str):
        """Get network info."""
        try:
            return await self._request("GET", f"networks/{name}")
        except RuntimeError as e:
            if "404" in str(e):
                return None
            raise

    async def create_container(self, name: str, image: str, **kwargs):
        """Create container."""
        data = {
            "Image": image,
            "name": name,
            "HostConfig": {},
            "NetworkingConfig": {}
        }

        # Handle network config
        if "network" in kwargs:
            network_name = kwargs.pop("network")
            data["NetworkingConfig"]["EndpointsConfig"] = {
                network_name: {}
            }

        # Handle environment variables
        if "environment" in kwargs:
            data["Env"] = [f"{k}={v}" for k, v in kwargs.pop("environment").items()]

        # Handle resource limits
        if "host_config" in kwargs:
            data["HostConfig"].update(kwargs.pop("host_config"))
        else:
            # Legacy parameter format
            host_config = {}
            if "mem_limit" in kwargs:
                host_config["Memory"] = kwargs.pop("mem_limit")
            if "cpu_quota" in kwargs:
                host_config["NanoCpus"] = kwargs.pop("cpu_quota")
            if "pids_limit" in kwargs:
                host_config["PidsLimit"] = kwargs.pop("pids_limit")
            if "restart_policy" in kwargs:
                host_config["RestartPolicy"] = kwargs.pop("restart_policy")
            data["HostConfig"].update(host_config)

        # Handle health check
        if "health_config" in kwargs:
            data["HealthCheck"] = kwargs.pop("health_config")

        # Create container
        result = await self._request("POST", "containers/create", params={"name": name}, json=data)
        return result["Id"]

    async def start_container(self, container_id: str):
        """Start container."""
        await self._request("POST", f"containers/{container_id}/start")

    async def get_container(self, name: str):
        """Get container info."""
        try:
            return await self._request("GET", f"containers/{name}/json")
        except RuntimeError as e:
            if "404" in str(e):
                return None
            raise

    async def stop_container(self, container_id: str, timeout: int = 0):
        """Stop container immediately (force kill, no graceful shutdown)."""
        await self._request("POST", f"containers/{container_id}/stop", params={"t": timeout})

    async def remove_container(self, container_id: str, force: bool = False):
        """Remove container."""
        params = {"force": "true"} if force else {}
        await self._request("DELETE", f"containers/{container_id}", params=params)

    async def list_processes(self, container_name: str) -> list:
        """Get process list from container.

        Args:
            container_name: Container name (e.g., "gns3-wireshark-xxx")

        Returns:
            List of process dicts with keys: PID, USER, COMMAND, etc.
        """
        # Note: Docker API /containers/{id}/top returns text, not JSON
        # We need to use the session directly to get text response
        if not self._connected:
            await self._check_connection()

        session = await self._get_session()
        url = f"http://docker/v{self._api_version}/containers/{container_name}/top?ps_args=aux"

        try:
            async with asyncio.timeout(self.REQUEST_TIMEOUT):
                async with session.get(url) as response:
                    if response.status >= 300:
                        error_text = await response.text()
                        raise RuntimeError(f"Docker API error {response.status}: {error_text}")
                    result = await response.text()
        except asyncio.TimeoutError:
            raise RuntimeError(f"Docker API timeout after {self.REQUEST_TIMEOUT}s for containers/{container_name}/top")
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Docker connection error: {e}") from e

        # Docker API returns text format like:
        # USER    PID ... COMMAND
        # root      1 ... tail -f /dev/null
        # We need to parse this

        lines = result.strip().split('\n')
        if len(lines) < 2:
            return []

        # First line is header
        headers = lines[0].split()
        processes = []

        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.split(None, len(headers) - 1)
            if len(values) < len(headers):
                continue

            proc = {}
            for i, header in enumerate(headers):
                if i < len(values):
                    proc[header] = values[i]

            processes.append(proc)

        return processes
