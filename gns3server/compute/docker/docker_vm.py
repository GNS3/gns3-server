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
Docker container instance.
"""

import sys
import asyncio
import shutil
import psutil
import shlex
import aiohttp
import subprocess
import os
import re

from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer
from gns3server.utils.asyncio.raw_command_server import AsyncioRawCommandServer
from gns3server.utils.asyncio import wait_for_file_creation
from gns3server.utils.asyncio import monitor_process
from gns3server.utils.get_resource import get_resource
from gns3server.utils.hostname import is_rfc1123_hostname_valid

from gns3server.compute.ubridge.ubridge_error import UbridgeError, UbridgeNamespaceError
from ..base_node import BaseNode

from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIOUDP
from .docker_error import DockerError, DockerHttp304Error, DockerHttp404Error

import logging

log = logging.getLogger(__name__)


class DockerVM(BaseNode):
    """
    Docker container implementation.

    :param name: Docker container name
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Manager instance
    :param image: Docker image
    :param console: TCP console port
    :param console_type: console type
    :param aux: TCP aux console port
    :param aux_type: auxiliary console type
    :param console_resolution: Resolution of the VNC display
    :param console_http_port: Port to redirect HTTP queries
    :param console_http_path: Url part with the path of the web interface
    :param extra_hosts: Hosts which will be written into /etc/hosts into docker conainer
    :param extra_volumes: Additional directories to make persistent
    """

    def __init__(
        self,
        name,
        node_id,
        project,
        manager,
        image,
        console=None,
        aux=None,
        start_command=None,
        adapters=None,
        environment=None,
        console_type="telnet",
        aux_type="none",
        console_resolution="1024x768",
        console_http_port=80,
        console_http_path="/",
        extra_hosts=None,
        extra_volumes=[],
        memory=0,
        cpus=0,
    ):

        if not is_rfc1123_hostname_valid(name):
            raise DockerError(f"'{name}' is an invalid name to create a Docker node")

        super().__init__(
            name, node_id, project, manager, console=console, console_type=console_type, aux=aux, aux_type=aux_type
        )

        # force the latest image if no version is specified
        if ":" not in image:
            image = f"{image}:latest"
        self._image = image
        self._start_command = start_command
        self._environment = environment
        self._cid = None
        self._ethernet_adapters = []
        self._temporary_directory = None
        self._telnet_servers = []
        self._vnc_process = None
        self._vncconfig_process = None
        self._console_resolution = console_resolution
        self._console_http_path = console_http_path
        self._console_http_port = console_http_port
        self._console_websocket = None
        self._extra_hosts = extra_hosts
        self._extra_volumes = extra_volumes or []
        self._memory = memory
        self._cpus = cpus
        self._permissions_fixed = True
        self._display = None
        self._closing = False

        self._volumes = []
        # Keep a list of created bridge
        self._bridges = set()

        if adapters is None:
            self.adapters = 1
        else:
            self.adapters = adapters

        log.debug(
            "{module}: {name} [{image}] initialized.".format(
                module=self.manager.module_name, name=self.name, image=self._image
            )
        )

    def asdict(self):
        return {
            "name": self._name,
            "usage": self.usage,
            "node_id": self._id,
            "container_id": self._cid,
            "project_id": self._project.id,
            "image": self._image,
            "adapters": self.adapters,
            "console": self.console,
            "console_type": self.console_type,
            "console_resolution": self.console_resolution,
            "console_http_port": self.console_http_port,
            "console_http_path": self.console_http_path,
            "aux": self.aux,
            "aux_type": self.aux_type,
            "start_command": self.start_command,
            "status": self.status,
            "environment": self.environment,
            "node_directory": self.working_path,
            "extra_hosts": self.extra_hosts,
            "extra_volumes": self.extra_volumes,
            "memory": self.memory,
            "cpus": self.cpus,
        }

    def _get_free_display_port(self):
        """
        Search a free display port
        """
        display = 100
        if not os.path.exists("/tmp/.X11-unix/"):
            return display
        while True:
            if not os.path.exists(f"/tmp/.X11-unix/X{display}"):
                return display
            display += 1

    @BaseNode.name.setter
    def name(self, new_name):
        """
        Sets the name of this Qemu VM.

        :param new_name: name
        """

        if not is_rfc1123_hostname_valid(new_name):
            raise DockerError(f"'{new_name}' is an invalid name to rename Docker container '{self._name}'")
        super(DockerVM, DockerVM).name.__set__(self, new_name)

    @property
    def ethernet_adapters(self):
        return self._ethernet_adapters

    @property
    def start_command(self):
        return self._start_command

    @start_command.setter
    def start_command(self, command):
        if command:
            command = command.strip()
        if command is None or len(command) == 0:
            self._start_command = None
        else:
            self._start_command = command

    @property
    def console_resolution(self):
        return self._console_resolution

    @console_resolution.setter
    def console_resolution(self, resolution):
        self._console_resolution = resolution

    @property
    def console_http_path(self):
        return self._console_http_path

    @console_http_path.setter
    def console_http_path(self, path):
        self._console_http_path = path

    @property
    def console_http_port(self):
        return self._console_http_port

    @console_http_port.setter
    def console_http_port(self, port):
        self._console_http_port = port

    @property
    def environment(self):
        return self._environment

    @environment.setter
    def environment(self, command):
        self._environment = command

    @property
    def extra_hosts(self):
        return self._extra_hosts

    @extra_hosts.setter
    def extra_hosts(self, extra_hosts):
        self._extra_hosts = extra_hosts

    @property
    def extra_volumes(self):
        return self._extra_volumes

    @extra_volumes.setter
    def extra_volumes(self, extra_volumes):
        self._extra_volumes = extra_volumes

    @property
    def memory(self):
        return self._memory

    @memory.setter
    def memory(self, memory):
        self._memory = memory

    @property
    def cpus(self):
        return self._cpus

    @cpus.setter
    def cpus(self, cpus):
        self._cpus = cpus

    async def _get_container_state(self):
        """
        Returns the container state (e.g. running, paused etc.)

        :returns: state
        :rtype: str
        """

        try:
            result = await self.manager.query("GET", f"containers/{self._cid}/json")
        except DockerError:
            return "exited"

        if result["State"]["Paused"]:
            return "paused"
        if result["State"]["Running"]:
            return "running"
        return "exited"

    async def _get_image_information(self):
        """
        :returns: Dictionary information about the container image
        """

        result = await self.manager.query("GET", f"images/{self._image}/json")
        return result

    def _mount_binds(self, image_info):
        """
        :returns: Return the path that we need to map to local folders
        """

        try:
            resources_path = self.manager.resources_path()
        except OSError as e:
            raise DockerError(f"Cannot access resources: {e}")

        log.info(f'Mount resources from "{resources_path}"')
        binds = [{
            "Type": "bind",
            "Source": resources_path,
            "Target": "/gns3",
            "ReadOnly": True
        }]

        # We mount our own etc/network
        try:
            self._create_network_config()
        except OSError as e:
            raise DockerError(f"Could not create network config in the container: {e}")
        volumes = ["/etc/network"]

        volumes.extend((image_info.get("Config", {}).get("Volumes") or {}).keys())
        for volume in self._extra_volumes:
            if not volume.strip() or volume[0] != "/" or volume.find("..") >= 0:
                raise DockerError(
                    f"Persistent volume '{volume}' has invalid format. It must start with a '/' and not contain '..'."
                )
        volumes.extend(self._extra_volumes)

        self._volumes = []
        # define lambdas for validation checks
        nf = lambda x: re.sub(r"//+", "/", (x if x.endswith("/") else x + "/"))
        generalises = lambda v1, v2: nf(v2).startswith(nf(v1))
        for volume in volumes:
            # remove any mount that is equal or more specific, then append this one
            self._volumes = list(filter(lambda v: not generalises(volume, v), self._volumes))
            # if there is nothing more general, append this mount
            if not [v for v in self._volumes if generalises(v, volume)]:
                self._volumes.append(volume)

        for volume in self._volumes:
            source = os.path.join(self.working_dir, os.path.relpath(volume, "/"))
            os.makedirs(source, exist_ok=True)
            binds.append({
                "Type": "bind",
                "Source": source,
                "Target": "/gns3volumes{}".format(volume)
            })

        return binds

    def _create_network_config(self):
        """
        If network config is empty we create a sample config
        """
        path = os.path.join(self.working_dir, "etc", "network")
        os.makedirs(path, exist_ok=True)
        open(os.path.join(path, ".gns3_perms"), "a").close()
        os.makedirs(os.path.join(path, "if-up.d"), exist_ok=True)
        os.makedirs(os.path.join(path, "if-down.d"), exist_ok=True)
        os.makedirs(os.path.join(path, "if-pre-up.d"), exist_ok=True)
        os.makedirs(os.path.join(path, "if-post-down.d"), exist_ok=True)
        os.makedirs(os.path.join(path, "interfaces.d"), exist_ok=True)

        if not os.path.exists(os.path.join(path, "interfaces")):
            with open(os.path.join(path, "interfaces"), "w+") as f:
                f.write("""#
# This is a sample network config, please uncomment lines to configure the network
#

# Uncomment this line to load custom interface files
# source /etc/network/interfaces.d/*
""")
                for adapter in range(0, self.adapters):
                    f.write(
                        """
# Static config for eth{adapter}
#auto eth{adapter}
#iface eth{adapter} inet static
#\taddress 192.168.{adapter}.2
#\tnetmask 255.255.255.0
#\tgateway 192.168.{adapter}.1
#\tup echo nameserver 192.168.{adapter}.1 > /etc/resolv.conf

# DHCP config for eth{adapter}
#auto eth{adapter}
#iface eth{adapter} inet dhcp
#\thostname {hostname}
""".format(adapter=adapter, hostname=self._name))
        return path

    async def create(self):
        """
        Creates the Docker container.
        """

        if ":" in os.path.splitdrive(self.working_dir)[1]:
            raise DockerError("Cannot create a Docker container with a project directory containing a colon character (':')")

        #await self.manager.install_resources()

        try:
            image_infos = await self._get_image_information()
        except DockerHttp404Error:
            log.info(f"Image '{self._image}' is missing, pulling it from Docker hub...")
            await self.pull_image(self._image)
            image_infos = await self._get_image_information()

        if image_infos is None:
            raise DockerError(f"Cannot get information for image '{self._image}', please try again.")

        available_cpus = psutil.cpu_count(logical=True)
        if self._cpus > available_cpus:
            raise DockerError(
                f"You have allocated too many CPUs for the Docker container "
                f"(max available is {available_cpus} CPUs)"
            )

        params = {
            "Hostname": self._name,
            "Image": self._image,
            "NetworkDisabled": True,
            "Tty": True,
            "OpenStdin": True,
            "StdinOnce": False,
            "HostConfig": {
                "CapAdd": ["ALL"],
                "Privileged": True,
                "Mounts": self._mount_binds(image_infos),
                "Memory": self._memory * (1024 * 1024),  # convert memory to bytes
                "NanoCpus": int(self._cpus * 1e9),  # convert cpus to nano cpus
            },
            "Volumes": {},
            "Env": ["container=docker"],  # Systemd compliant: https://github.com/GNS3/gns3-server/issues/573
            "Cmd": [],
            "Entrypoint": image_infos.get("Config", {"Entrypoint": []}).get("Entrypoint"),
        }

        if params["Entrypoint"] is None:
            params["Entrypoint"] = []
        if self._start_command:
            try:
                params["Cmd"] = shlex.split(self._start_command)
            except ValueError as e:
                raise DockerError(f"Invalid start command '{self._start_command}': {e}")
        if len(params["Cmd"]) == 0:
            params["Cmd"] = image_infos.get("Config", {"Cmd": []}).get("Cmd")
            if params["Cmd"] is None:
                params["Cmd"] = []
        if len(params["Cmd"]) == 0 and len(params["Entrypoint"]) == 0:
            params["Cmd"] = ["/bin/sh"]
        params["Entrypoint"].insert(0, "/gns3/init.sh")  # FIXME /gns3/init.sh is not found?

        # Give the information to the container on how many interface should be inside
        params["Env"].append(f"GNS3_MAX_ETHERNET=eth{self.adapters - 1}")
        # Give the information to the container the list of volume path mounted
        params["Env"].append("GNS3_VOLUMES={}".format(":".join(self._volumes)))

        # Pass user configured for image to init script
        if image_infos.get("Config", {"User": ""}).get("User"):
            params["User"] = "root"
            params["Env"].append("GNS3_USER={}".format(image_infos.get("Config", {"User": ""})["User"]))

        variables = self.project.variables
        if not variables:
            variables = []

        for var in variables:
            formatted = self._format_env(variables, var.get("value", ""))
            params["Env"].append("{}={}".format(var["name"], formatted))

        if self._environment:
            for e in self._environment.strip().split("\n"):
                e = e.strip()
                if e.split("=")[0] == "":
                    self.project.emit("log.warning", {"message": f"{self.name} has invalid environment variable: {e}"})
                    continue
                if not e.startswith("GNS3_"):
                    formatted = self._format_env(variables, e)
                    vm_name = self._name.replace(",", ",,")
                    project_path = self.project.path.replace(",", ",,")
                    formatted = formatted.replace("%vm-name%", '"' + vm_name.replace('"', '\\"') + '"')
                    formatted = formatted.replace("%vm-id%", self._id)
                    formatted = formatted.replace("%project-id%", self.project.id)
                    formatted = formatted.replace("%project-path%", '"' + project_path.replace('"', '\\"') + '"')
                    params["Env"].append(formatted)

        if self._console_type == "vnc":
            await self._start_vnc()
            params["Env"].append(
                "QT_GRAPHICSSYSTEM=native"
            )  # To fix a Qt issue: https://github.com/GNS3/gns3-server/issues/556
            params["Env"].append(f"DISPLAY=:{self._display}")
            params["HostConfig"]["Mounts"].append({
                "Type": "bind",
                "Source": f"/tmp/.X11-unix/X{self._display}",
                "Target": f"/tmp/.X11-unix/X{self._display}",
                "ReadOnly": True
            })

        if self._extra_hosts:
            extra_hosts = self._format_extra_hosts(self._extra_hosts)
            if extra_hosts:
                params["Env"].append(f"GNS3_EXTRA_HOSTS={extra_hosts}")

        result = await self.manager.query("POST", "containers/create", data=params)
        self._cid = result["Id"]
        log.info(f"Docker container '{self._name}' [{self._id}] created")
        if self._cpus > 0:
            log.info(f"CPU limit set to {self._cpus} CPUs")
        if self._memory > 0:
            log.info(f"Memory limit set to {self._memory} MB")
        return True

    def _format_env(self, variables, env):
        for variable in variables:
            env = env.replace("${" + variable["name"] + "}", variable.get("value", ""))
        return env

    def _format_extra_hosts(self, extra_hosts):
        lines = [h.strip() for h in self._extra_hosts.split("\n") if h.strip() != ""]
        hosts = []
        try:
            for host in lines:
                hostname, ip = host.split(":")
                hostname = hostname.strip()
                ip = ip.strip()
                if hostname and ip:
                    hosts.append((hostname, ip))
        except ValueError:
            raise DockerError(f"Can't apply `ExtraHosts`, wrong format: {extra_hosts}")
        return "\n".join([f"{h[1]}\t{h[0]}" for h in hosts])

    async def update(self):
        """
        Destroy and recreate the container with the new settings
        """

        # We need to save the console and state and restore it
        console = self.console
        aux = self.aux
        state = await self._get_container_state()

        # reset the docker container, but don't release the NIO UDP ports
        await self.reset(False)
        await self.create()
        self.console = console
        self.aux = aux
        if state == "running":
            await self.start()

    async def start(self):
        """
        Starts this Docker container.
        """

        await self.manager.install_resources()

        try:
            state = await self._get_container_state()
        except DockerHttp404Error:
            raise DockerError(
                "Docker container '{name}' with ID {cid} does not exist or is not ready yet. Please try again in a few seconds.".format(
                    name=self.name, cid=self._cid
                )
            )
        if state == "paused":
            await self.unpause()
        elif state == "running":
            return
        else:

            if self._console_type == "vnc" and not self._vnc_process:
                # restart the vnc process in case it had previously crashed
                await self._start_vnc_process(restart=True)
                monitor_process(self._vnc_process, self._vnc_callback)

            if self._console_websocket:
                await self._console_websocket.close()
                self._console_websocket = None
            await self._clean_servers()

            await self.manager.query("POST", f"containers/{self._cid}/start")
            self._namespace = await self._get_namespace()

            await self._start_ubridge(require_privileged_access=True)

            for adapter_number in range(0, self.adapters):
                nio = self._ethernet_adapters[adapter_number].get_nio(0)
                async with self.manager.ubridge_lock:
                    try:
                        await self._add_ubridge_connection(nio, adapter_number)
                    except UbridgeNamespaceError:
                        log.error("Container %s failed to start", self.name)
                        await self.stop()

                        # The container can crash soon after the start, this means we can not move the interface to the container namespace
                        logdata = await self._get_log()
                        for line in logdata.split("\n"):
                            log.error(line)
                        raise DockerError(logdata)

            if self.console_type == "telnet":
                await self._start_console()
            elif self.console_type == "http" or self.console_type == "https":
                await self._start_http()

            if self.aux_type != "none":
                await self._start_aux()

        self._permissions_fixed = False
        self.status = "started"
        log.info(
            "Docker container '{name}' [{image}] started listen for {console_type} on {console}".format(
                name=self._name, image=self._image, console=self.console, console_type=self.console_type
            )
        )

    async def _start_aux(self):
        """
        Start an auxiliary console
        """

        # We can not use the API because docker doesn't expose a websocket api for exec
        # https://github.com/GNS3/gns3-gui/issues/1039
        try:
            process = await asyncio.subprocess.create_subprocess_exec(
                "script",
                "-qfc",
                f"docker exec -i -t {self._cid} /gns3/bin/busybox sh -c 'while true; do TERM=vt100 /gns3/bin/busybox sh; done'",
                "/dev/null",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                stdin=asyncio.subprocess.PIPE,
            )
        except OSError as e:
            raise DockerError(f"Could not start auxiliary console process: {e}")
        server = AsyncioTelnetServer(reader=process.stdout, writer=process.stdin, binary=True, echo=True)
        try:
            self._telnet_servers.append(
                await asyncio.start_server(server.run, self._manager.port_manager.console_host, self.aux)
            )
        except OSError as e:
            raise DockerError(
                f"Could not start Telnet server on socket {self._manager.port_manager.console_host}:{self.aux}: {e}"
            )
        log.debug(f"Docker container '{self.name}' started listen for auxiliary telnet on {self.aux}")

    async def _fix_permissions(self):
        """
        Because docker run as root we need to fix permission and ownership to allow user to interact
        with it from their filesystem and do operation like file delete
        """

        state = await self._get_container_state()
        log.info(f"Docker container '{self._name}' fix ownership, state = {state}")
        if state == "stopped" or state == "exited":
            # We need to restart it to fix permissions
            await self.manager.query("POST", f"containers/{self._cid}/start")

        for volume in self._volumes:
            log.debug(
                "Docker container '{name}' [{image}] fix ownership on {path}".format(
                    name=self._name, image=self._image, path=volume
                )
            )

            try:
                process = await asyncio.subprocess.create_subprocess_exec(
                    "docker",
                    "exec",
                    self._cid,
                    "/gns3/bin/busybox",
                    "sh",
                    "-c",
                    "("
                    '/gns3/bin/busybox find "{path}" -depth -print0'
                    " | /gns3/bin/busybox xargs -0 /gns3/bin/busybox stat -c '%a:%u:%g:%n' > \"{path}/.gns3_perms\""
                    ")"
                    ' && /gns3/bin/busybox chmod -R u+rX "{path}"'
                    ' && /gns3/bin/busybox chown {uid}:{gid} -R "{path}"'.format(
                        uid=os.getuid(), gid=os.getgid(), path=volume
                    ),
                )
            except OSError as e:
                raise DockerError(f"Could not fix permissions for {volume}: {e}")
            await process.wait()
            self._permissions_fixed = True

    async def _start_vnc_process(self, restart=False):
        """
        Starts the VNC process.
        """

        self._display = self._get_free_display_port()
        tigervnc_path = shutil.which("Xtigervnc") or shutil.which("Xvnc")

        if not tigervnc_path:
            raise DockerError("Please install TigerVNC server before using VNC support")

        if tigervnc_path:
            with open(os.path.join(self.working_dir, "vnc.log"), "w") as fd:
                self._vnc_process = await asyncio.create_subprocess_exec(tigervnc_path,
                                                                         "-extension", "MIT-SHM",
                                                                         "-geometry", self._console_resolution,
                                                                         "-depth", "16",
                                                                         "-interface", self._manager.port_manager.console_host,
                                                                         "-rfbport", str(self.console),
                                                                         "-AlwaysShared",
                                                                         "-SecurityTypes", "None",
                                                                         ":{}".format(self._display),
                                                                         stdout=fd, stderr=subprocess.STDOUT)

    async def _start_vnc(self):
        """
        Starts a VNC server for this container
        """

        self._display = self._get_free_display_port()
        tigervnc_path = shutil.which("Xtigervnc") or shutil.which("Xvnc")
        if not tigervnc_path:
            raise DockerError("Please install TigerVNC server before using VNC support")
        await self._start_vnc_process()
        x11_socket = os.path.join("/tmp/.X11-unix/", f"X{self._display}")
        try:
            await wait_for_file_creation(x11_socket)
        except asyncio.TimeoutError:
            raise DockerError(f'x11 socket file "{x11_socket}" does not exist')

        if not hasattr(sys, "_called_from_test") or not sys._called_from_test:
            # Start vncconfig for tigervnc clipboard support, connection available only after socket creation.
            tigervncconfig_path = shutil.which("vncconfig")
            if tigervnc_path and tigervncconfig_path:
                self._vncconfig_process = await asyncio.create_subprocess_exec(
                    tigervncconfig_path, "-display", f":{self._display}", "-nowin"
                )

        # sometimes the VNC process can crash
        monitor_process(self._vnc_process, self._vnc_callback)

    def _vnc_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        if returncode != 0 and self._closing is False:
            self.project.emit(
                "log.error",
                {
                    "message": f"The vnc process has stopped with return code {returncode} for node '{self.name}'. Please restart this node."
                },
            )
            self._vnc_process = None

    async def _start_http(self):
        """
        Starts an HTTP tunnel to container localhost. It's not perfect
        but the only way we have to inject network packet is using nc.
        """

        log.debug("Forward HTTP for %s to %d", self.name, self._console_http_port)
        command = [
            "docker",
            "exec",
            "-i",
            self._cid,
            "/gns3/bin/busybox",
            "nc",
            "127.0.0.1",
            str(self._console_http_port),
        ]
        # We replace host and port in the server answer otherwise some link could be broken
        server = AsyncioRawCommandServer(
            command,
            replaces=[
                (
                    b"://127.0.0.1",  # {{HOST}} mean client host
                    b"://{{HOST}}",
                ),
                (
                    f":{self._console_http_port}".encode(),
                    f":{self.console}".encode(),
                ),
            ],
        )
        self._telnet_servers.append(
            await asyncio.start_server(server.run, self._manager.port_manager.console_host, self.console)
        )

    async def _window_size_changed_callback(self, columns, rows):
        """
        Called when the console window size has been changed.
        (when naws is enabled in the Telnet server)

        :param columns: number of columns
        :param rows: number of rows
        """

        # resize the container TTY.
        await self._manager.query("POST", f"containers/{self._cid}/resize?h={rows}&w={columns}")

    async def _start_console(self):
        """
        Starts streaming the console via telnet
        """

        class InputStream:
            def __init__(self):
                self._data = b""

            def write(self, data):
                self._data += data

            async def drain(self):
                if not self.ws.closed:
                    await self.ws.send_bytes(self._data)
                self._data = b""

        output_stream = asyncio.StreamReader()
        input_stream = InputStream()
        telnet = AsyncioTelnetServer(
            reader=output_stream,
            writer=input_stream,
            echo=True,
            naws=True,
            window_size_changed_callback=self._window_size_changed_callback,
        )
        try:
            self._telnet_servers.append(
                await asyncio.start_server(telnet.run, self._manager.port_manager.console_host, self.console)
            )
        except OSError as e:
            raise DockerError(
                f"Could not start Telnet server on socket {self._manager.port_manager.console_host}:{self.console}: {e}"
            )

        self._console_websocket = await self.manager.websocket_query(
            f"containers/{self._cid}/attach/ws?stream=1&stdin=1&stdout=1&stderr=1"
        )
        input_stream.ws = self._console_websocket
        output_stream.feed_data(self.name.encode() + b" console is now available... Press RETURN to get started.\r\n")
        asyncio.ensure_future(self._read_console_output(self._console_websocket, output_stream))

    async def _read_console_output(self, ws, out):
        """
        Reads Websocket and forward it to the telnet

        :param ws: Websocket connection
        :param out: Output stream
        """

        while True:
            msg = await ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                out.feed_data(msg.data.encode())
            elif msg.type == aiohttp.WSMsgType.BINARY:
                out.feed_data(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                log.critical(f"Docker WebSocket Error: {ws.exception()}")
            else:
                out.feed_eof()
                await ws.close()
                break

    async def reset_console(self):
        """
        Reset the console.
        """

        if self._console_websocket:
            await self._console_websocket.close()
        await self._clean_servers()
        await self._start_console()

    async def is_running(self):
        """
        Checks if the container is running.

        :returns: True or False
        :rtype: bool
        """

        state = await self._get_container_state()
        if state == "running":
            return True
        if self.status == "started":  # The container crashed we need to clean
            await self.stop()
        return False

    async def restart(self):
        """
        Restart this Docker container.
        """

        await self.manager.query("POST", f"containers/{self._cid}/restart")
        log.info("Docker container '{name}' [{image}] restarted".format(name=self._name, image=self._image))

    async def _clean_servers(self):
        """
        Clean the list of running console servers
        """

        if len(self._telnet_servers) > 0:
            for telnet_server in self._telnet_servers:
                telnet_server.close()
                await telnet_server.wait_closed()
            self._telnet_servers = []

    async def stop(self):
        """
        Stops this Docker container.
        """

        try:
            if self._console_websocket:
                await self._console_websocket.close()
                self._console_websocket = None
            await self._clean_servers()
            await self._stop_ubridge()

            try:
                state = await self._get_container_state()
            except DockerHttp404Error:
                self.status = "stopped"
                return

            if state == "paused":
                await self.unpause()

            if not self._permissions_fixed:
                await self._fix_permissions()

            state = await self._get_container_state()
            if state != "stopped" or state != "exited":
                # t=5 number of seconds to wait before killing the container
                try:
                    await self.manager.query("POST", f"containers/{self._cid}/stop", params={"t": 5})
                    log.info(f"Docker container '{self._name}' [{self._image}] stopped")
                except DockerHttp304Error:
                    # Container is already stopped
                    pass
        # Ignore runtime error because when closing the server
        except RuntimeError as e:
            log.debug(f"Docker runtime error when closing: {str(e)}")
            return
        self.status = "stopped"

    async def pause(self):
        """
        Pauses this Docker container.
        """

        await self.manager.query("POST", f"containers/{self._cid}/pause")
        self.status = "suspended"
        log.info(f"Docker container '{self._name}' [{self._image}] paused")

    async def unpause(self):
        """
        Unpauses this Docker container.
        """

        await self.manager.query("POST", f"containers/{self._cid}/unpause")
        self.status = "started"
        log.info(f"Docker container '{self._name}' [{self._image}] unpaused")

    async def close(self):
        """
        Closes this Docker container.
        """

        self._closing = True
        if not (await super().close()):
            return False
        await self.reset()

    async def reset(self, release_nio_udp_ports=True):

        try:
            state = await self._get_container_state()
            if state == "paused" or state == "running":
                await self.stop()

            if self.console_type == "vnc":
                if self._vncconfig_process:
                    try:
                        self._vncconfig_process.terminate()
                        await self._vncconfig_process.wait()
                    except ProcessLookupError:
                        pass
                if self._vnc_process:
                    try:
                        self._vnc_process.terminate()
                        await self._vnc_process.wait()
                    except ProcessLookupError:
                        pass

                if self._display:
                    display = f"/tmp/.X11-unix/X{self._display}"
                    try:
                        if os.path.exists(display):
                            os.remove(display)
                    except OSError as e:
                        log.warning(f"Could not remove display {display}: {e}")

            # v – 1/True/true or 0/False/false, Remove the volumes associated to the container. Default false.
            # force - 1/True/true or 0/False/false, Kill then remove the container. Default false.
            try:
                await self.manager.query("DELETE", f"containers/{self._cid}", params={"force": 1, "v": 1})
            except DockerError:
                pass
            log.info("Docker container '{name}' [{image}] removed".format(name=self._name, image=self._image))

            if release_nio_udp_ports:
                for adapter in self._ethernet_adapters:
                    if adapter is not None:
                        for nio in adapter.ports.values():
                            if nio and isinstance(nio, NIOUDP):
                                self.manager.port_manager.release_udp_port(nio.lport, self._project)
        # Ignore runtime error because when closing the server
        except (DockerHttp404Error, RuntimeError) as e:
            log.debug(f"Docker error when closing: {str(e)}")
            return

    async def _add_ubridge_connection(self, nio, adapter_number):
        """
        Creates a connection in uBridge.

        :param nio: NIO instance or None if it's a dummy interface (if an interface is missing in ubridge you can't see it via ifconfig in the container)
        :param adapter_number: adapter number
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(
                    name=self.name, adapter_number=adapter_number
                )
            )

        for index in range(4096):
            if f"tap-gns3-e{index}" not in psutil.net_if_addrs():
                adapter.host_ifc = f"tap-gns3-e{str(index)}"
                break
        if adapter.host_ifc is None:
            raise DockerError(
                "Adapter {adapter_number} couldn't allocate interface on Docker container '{name}'. Too many Docker interfaces already exists".format(
                    name=self.name, adapter_number=adapter_number
                )
            )
        bridge_name = f"bridge{adapter_number}"
        await self._ubridge_send(f"bridge create {bridge_name}")
        self._bridges.add(bridge_name)
        await self._ubridge_send(
            "bridge add_nio_tap bridge{adapter_number} {hostif}".format(
                adapter_number=adapter_number, hostif=adapter.host_ifc
            )
        )
        log.debug("Move container %s adapter %s to namespace %s", self.name, adapter.host_ifc, self._namespace)
        try:
            await self._ubridge_send(
                "docker move_to_ns {ifc} {ns} eth{adapter}".format(
                    ifc=adapter.host_ifc, ns=self._namespace, adapter=adapter_number
                )
            )
        except UbridgeError as e:
            raise UbridgeNamespaceError(e)

        if nio:
            await self._connect_nio(adapter_number, nio)

    async def _get_namespace(self):

        result = await self.manager.query("GET", f"containers/{self._cid}/json")
        return int(result["State"]["Pid"])

    async def _connect_nio(self, adapter_number, nio):

        bridge_name = f"bridge{adapter_number}"
        await self._ubridge_send(
            "bridge add_nio_udp {bridge_name} {lport} {rhost} {rport}".format(
                bridge_name=bridge_name, lport=nio.lport, rhost=nio.rhost, rport=nio.rport
            )
        )

        if nio.capturing:
            await self._ubridge_send(
                'bridge start_capture {bridge_name} "{pcap_file}"'.format(
                    bridge_name=bridge_name, pcap_file=nio.pcap_output_file
                )
            )
        await self._ubridge_send(f"bridge start {bridge_name}")
        await self._ubridge_apply_filters(bridge_name, nio.filters)

    async def adapter_add_nio_binding(self, adapter_number, nio):
        """
        Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(
                    name=self.name, adapter_number=adapter_number
                )
            )

        if self.status == "started" and self.ubridge:
            await self._connect_nio(adapter_number, nio)

        adapter.add_nio(0, nio)
        log.info(
            "Docker container '{name}' [{id}]: {nio} added to adapter {adapter_number}".format(
                name=self.name, id=self._id, nio=nio, adapter_number=adapter_number
            )
        )

    async def adapter_update_nio_binding(self, adapter_number, nio):
        """
        Update an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to update the adapter
        """

        if self.ubridge:
            bridge_name = f"bridge{adapter_number}"
            if bridge_name in self._bridges:
                await self._ubridge_apply_filters(bridge_name, nio.filters)

    async def adapter_remove_nio_binding(self, adapter_number):
        """
        Removes an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker VM '{name}'".format(
                    name=self.name, adapter_number=adapter_number
                )
            )

        await self.stop_capture(adapter_number)
        if self.ubridge:
            nio = adapter.get_nio(0)
            bridge_name = f"bridge{adapter_number}"
            await self._ubridge_send(f"bridge stop {bridge_name}")
            await self._ubridge_send(
                "bridge remove_nio_udp bridge{adapter} {lport} {rhost} {rport}".format(
                    adapter=adapter_number, lport=nio.lport, rhost=nio.rhost, rport=nio.rport
                )
            )

        adapter.remove_nio(0)

        log.info(
            "Docker VM '{name}' [{id}]: {nio} removed from adapter {adapter_number}".format(
                name=self.name, id=self.id, nio=adapter.host_ifc, adapter_number=adapter_number
            )
        )

    def get_nio(self, adapter_number):
        """
        Gets an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except KeyError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker VM '{name}'".format(
                    name=self.name, adapter_number=adapter_number
                )
            )

        nio = adapter.get_nio(0)

        if not nio:
            raise DockerError(f"Adapter {adapter_number} is not connected")

        return nio

    @property
    def adapters(self):
        """
        Returns the number of Ethernet adapters for this Docker VM.

        :returns: number of adapters
        :rtype: int
        """

        return len(self._ethernet_adapters)

    @adapters.setter
    def adapters(self, adapters):
        """
        Sets the number of Ethernet adapters for this Docker container.

        :param adapters: number of adapters
        """

        if len(self._ethernet_adapters) == adapters:
            return

        self._ethernet_adapters.clear()
        for adapter_number in range(0, adapters):
            self._ethernet_adapters.append(EthernetAdapter())

        log.info(
            'Docker container "{name}" [{id}]: number of Ethernet adapters changed to {adapters}'.format(
                name=self._name, id=self._id, adapters=adapters
            )
        )

    async def pull_image(self, image):
        """
        Pulls an image from Docker repository
        """

        def callback(msg):
            self.project.emit("log.info", {"message": msg})

        await self.manager.pull_image(image, progress_callback=callback)

    async def _start_ubridge_capture(self, adapter_number, output_file):
        """
        Starts a packet capture in uBridge.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        adapter = f"bridge{adapter_number}"
        if not self.ubridge:
            raise DockerError("Cannot start the packet capture: uBridge is not running")
        await self._ubridge_send(f'bridge start_capture {adapter} "{output_file}"')

    async def _stop_ubridge_capture(self, adapter_number):
        """
        Stops a packet capture in uBridge.

        :param adapter_number: adapter number
        """

        adapter = f"bridge{adapter_number}"
        if not self.ubridge:
            raise DockerError("Cannot stop the packet capture: uBridge is not running")
        await self._ubridge_send(f"bridge stop_capture {adapter}")

    async def start_capture(self, adapter_number, output_file):
        """
        Starts a packet capture.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        nio = self.get_nio(adapter_number)
        if nio.capturing:
            raise DockerError(f"Packet capture is already activated on adapter {adapter_number}")

        nio.start_packet_capture(output_file)
        if self.status == "started" and self.ubridge:
            await self._start_ubridge_capture(adapter_number, output_file)

        log.info(
            "Docker VM '{name}' [{id}]: starting packet capture on adapter {adapter_number}".format(
                name=self.name, id=self.id, adapter_number=adapter_number
            )
        )

    async def stop_capture(self, adapter_number):
        """
        Stops a packet capture.

        :param adapter_number: adapter number
        """

        nio = self.get_nio(adapter_number)
        if not nio.capturing:
            return
        nio.stop_packet_capture()
        if self.status == "started" and self.ubridge:
            await self._stop_ubridge_capture(adapter_number)

        log.info(
            "Docker VM '{name}' [{id}]: stopping packet capture on adapter {adapter_number}".format(
                name=self.name, id=self.id, adapter_number=adapter_number
            )
        )

    async def _get_log(self):
        """
        Returns the log from the container

        :returns: string
        """

        result = await self.manager.query("GET", f"containers/{self._cid}/logs", params={"stderr": 1, "stdout": 1})
        return result

    async def delete(self):
        """
        Deletes the VM (including all its files).
        """

        await self.close()
        await super().delete()
