#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
Docker server module.
"""

import asyncio
import json
import logging
import os
import shutil
import sys

import aiohttp
import platformdirs

from gns3server.compute.base_manager import BaseManager
from gns3server.compute.docker.docker_error import (
    DockerError,
    DockerHttp304Error,
    DockerHttp404Error,
    DockerHttp409Error,
)
from gns3server.compute.docker.docker_images import DockerImagesMixin
from gns3server.compute.docker.docker_vm import DockerVM
from gns3server.compute.docker.iol_docker_vm import IOLDockerVM
from gns3server.compute.docker.vendor_docker_vm import VendorDockerVM
from gns3server.config import Config
from gns3server.utils import parse_version

log = logging.getLogger(__name__)


# Be careful to keep it consistent
DOCKER_MINIMUM_API_VERSION = "1.40"
DOCKER_MINIMUM_VERSION = "19.03.8"
DOCKER_PREFERRED_API_VERSION = "1.44"


class Docker(DockerImagesMixin, BaseManager):
    _NODE_CLASS = DockerVM

    def __init__(self):

        super().__init__()
        self._server_url = "/var/run/docker.sock"
        self._connected = False
        # Allow locking during ubridge operations
        self.ubridge_lock = asyncio.Lock()
        self._connector = None
        self._session = None
        self._api_version = DOCKER_MINIMUM_API_VERSION
        self._host_checked = False
        # Image name -> (controller digest, local id) for the images synced from
        # the controller. The controller pins the id its own daemon reports,
        # which is not comparable with the id this daemon reports for the same
        # content (see load_image()).
        self._image_id_translations = {}

    def _select_node_class(self, **kwargs):
        """
        Select the node class based on console_type and GNS3_* environment
        markers. Like console_type, the environment is fixed at node creation
        time: toggling a marker via PUT takes effect after a project reload.
        """
        if kwargs.get("console_type") == "docker_exec":
            return VendorDockerVM
        environment = kwargs.get("environment") or ""
        for line in environment.splitlines():
            line = line.strip().rstrip(",")
            if line.startswith("GNS3_IOL_RUNNER="):
                return IOLDockerVM
            if line.startswith("GNS3_UNIX_SOCKET_NIO="):
                # Generic capability, usable without the IOL specifics.
                return VendorDockerVM
        return DockerVM

    async def create_node(self, name, project_id, node_id, *args, **kwargs):
        self._NODE_CLASS = self._select_node_class(**kwargs)
        return await super().create_node(name, project_id, node_id, *args, **kwargs)

    @staticmethod
    async def install_busybox(dst_dir):

        dst_busybox = os.path.join(dst_dir, "bin", "busybox")
        if os.path.isfile(dst_busybox):
            return
        for busybox_exec in ("busybox-static", "busybox.static", "busybox"):
            busybox_path = shutil.which(busybox_exec)
            if busybox_path:
                try:
                    # check that busybox is statically linked
                    # (dynamically linked busybox will fail to run in a container)
                    proc = await asyncio.create_subprocess_exec(
                        "ldd", busybox_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
                    )
                    stdout, _ = await proc.communicate()
                    if proc.returncode == 1 or "static" in busybox_exec:
                        # ldd returns 1 if the file is not a dynamic executable
                        # on Alpine/musl, ldd returns 0 even for static binaries,
                        # so also trust binaries named busybox-static or busybox.static
                        log.info(f"Installing busybox from '{busybox_path}' to '{dst_busybox}'")
                        shutil.copy2(busybox_path, dst_busybox, follow_symlinks=True)
                        return
                    else:
                        log.warning(
                            f"Busybox '{busybox_path}' is dynamically linked\n"
                            f"{stdout.decode('utf-8', errors='ignore').strip()}"
                        )
                except OSError as e:
                    raise DockerError(f"Could not install busybox: {e}")
        raise DockerError(
            "No busybox executable could be found, please install busybox (apt install busybox-static on Debian/Ubuntu) and make sure it is in your PATH"
        )

    @staticmethod
    def resources_path():
        """
        Get the Docker resources storage directory
        """

        resources_path = Config.instance().settings.Server.resources_path
        if not resources_path:
            appname = vendor = "GNS3"
            resources_path = platformdirs.user_data_dir(appname, vendor, roaming=True)
        else:
            resources_path = os.path.expanduser(resources_path)
        docker_resources_dir = os.path.join(resources_path, "docker")
        os.makedirs(docker_resources_dir, exist_ok=True)
        return docker_resources_dir

    async def install_resources(self):
        """
        Copy the necessary resources to a writable location and install busybox
        """

        try:
            dst_path = self.resources_path()
            log.info(f"Installing Docker resources in '{dst_path}'")
            from gns3server.controller import Controller

            await Controller.instance().install_resource_files(dst_path, "compute/docker/resources")
            await self.install_busybox(dst_path)
        except OSError as e:
            raise DockerError(f"Could not install Docker resources to {dst_path}: {e}")

    async def _check_connection(self):

        if not self._connected:
            try:
                self._connected = True
                docker_info = await self.query("GET", "version")
            except (aiohttp.ClientError, FileNotFoundError):
                self._connected = False
                raise DockerError("Can't connect to Docker daemon")

            api_version = parse_version(docker_info["ApiVersion"])
            version = docker_info["Version"]

            if api_version < parse_version(DOCKER_MINIMUM_API_VERSION):
                raise DockerError(
                    f"Docker version is {version}. GNS3 requires a minimum version of {DOCKER_MINIMUM_VERSION}"
                )

            preferred_api_version = parse_version(DOCKER_PREFERRED_API_VERSION)
            if api_version >= preferred_api_version:
                self._api_version = DOCKER_PREFERRED_API_VERSION
            else:
                # use the Min API version supported by the daemon
                self._api_version = docker_info["MinAPIVersion"]
                log.warning(f"Using Docker client with the minimum API version {self._api_version}")

            log.info(f"Connected to Docker daemon version {version} using API version {self._api_version}")
            self._check_host_readiness()

    def _check_host_readiness(self):
        """
        Best-effort, read-only check of kernel settings that heavy NOS containers
        (e.g. Cisco XRd) need. The server runs unprivileged (only the setuid
        ubridge helper gets root), so we cannot raise these limits ourselves --
        we only warn, with the exact commands to fix, when they are too low or
        when FUSE support is missing. Runs at most once per process.
        """

        if self._host_checked:
            return
        self._host_checked = True

        # Thresholds recommended for running several heavy containers (sized for
        # ~15 XRd-style nodes). Raising them is harmless; the stock Linux defaults
        # (e.g. max_user_instances=128) are far too low and break such images.
        thresholds = {
            "fs.inotify.max_user_instances": 64000,
            "fs.inotify.max_user_watches": 524288,
            "fs.file-max": 1000000,
        }
        low = []
        for key, minimum in thresholds.items():
            try:
                with open(f"/proc/sys/{key.replace('.', '/')}") as f:
                    current = int(f.read().strip())
            except (OSError, ValueError):
                # One unreadable key must not discard the warnings already
                # collected nor skip the FUSE check — skip just this key.
                continue
            if current < minimum:
                low.append((key, current, minimum))

        fuse_supported = False
        try:
            with open("/proc/filesystems") as f:
                filesystems = {parts[-1] for parts in (line.split() for line in f) if parts}
            fuse_supported = "fuse" in filesystems or "fuseblk" in filesystems
        except OSError:
            pass

        if low:
            details = ", ".join(f"{k}={c} (need >={m})" for k, c, m in low)
            raise_cmd = " ".join(f"{k}={m}" for k, _, m in low)
            log.warning(
                f"Low kernel limits for heavy Docker containers ({details}). "
                f"Some NOS images (e.g. Cisco XRd) may fail to start. Raise once: "
                f"'sudo sysctl -w {raise_cmd}' and persist it under /etc/sysctl.d/."
            )
        if not fuse_supported:
            log.warning(
                "FUSE filesystem support is not available in the kernel. "
                "Containers that need it (e.g. Cisco XRd) will fail. Load it: 'sudo modprobe fuse'."
            )

    def connector(self):

        if self._connector is None or self._connector.closed:
            if not sys.platform.startswith("linux"):
                raise DockerError("Docker is supported only on Linux")
            try:
                self._connector = aiohttp.connector.UnixConnector(self._server_url, limit=None)
            except (aiohttp.ClientError, FileNotFoundError):
                raise DockerError("Can't connect to docker daemon")
        return self._connector

    async def unload(self):

        await super().unload()
        if self._connected:
            if self._connector and not self._connector.closed:
                await self._connector.close()
        if self._session and not self._session.closed:
            await self._session.close()

    async def query(self, method, path, data={}, params={}):
        """
        Makes a query to the Docker daemon and decode the request

        :param method: HTTP method
        :param path: Endpoint in API
        :param data: Dictionary with the body. Will be transformed to a JSON
        :param params: Parameters added as a query arg
        """

        response = await self.http_query(method, path, data=data, params=params)
        body = await response.read()
        response.close()
        if response.headers.get("CONTENT-TYPE") == "application/json":
            body = json.loads(body.decode("utf-8", errors="ignore"))
        else:
            body = body.decode("utf-8", errors="ignore")
        log.debug("Query Docker %s %s params=%s data=%s Response: %s", method, path, params, data, body)
        return body

    async def http_query(self, method, path, data={}, params={}, timeout=300):  # noqa: ASYNC109 - operation-specific timeout is intentional
        """
        Makes a query to the docker daemon

        :param method: HTTP method
        :param path: Endpoint in API
        :param data: Dictionary with the body. Will be transformed to a JSON
        :param params: Parameters added as a query arg
        :param timeout: Total timeout in seconds, an aiohttp ClientTimeout object
            for a finer policy (e.g. an idle socket read timeout), or None for no timeout
        :returns: HTTP response
        """

        if isinstance(data, dict):
            data = json.dumps(data)
            headers = {"content-type": "application/json"}
        else:
            # not a dict (e.g. a Docker image tar stream): let aiohttp stream the raw body
            headers = {"content-type": "application/x-tar"}
        if timeout is None:
            timeout = aiohttp.ClientTimeout(total=None)

        if path == "version":
            url = "http://docker/" + path
        else:
            await self._check_connection()  # version is use by check connection
            url = "http://docker/v" + self._api_version + "/" + path
        try:
            if self._session is None or self._session.closed:
                connector = self.connector()
                self._session = aiohttp.ClientSession(connector=connector)
            response = await self._session.request(
                method,
                url,
                params=params,
                data=data,
                headers=headers,
                timeout=timeout,
            )
        except aiohttp.ClientError as e:
            raise DockerError(f"Docker has returned an error: {e}")
        except TimeoutError:
            raise DockerError("Docker timeout " + method + " " + path)
        if response.status >= 300:
            body = await response.read()
            try:
                body = json.loads(body.decode("utf-8"))["message"]
            except ValueError:
                pass
            log.debug(f"Query Docker {method} {path} params={params} data={data} Response: {body}")
            if response.status == 304:
                raise DockerHttp304Error(f"Docker has returned an error: {response.status} {body}")
            elif response.status == 404:
                raise DockerHttp404Error(f"Docker has returned an error: {response.status} {body}")
            elif response.status == 409:
                raise DockerHttp409Error(f"Docker has returned an error: {response.status} {body}")
            else:
                raise DockerError(f"Docker has returned an error: {response.status} {body}")
        return response

    async def websocket_query(self, path, params={}):
        """
        Opens a websocket connection

        :param path: Endpoint in API
        :param params: Parameters added as a query arg
        :returns: Websocket
        """

        url = "http://docker/v" + self._api_version + "/" + path
        connection = await self._session.ws_connect(url, origin="http://docker", autoping=True)
        return connection
