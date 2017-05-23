# -*- coding: utf-8 -*-
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

import asyncio
import shutil
import psutil
import shlex
import aiohttp
import os

from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer
from gns3server.utils.asyncio.raw_command_server import AsyncioRawCommandServer
from gns3server.utils.asyncio import wait_for_file_creation
from gns3server.utils.get_resource import get_resource

from gns3server.ubridge.ubridge_error import UbridgeError, UbridgeNamespaceError
from ..base_node import BaseNode

from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIOUDP
from .docker_error import (
    DockerError,
    DockerHttp304Error,
    DockerHttp404Error
)

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
    :param console_type: Console type
    :param aux: TCP aux console port
    :param console_resolution: Resolution of the VNC display
    :param console_http_port: Port to redirect HTTP queries
    :param console_http_path: Url part with the path of the web interface
    """

    def __init__(self, name, node_id, project, manager, image, console=None, aux=None, start_command=None,
                 adapters=None, environment=None, console_type="telnet", console_resolution="1024x768",
                 console_http_port=80, console_http_path="/"):

        super().__init__(name, node_id, project, manager, console=console, aux=aux, allocate_aux=True, console_type=console_type)

        # force the latest image if no version is specified
        if ":" not in image:
            image = "{}:latest".format(image)
        self._image = image
        self._start_command = start_command
        self._environment = environment
        self._cid = None
        self._ethernet_adapters = []
        self._temporary_directory = None
        self._telnet_servers = []
        self._x11vnc_process = None
        self._console_resolution = console_resolution
        self._console_http_path = console_http_path
        self._console_http_port = console_http_port
        self._console_websocket = None
        self._volumes = []

        if adapters is None:
            self.adapters = 1
        else:
            self.adapters = adapters

        log.debug("{module}: {name} [{image}] initialized.".format(module=self.manager.module_name,
                                                                   name=self.name,
                                                                   image=self._image))

    def __json__(self):
        return {
            "name": self._name,
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
            "start_command": self.start_command,
            "status": self.status,
            "environment": self.environment,
            "node_directory": self.working_dir
        }

    def _get_free_display_port(self):
        """
        Search a free display port
        """
        display = 100
        if not os.path.exists("/tmp/.X11-unix/"):
            return display
        while True:
            if not os.path.exists("/tmp/.X11-unix/X{}".format(display)):
                return display
            display += 1

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

    @asyncio.coroutine
    def _get_container_state(self):
        """Returns the container state (e.g. running, paused etc.)

        :returns: state
        :rtype: str
        """
        try:
            result = yield from self.manager.query("GET", "containers/{}/json".format(self._cid))
        except DockerError:
            return "exited"

        if result["State"]["Paused"]:
            return "paused"
        if result["State"]["Running"]:
            return "running"
        return "exited"

    @asyncio.coroutine
    def _get_image_information(self):
        """
        :returns: Dictionary information about the container image
        """
        result = yield from self.manager.query("GET", "images/{}/json".format(self._image))
        return result

    def _mount_binds(self, image_infos):
        """
        :returns: Return the path that we need to map to local folders
        """
        ressources = get_resource("compute/docker/resources")
        if not os.path.exists(ressources):
            raise DockerError("{} is missing can't start Docker containers".format(ressources))
        binds = ["{}:/gns3:ro".format(ressources)]

        # We mount our own etc/network
        network_config = self._create_network_config()
        binds.append("{}:/gns3volumes/etc/network:rw".format(network_config))

        self._volumes = ["/etc/network"]

        volumes = image_infos.get("Config", {}).get("Volumes")
        if volumes is None:
            return binds
        for volume in volumes.keys():
            source = os.path.join(self.working_dir, os.path.relpath(volume, "/"))
            os.makedirs(source, exist_ok=True)
            binds.append("{}:/gns3volumes{}".format(source, volume))
            self._volumes.append(volume)

        return binds

    def _create_network_config(self):
        """
        If network config is empty we create a sample config
        """
        path = os.path.join(self.working_dir, "etc", "network")
        os.makedirs(path, exist_ok=True)
        os.makedirs(os.path.join(path, "if-up.d"), exist_ok=True)
        os.makedirs(os.path.join(path, "if-down.d"), exist_ok=True)
        os.makedirs(os.path.join(path, "if-pre-up.d"), exist_ok=True)
        os.makedirs(os.path.join(path, "if-post-down.d"), exist_ok=True)

        if not os.path.exists(os.path.join(path, "interfaces")):
            with open(os.path.join(path, "interfaces"), "w+") as f:
                f.write("""#
# This is a sample network config uncomment lines to configure the network
#

""")
                for adapter in range(0, self.adapters):
                    f.write("""
# Static config for eth{adapter}
#auto eth{adapter}
#iface eth{adapter} inet static
#\taddress 192.168.{adapter}.2
#\tnetmask 255.255.255.0
#\tgateway 192.168.{adapter}.1
#\tup echo nameserver 192.168.{adapter}.1 > /etc/resolv.conf

# DHCP config for eth{adapter}
# auto eth{adapter}
# iface eth{adapter} inet dhcp""".format(adapter=adapter))
        return path

    @asyncio.coroutine
    def create(self):
        """Creates the Docker container."""

        try:
            image_infos = yield from self._get_image_information()
        except DockerHttp404Error:
            log.info("Image %s is missing pulling it from docker hub", self._image)
            yield from self.pull_image(self._image)
            image_infos = yield from self._get_image_information()
            if image_infos is None:
                raise DockerError("Can't get image informations, please try again.")

        params = {
            "Hostname": self._name,
            "Name": self._name,
            "Image": self._image,
            "NetworkDisabled": True,
            "Tty": True,
            "OpenStdin": True,
            "StdinOnce": False,
            "HostConfig": {
                "CapAdd": ["ALL"],
                "Privileged": True,
                "Binds": self._mount_binds(image_infos)
            },
            "Volumes": {},
            "Env": ["container=docker"],  # Systemd compliant: https://github.com/GNS3/gns3-server/issues/573
            "Cmd": [],
            "Entrypoint": image_infos.get("Config", {"Entrypoint": []})["Entrypoint"]
        }

        if params["Entrypoint"] is None:
            params["Entrypoint"] = []
        if self._start_command:
            params["Cmd"] = shlex.split(self._start_command)
        if len(params["Cmd"]) == 0:
            params["Cmd"] = image_infos.get("Config", {"Cmd": []})["Cmd"]
            if params["Cmd"] is None:
                params["Cmd"] = []
        if len(params["Cmd"]) == 0 and len(params["Entrypoint"]) == 0:
            params["Cmd"] = ["/bin/sh"]
        params["Entrypoint"].insert(0, "/gns3/init.sh")  # FIXME /gns3/init.sh is not found?

        # Give the information to the container on how many interface should be inside
        params["Env"].append("GNS3_MAX_ETHERNET=eth{}".format(self.adapters - 1))
        # Give the information to the container the list of volume path mounted
        params["Env"].append("GNS3_VOLUMES={}".format(":".join(self._volumes)))

        if self._environment:
            params["Env"] += [e.strip() for e in self._environment.split("\n")]

        if self._console_type == "vnc":
            yield from self._start_vnc()
            params["Env"].append("QT_GRAPHICSSYSTEM=native")  # To fix a Qt issue: https://github.com/GNS3/gns3-server/issues/556
            params["Env"].append("DISPLAY=:{}".format(self._display))
            params["HostConfig"]["Binds"].append("/tmp/.X11-unix/:/tmp/.X11-unix/")

        result = yield from self.manager.query("POST", "containers/create", data=params)
        self._cid = result['Id']
        log.info("Docker container '{name}' [{id}] created".format(
            name=self._name, id=self._id))
        return True

    @asyncio.coroutine
    def update(self):
        """
        Destroy an recreate the container with the new settings
        """
        # We need to save the console and state and restore it
        console = self.console
        aux = self.aux
        state = yield from self._get_container_state()

        yield from self.reset()
        yield from self.create()
        self.console = console
        self.aux = aux
        if state == "running":
            yield from self.start()

    @asyncio.coroutine
    def start(self):
        """Starts this Docker container."""

        state = yield from self._get_container_state()
        if state == "paused":
            yield from self.unpause()
        elif state == "running":
            return
        else:
            yield from self._clean_servers()

            yield from self.manager.query("POST", "containers/{}/start".format(self._cid))
            self._namespace = yield from self._get_namespace()

            yield from self._start_ubridge()

            for adapter_number in range(0, self.adapters):
                nio = self._ethernet_adapters[adapter_number].get_nio(0)
                with (yield from self.manager.ubridge_lock):
                    try:
                        yield from self._add_ubridge_connection(nio, adapter_number)
                    except UbridgeNamespaceError:
                        log.error("Container %s failed to start", self.name)
                        yield from self.stop()

                        # The container can crash soon after the start, this means we can not move the interface to the container namespace
                        logdata = yield from self._get_log()
                        for line in logdata.split('\n'):
                            log.error(line)
                        raise DockerError(logdata)

            if self.console_type == "telnet":
                yield from self._start_console()
            elif self.console_type == "http" or self.console_type == "https":
                yield from self._start_http()

            if self.allocate_aux:
                yield from self._start_aux()

        self.status = "started"
        log.info("Docker container '{name}' [{image}] started listen for {console_type} on {console}".format(name=self._name,
                                                                                                             image=self._image,
                                                                                                             console=self.console,
                                                                                                             console_type=self.console_type))

    @asyncio.coroutine
    def _start_aux(self):
        """
        Start an auxilary console
        """

        # We can not use the API because docker doesn't expose a websocket api for exec
        # https://github.com/GNS3/gns3-gui/issues/1039
        process = yield from asyncio.subprocess.create_subprocess_exec(
            "docker", "exec", "-i", self._cid, "/gns3/bin/busybox", "script", "-qfc", "while true; do TERM=vt100 /gns3/bin/busybox sh; done", "/dev/null",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.PIPE)
        server = AsyncioTelnetServer(reader=process.stdout, writer=process.stdin, binary=True, echo=True)
        self._telnet_servers.append((yield from asyncio.start_server(server.run, self._manager.port_manager.console_host, self.aux)))
        log.debug("Docker container '%s' started listen for auxilary telnet on %d", self.name, self.aux)

    @asyncio.coroutine
    def _fix_permissions(self):
        """
        Because docker run as root we need to fix permission and ownership to allow user to interact
        with it from their filesystem and do operation like file delete
        """
        for volume in self._volumes:
            log.debug("Docker container '{name}' [{image}] fix ownership on {path}".format(
                name=self._name, image=self._image, path=volume))
            process = yield from asyncio.subprocess.create_subprocess_exec("docker",
                                                                           "exec",
                                                                           self._cid,
                                                                           "/gns3/bin/busybox",
                                                                           "sh",
                                                                           "-c",
                                                                           "(/gns3/bin/busybox find \"{path}\" -depth -print0 | /gns3/bin/busybox xargs -0 /gns3/bin/busybox stat -c '%a:%u:%g:%n' > \"{path}/.gns3_perms\") && /gns3/bin/busybox chmod -R u+rX \"{path}\" && /gns3/bin/busybox chown {uid}:{gid} -R \"{path}\"".format(uid=os.getuid(), gid=os.getgid(), path=volume))
            yield from process.wait()

    @asyncio.coroutine
    def _start_vnc(self):
        """
        Start a VNC server for this container
        """

        self._display = self._get_free_display_port()
        if shutil.which("Xvfb") is None or shutil.which("x11vnc") is None:
            raise DockerError("Please install Xvfb and x11vnc before using the VNC support")
        self._xvfb_process = yield from asyncio.create_subprocess_exec("Xvfb", "-nolisten", "tcp", ":{}".format(self._display), "-screen", "0", self._console_resolution + "x16")
        # We pass a port for TCPV6 due to a crash in X11VNC if not here: https://github.com/GNS3/gns3-server/issues/569
        self._x11vnc_process = yield from asyncio.create_subprocess_exec("x11vnc", "-forever", "-nopw", "-shared", "-geometry", self._console_resolution, "-display", "WAIT:{}".format(self._display), "-rfbport", str(self.console), "-rfbportv6", str(self.console), "-noncache", "-listen", self._manager.port_manager.console_host)

        x11_socket = os.path.join("/tmp/.X11-unix/", "X{}".format(self._display))
        yield from wait_for_file_creation(x11_socket)

    @asyncio.coroutine
    def _start_http(self):
        """
        Start an HTTP tunnel to container localhost. It's not perfect
        but the only way we have to inject network packet is using nc.
        """
        log.debug("Forward HTTP for %s to %d", self.name, self._console_http_port)
        command = ["docker", "exec", "-i", self._cid, "/gns3/bin/busybox", "nc", "127.0.0.1", str(self._console_http_port)]
        # We replace host and port in the server answer otherwise some link could be broken
        server = AsyncioRawCommandServer(command, replaces=[
            (
                '://127.0.0.1'.encode(),  # {{HOST}} mean client host
                '://{{HOST}}'.encode(),
            ),
            (
                ':{}'.format(self._console_http_port).encode(),
                ':{}'.format(self.console).encode(),
            )
        ])
        self._telnet_servers.append((yield from asyncio.start_server(server.run, self._manager.port_manager.console_host, self.console)))

    @asyncio.coroutine
    def _start_console(self):
        """
        Start streaming the console via telnet
        """

        class InputStream:

            def __init__(self):
                self._data = b""

            def write(self, data):
                self._data += data

            @asyncio.coroutine
            def drain(self):
                if not self.ws.closed:
                    self.ws.send_bytes(self._data)
                self._data = b""

        output_stream = asyncio.StreamReader()
        input_stream = InputStream()

        telnet = AsyncioTelnetServer(reader=output_stream, writer=input_stream, echo=True)
        self._telnet_servers.append((yield from asyncio.start_server(telnet.run, self._manager.port_manager.console_host, self.console)))

        self._console_websocket = yield from self.manager.websocket_query("containers/{}/attach/ws?stream=1&stdin=1&stdout=1&stderr=1".format(self._cid))
        input_stream.ws = self._console_websocket

        output_stream.feed_data(self.name.encode() + b" console is now available... Press RETURN to get started.\r\n")

        asyncio.async(self._read_console_output(self._console_websocket, output_stream))

    @asyncio.coroutine
    def _read_console_output(self, ws, out):
        """
        Read Websocket and forward it to the telnet

        :param ws: Websocket connection
        :param out: Output stream
        """

        while True:
            msg = yield from ws.receive()
            if msg.tp == aiohttp.MsgType.text:
                out.feed_data(msg.data.encode())
            else:
                out.feed_eof()
                ws.close()
                break
        yield from self.stop()

    @asyncio.coroutine
    def is_running(self):
        """Checks if the container is running.

        :returns: True or False
        :rtype: bool
        """
        state = yield from self._get_container_state()
        if state == "running":
            return True
        if self.status == "started":  # The container crashed we need to clean
            yield from self.stop()
        return False

    @asyncio.coroutine
    def restart(self):
        """Restart this Docker container."""
        yield from self.manager.query("POST", "containers/{}/restart".format(self._cid))
        log.info("Docker container '{name}' [{image}] restarted".format(
            name=self._name, image=self._image))

    @asyncio.coroutine
    def _clean_servers(self):
        """
        Clean the list of running console servers
        """
        if len(self._telnet_servers) > 0:
            for telnet_server in self._telnet_servers:
                telnet_server.close()
                yield from telnet_server.wait_closed()
            self._telnet_servers = []

    @asyncio.coroutine
    def stop(self):
        """Stops this Docker container."""

        try:
            yield from self._clean_servers()
            yield from self._stop_ubridge()

            try:
                state = yield from self._get_container_state()
            except DockerHttp404Error:
                state = "stopped"

            if state == "paused":
                yield from self.unpause()

            if state != "stopped":
                yield from self._fix_permissions()
                # t=5 number of seconds to wait before killing the container
                try:
                    yield from self.manager.query("POST", "containers/{}/stop".format(self._cid), params={"t": 5})
                    log.info("Docker container '{name}' [{image}] stopped".format(
                        name=self._name, image=self._image))
                except DockerHttp304Error:
                    # Container is already stopped
                    pass
        # Ignore runtime error because when closing the server
        except RuntimeError as e:
            log.debug("Docker runtime error when closing: {}".format(str(e)))
            return
        self.status = "stopped"

    @asyncio.coroutine
    def pause(self):
        """Pauses this Docker container."""
        yield from self.manager.query("POST", "containers/{}/pause".format(self._cid))
        self.status = "suspended"
        log.info("Docker container '{name}' [{image}] paused".format(name=self._name, image=self._image))

    @asyncio.coroutine
    def unpause(self):
        """Unpauses this Docker container."""
        yield from self.manager.query("POST", "containers/{}/unpause".format(self._cid))
        self.status = "started"
        log.info("Docker container '{name}' [{image}] unpaused".format(name=self._name, image=self._image))

    @asyncio.coroutine
    def close(self):
        """Closes this Docker container."""

        if not (yield from super().close()):
            return False
        yield from self.reset()

    @asyncio.coroutine
    def reset(self):
        try:
            state = yield from self._get_container_state()
            if state == "paused" or state == "running":
                yield from self.stop()
            if self.console_type == "vnc":
                if self._x11vnc_process:
                    try:
                        self._x11vnc_process.terminate()
                        yield from self._x11vnc_process.wait()
                    except ProcessLookupError:
                        pass
                    try:
                        self._xvfb_process.terminate()
                        yield from self._xvfb_process.wait()
                    except ProcessLookupError:
                        pass
            # v – 1/True/true or 0/False/false, Remove the volumes associated to the container. Default false.
            # force - 1/True/true or 0/False/false, Kill then remove the container. Default false.
            try:
                yield from self.manager.query("DELETE", "containers/{}".format(self._cid), params={"force": 1, "v": 1})
            except DockerError:
                pass
            log.info("Docker container '{name}' [{image}] removed".format(
                name=self._name, image=self._image))

            for adapter in self._ethernet_adapters:
                if adapter is not None:
                    for nio in adapter.ports.values():
                        if nio and isinstance(nio, NIOUDP):
                            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        # Ignore runtime error because when closing the server
        except (DockerHttp404Error, RuntimeError) as e:
            log.debug("Docker error when closing: {}".format(str(e)))
            return

    @asyncio.coroutine
    def _add_ubridge_connection(self, nio, adapter_number):
        """
        Creates a connection in uBridge.

        :param nio: NIO instance or None if it's a dummy interface (if an interface is missing in ubridge you can't see it via ifconfig in the container)
        :param adapter_number: adapter number
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError("Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(name=self.name,
                                                                                                           adapter_number=adapter_number))

        for index in range(4096):
            if "tap-gns3-e{}".format(index) not in psutil.net_if_addrs():
                adapter.host_ifc = "tap-gns3-e{}".format(str(index))
                break
        if adapter.host_ifc is None:
            raise DockerError("Adapter {adapter_number} couldn't allocate interface on Docker container '{name}'. Too many Docker interfaces already exists".format(name=self.name,
                                                                                                                                                                    adapter_number=adapter_number))

        yield from self._ubridge_send('bridge create bridge{}'.format(adapter_number))
        yield from self._ubridge_send('bridge add_nio_tap bridge{adapter_number} {hostif}'.format(adapter_number=adapter_number,
                                                                                                  hostif=adapter.host_ifc))
        log.debug("Move container %s adapter %s to namespace %s", self.name, adapter.host_ifc, self._namespace)
        try:
            yield from self._ubridge_send('docker move_to_ns {ifc} {ns} eth{adapter}'.format(ifc=adapter.host_ifc,
                                                                                             ns=self._namespace,
                                                                                             adapter=adapter_number))
        except UbridgeError as e:
            raise UbridgeNamespaceError(e)

        if nio:
            yield from self._connect_nio(adapter_number, nio)

    @asyncio.coroutine
    def _get_namespace(self):
        result = yield from self.manager.query("GET", "containers/{}/json".format(self._cid))
        return int(result['State']['Pid'])

    @asyncio.coroutine
    def _connect_nio(self, adapter_number, nio):
        yield from self._ubridge_send('bridge add_nio_udp bridge{adapter} {lport} {rhost} {rport}'.format(adapter=adapter_number,
                                                                                                          lport=nio.lport,
                                                                                                          rhost=nio.rhost,
                                                                                                          rport=nio.rport))

        if nio.capturing:
            yield from self._ubridge_send('bridge start_capture bridge{adapter} "{pcap_file}"'.format(adapter=adapter_number,
                                                                                                      pcap_file=nio.pcap_output_file))
        yield from self._ubridge_send('bridge start bridge{adapter}'.format(adapter=adapter_number))

    @asyncio.coroutine
    def adapter_add_nio_binding(self, adapter_number, nio):
        """Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the slot/port
        """
        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError("Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(name=self.name,
                                                                                                           adapter_number=adapter_number))

        if self.status == "started" and self.ubridge:
            yield from self._connect_nio(adapter_number, nio)

        adapter.add_nio(0, nio)
        log.info("Docker container '{name}' [{id}]: {nio} added to adapter {adapter_number}".format(name=self.name,
                                                                                                    id=self._id,
                                                                                                    nio=nio,
                                                                                                    adapter_number=adapter_number))

    @asyncio.coroutine
    def adapter_remove_nio_binding(self, adapter_number):
        """
        Removes an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """
        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError("Adapter {adapter_number} doesn't exist on Docker VM '{name}'".format(name=self.name,
                                                                                                    adapter_number=adapter_number))

        if self.ubridge:
            nio = adapter.get_nio(0)
            yield from self._ubridge_send("bridge stop bridge{name}".format(name=adapter_number))
            yield from self._ubridge_send('bridge remove_nio_udp bridge{adapter} {lport} {rhost} {rport}'.format(adapter=adapter_number,
                                                                                                                 lport=nio.lport,
                                                                                                                 rhost=nio.rhost,
                                                                                                                 rport=nio.rport))

        adapter.remove_nio(0)

        log.info("Docker VM '{name}' [{id}]: {nio} removed from adapter {adapter_number}".format(name=self.name,
                                                                                                 id=self.id,
                                                                                                 nio=adapter.host_ifc,
                                                                                                 adapter_number=adapter_number))

    @property
    def adapters(self):
        """Returns the number of Ethernet adapters for this Docker VM.

        :returns: number of adapters
        :rtype: int
        """
        return len(self._ethernet_adapters)

    @adapters.setter
    def adapters(self, adapters):
        """Sets the number of Ethernet adapters for this Docker container.

        :param adapters: number of adapters
        """

        if len(self._ethernet_adapters) == adapters:
            return

        self._ethernet_adapters.clear()
        for adapter_number in range(0, adapters):
            self._ethernet_adapters.append(EthernetAdapter())

        log.info('Docker container "{name}" [{id}]: number of Ethernet adapters changed to {adapters}'.format(name=self._name,
                                                                                                              id=self._id,
                                                                                                              adapters=adapters))

    @asyncio.coroutine
    def pull_image(self, image):
        """
        Pull image from docker repository
        """
        def callback(msg):
            self.project.emit("log.info", {"message": msg})
        yield from self.manager.pull_image(image, progress_callback=callback)

    @asyncio.coroutine
    def _start_ubridge_capture(self, adapter_number, output_file):
        """
        Start a packet capture in uBridge.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        adapter = "bridge{}".format(adapter_number)
        if not self.ubridge:
            raise DockerError("Cannot start the packet capture: uBridge is not running")
        yield from self._ubridge_send('bridge start_capture {name} "{output_file}"'.format(name=adapter, output_file=output_file))

    @asyncio.coroutine
    def _stop_ubridge_capture(self, adapter_number):
        """
        Stop a packet capture in uBridge.

        :param adapter_number: adapter number
        """

        adapter = "bridge{}".format(adapter_number)
        if not self.ubridge:
            raise DockerError("Cannot stop the packet capture: uBridge is not running")
        yield from self._ubridge_send("bridge stop_capture {name}".format(name=adapter))

    @asyncio.coroutine
    def start_capture(self, adapter_number, output_file):
        """
        Starts a packet capture.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except KeyError:
            raise DockerError("Adapter {adapter_number} doesn't exist on Docker VM '{name}'".format(name=self.name,
                                                                                                    adapter_number=adapter_number))

        nio = adapter.get_nio(0)

        if not nio:
            raise DockerError("Adapter {} is not connected".format(adapter_number))

        if nio.capturing:
            raise DockerError("Packet capture is already activated on adapter {adapter_number}".format(adapter_number=adapter_number))

        nio.startPacketCapture(output_file)

        if self.status == "started" and self.ubridge:
            yield from self._start_ubridge_capture(adapter_number, output_file)

        log.info("Docker VM '{name}' [{id}]: starting packet capture on adapter {adapter_number}".format(name=self.name,
                                                                                                         id=self.id,
                                                                                                         adapter_number=adapter_number))

    def stop_capture(self, adapter_number):
        """
        Stops a packet capture.

        :param adapter_number: adapter number
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except KeyError:
            raise DockerError("Adapter {adapter_number} doesn't exist on Docker VM '{name}'".format(name=self.name,
                                                                                                    adapter_number=adapter_number))

        nio = adapter.get_nio(0)

        if not nio:
            raise DockerError("Adapter {} is not connected".format(adapter_number))

        nio.stopPacketCapture()

        if self.status == "started" and self.ubridge:
            yield from self._stop_ubridge_capture(adapter_number)

        log.info("Docker VM '{name}' [{id}]: stopping packet capture on adapter {adapter_number}".format(name=self.name,
                                                                                                         id=self.id,
                                                                                                         adapter_number=adapter_number))

    @asyncio.coroutine
    def _get_log(self):
        """
        Return the log from the container

        :returns: string
        """

        result = yield from self.manager.query("GET", "containers/{}/logs".format(self._cid), params={"stderr": 1, "stdout": 1})
        return result

    @asyncio.coroutine
    def delete(self):
        """
        Delete the VM (including all its files).
        """
        yield from self.close()
        yield from super().delete()
