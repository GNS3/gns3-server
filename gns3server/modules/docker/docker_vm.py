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
import json
import os

from .docker_error import *
from ..base_vm import BaseVM
from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIOUDP
from ...utils.asyncio.telnet_server import AsyncioTelnetServer
from ...utils.asyncio.raw_command_server import AsyncioRawCommandServer
from ...utils.asyncio import wait_for_file_creation
from ...utils.get_resource import get_resource
from ...ubridge.ubridge_error import UbridgeError, UbridgeNamespaceError


import logging
log = logging.getLogger(__name__)


class DockerVM(BaseVM):
    """Docker container implementation.

    :param name: Docker container name
    :param vm_id: Docker VM identifier
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

    def __init__(self, name, vm_id, project, manager, image,
                 console=None, aux=None, start_command=None,
                 adapters=None, environment=None, console_type="telnet",
                 console_resolution="1024x768", console_http_port=80, console_http_path="/"):
        super().__init__(name, vm_id, project, manager, console=console, aux=aux, allocate_aux=True, console_type=console_type)

        # If no version is specified force latest
        if ":" not in image:
            image = "{}:latest".format(image)
        self._image = image
        self._start_command = start_command
        self._environment = environment
        self._cid = None
        self._ethernet_adapters = []
        self._ubridge_hypervisor = None
        self._temporary_directory = None
        self._telnet_servers = []
        self._x11vnc_process = None
        self._console_resolution = console_resolution
        self._console_http_path = console_http_path
        self._console_http_port = console_http_port
        self._console_websocket = None

        if adapters is None:
            self.adapters = 1
        else:
            self.adapters = adapters

        log.debug(
            "{module}: {name} [{image}] initialized.".format(
                module=self.manager.module_name,
                name=self.name,
                image=self._image))

    def __json__(self):
        return {
            "name": self._name,
            "vm_id": self._id,
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
            "environment": self.environment,
            "vm_directory": self.working_dir
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
        command = command.strip()
        if len(command) == 0:
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
        result = yield from self.manager.query("GET", "containers/{}/json".format(self._cid))

        if result["State"]["Paused"]:
            return "paused"
        if result["State"]["Running"]:
            return "running"
        return "exited"

    @asyncio.coroutine
    def _get_image_informations(self):
        """
        :returns: Dictionnary informations about the container image
        """
        result = yield from self.manager.query("GET", "images/{}/json".format(self._image))
        return result

    def _mount_binds(self, image_infos):
        """
        :returns: Return the path that we need to map to local folders
        """
        binds = []

        binds.append("{}:/gns3:ro".format(get_resource("modules/docker/resources")))

        # We mount our own etc/network
        network_config = self._create_network_config()
        binds.append("{}:/etc/network:rw".format(network_config))

        volumes = image_infos.get("ContainerConfig", {}).get("Volumes")
        if volumes is None:
            return binds
        for volume in volumes.keys():
            source = os.path.join(self.working_dir, os.path.relpath(volume, "/"))
            os.makedirs(source, exist_ok=True)
            binds.append("{}:{}".format(source, volume))

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
            image_infos = yield from self._get_image_informations()
        except DockerHttp404Error:
            log.info("Image %s is missing pulling it from docker hub", self._image)
            yield from self.pull_image(self._image)
            image_infos = yield from self._get_image_informations()

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
            "Env": [],
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
        params["Entrypoint"].insert(0, "/gns3/init.sh")

        # Give the information to the container on how many interface should be inside
        params["Env"].append("GNS3_MAX_ETHERNET=eth{}".format(self.adapters - 1))

        if self._environment:
            params["Env"] += [e.strip() for e in self._environment.split("\n")]

        if self._console_type == "vnc":
            yield from self._start_vnc()
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

        yield from self.close()
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
        else:
            yield from self._clean_servers()

            result = yield from self.manager.query("POST", "containers/{}/start".format(self._cid))

            namespace = yield from self._get_namespace()

            yield from self._start_ubridge()

            for adapter_number in range(0, self.adapters):
                nio = self._ethernet_adapters[adapter_number].get_nio(0)
                with (yield from self.manager.ubridge_lock):
                    try:
                        yield from self._add_ubridge_connection(nio, adapter_number, namespace)
                    except UbridgeNamespaceError:
                        yield from self.stop()

                        # The container can crash soon after the start this mean we can not move the interface to the container namespace
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
        log.info("Docker container '{name}' [{image}] started listen for {console_type} on {console}".format(name=self._name, image=self._image, console=self.console, console_type=self.console_type))

    @asyncio.coroutine
    def _start_aux(self):
        """
        Start an auxilary console
        """

        # We can not use the API because docker doesn't expose a websocket api for exec
        # https://github.com/GNS3/gns3-gui/issues/1039
        process = yield from asyncio.subprocess.create_subprocess_exec(
            "docker", "exec", "-i", self._cid, "/gns3/bin/busybox", "script", "-qfc", "/gns3/bin/busybox sh", "/dev/null",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.PIPE)
        server = AsyncioTelnetServer(reader=process.stdout, writer=process.stdin, binary=True, echo=True)
        self._telnet_servers.append((yield from asyncio.start_server(server.run, self._manager.port_manager.console_host, self.aux)))
        log.debug("Docker container '%s' started listen for auxilary telnet on %d", self.name, self.aux)

    @asyncio.coroutine
    def _start_vnc(self):
        """
        Start a VNC server for this container
        """

        self._display = self._get_free_display_port()
        if shutil.which("Xvfb") is None or shutil.which("x11vnc") is None:
            raise DockerError("Please install Xvfb and x11vnc before using the VNC support")
        self._xvfb_process = yield from asyncio.create_subprocess_exec("Xvfb", "-nolisten", "tcp", ":{}".format(self._display), "-screen", "0", self._console_resolution + "x16")
        self._x11vnc_process = yield from asyncio.create_subprocess_exec("x11vnc", "-forever", "-nopw", "-shared", "-geometry", self._console_resolution, "-display", "WAIT:{}".format(self._display), "-rfbport", str(self.console), "-noncache", "-listen", self._manager.port_manager.console_host)

        x11_socket = os.path.join("/tmp/.X11-unix/", "X{}".format(self._display))
        yield from wait_for_file_creation(x11_socket)

    @asyncio.coroutine
    def _start_http(self):
        """
        Start an HTTP tunnel to container localhost
        """
        log.debug("Forward HTTP for %s to %d", self.name, self._console_http_port)
        command = ["docker", "exec", "-i", self._cid, "/gns3/bin/busybox", "nc", "127.0.0.1", str(self._console_http_port)]
        # We replace the port in the server answer otherwise somelink could be broke
        server = AsyncioRawCommandServer(command, replaces=[
            (
                '{}'.format(self._console_http_port).encode(),
                '{}'.format(self.console).encode(),
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
        Read websocket and forward it to the telnet
        :params ws: Websocket connection
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

    def is_running(self):
        """Checks if the container is running.

        :returns: True or False
        :rtype: bool
        """
        state = yield from self._get_container_state()
        if state == "running":
            return True
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

            if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
                yield from self._ubridge_hypervisor.stop()

            state = yield from self._get_container_state()
            if state == "paused":
                yield from self.unpause()

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

    @asyncio.coroutine
    def pause(self):
        """Pauses this Docker container."""
        yield from self.manager.query("POST", "containers/{}/pause".format(self._cid))
        log.info("Docker container '{name}' [{image}] paused".format(
            name=self._name, image=self._image))
        self.status = "paused"

    @asyncio.coroutine
    def unpause(self):
        """Unpauses this Docker container."""
        yield from self.manager.query("POST", "containers/{}/unpause".format(self._cid))
        log.info("Docker container '{name}' [{image}] unpaused".format(
            name=self._name, image=self._image))
        self.status = "started"

    @asyncio.coroutine
    def close(self):
        """Closes this Docker container."""

        if not (yield from super().close()):
            return False

        try:
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
            state = yield from self._get_container_state()
            if state == "paused" or state == "running":
                yield from self.stop()
            yield from self.manager.query("DELETE", "containers/{}".format(self._cid), params={"force": 1})
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
    def _add_ubridge_connection(self, nio, adapter_number, namespace):
        """
        Creates a connection in uBridge.

        :param nio: NIO instance or None if it's a dummu interface (if an interface is missing in ubridge you can't see it via ifconfig in the container)
        :param adapter_number: adapter number
        :param namespace: Container namespace (pid)
        """
        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(name=self.name, adapter_number=adapter_number))

        for index in range(128):
            if "veth-gns3-ext{}".format(index) not in psutil.net_if_addrs():
                adapter.ifc = "eth{}".format(str(index))
                adapter.host_ifc = "veth-gns3-ext{}".format(str(index))
                adapter.guest_ifc = "veth-gns3-int{}".format(str(index))
                break
        if not hasattr(adapter, "ifc"):
            raise DockerError(
                "Adapter {adapter_number} couldn't allocate interface on Docker container '{name}'. Too many Docker interfaces already exists".format(
                    name=self.name, adapter_number=adapter_number))

        yield from self._ubridge_hypervisor.send(
            'docker create_veth {hostif} {guestif}'.format(
                guestif=adapter.guest_ifc, hostif=adapter.host_ifc))

        log.debug("Move container %s adapter %s to namespace %s", self.name, adapter.guest_ifc, namespace)
        try:
            yield from self._ubridge_hypervisor.send(
                'docker move_to_ns {ifc} {ns} eth{adapter}'.format(
                    ifc=adapter.guest_ifc, ns=namespace, adapter=adapter_number))
        except UbridgeError as e:
            raise UbridgeNamespaceError(e)

        if isinstance(nio, NIOUDP):
            yield from self._ubridge_hypervisor.send(
                'bridge create bridge{}'.format(adapter_number))
            yield from self._ubridge_hypervisor.send(
                'bridge add_nio_linux_raw bridge{adapter} {ifc}'.format(
                    ifc=adapter.host_ifc, adapter=adapter_number))

            yield from self._ubridge_hypervisor.send(
                'bridge add_nio_udp bridge{adapter} {lport} {rhost} {rport}'.format(
                    adapter=adapter_number, lport=nio.lport, rhost=nio.rhost,
                    rport=nio.rport))

            if nio.capturing:
                yield from self._ubridge_hypervisor.send(
                    'bridge start_capture bridge{adapter} "{pcap_file}"'.format(
                        adapter=adapter_number, pcap_file=nio.pcap_output_file))

            yield from self._ubridge_hypervisor.send(
                'bridge start bridge{adapter}'.format(adapter=adapter_number))

    def _delete_ubridge_connection(self, adapter_number):
        """Deletes a connection in uBridge.

        :param adapter_number: adapter number
        """
        if not self._ubridge_hypervisor or not self._ubridge_hypervisor.is_running():
            return

        adapter = self._ethernet_adapters[adapter_number]

        try:
            yield from self._ubridge_hypervisor.send("bridge delete bridge{name}".format(
                name=adapter_number))
        except UbridgeError as e:
            log.debug(str(e))
        try:
            yield from self._ubridge_hypervisor.send('docker delete_veth {hostif}'.format(hostif=adapter.host_ifc))
        except UbridgeError as e:
            log.debug(str(e))

    @asyncio.coroutine
    def _get_namespace(self):
        result = yield from self.manager.query("GET", "containers/{}/json".format(self._cid))
        return int(result['State']['Pid'])

    @asyncio.coroutine
    def adapter_add_nio_binding(self, adapter_number, nio):
        """Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the slot/port
        """
        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(
                    name=self.name, adapter_number=adapter_number))

        adapter.add_nio(0, nio)
        log.info(
            "Docker container '{name}' [{id}]: {nio} added to adapter {adapter_number}".format(
                name=self.name,
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
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker VM '{name}'".format(
                    name=self.name, adapter_number=adapter_number))

        adapter.remove_nio(0)
        yield from self._delete_ubridge_connection(adapter_number)

        log.info(
            "Docker VM '{name}' [{id}]: {nio} removed from adapter {adapter_number}".format(
                name=self.name, id=self.id, nio=adapter.host_ifc,
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

        log.info(
            'Docker container "{name}" [{id}]: number of Ethernet adapters changed to {adapters}'.format(
                name=self._name,
                id=self._id,
                adapters=adapters))

    @asyncio.coroutine
    def pull_image(self, image):
        """
        Pull image from docker repository
        """
        log.info("Pull %s from docker hub", image)
        response = yield from self.manager.http_query("POST", "images/create", params={"fromImage": image})
        # The pull api will stream status via an HTTP JSON stream
        content = ""
        while True:
            chunk = yield from response.content.read(1024)
            if not chunk:
                break
            content += chunk.decode("utf-8")

            try:
                while True:
                    content = content.lstrip(" \r\n\t")
                    answer, index = json.JSONDecoder().raw_decode(content)
                    if "progress" in answer:
                        self.project.emit("log.info", {"message": "Pulling image {}:{}: {}".format(self._image, answer["id"], answer["progress"])})
                    content = content[index:]
            except ValueError:  # Partial JSON
                pass
        self.project.emit("log.info", {"message": "Success pulling image {}".format(self._image)})

    @asyncio.coroutine
    def _start_ubridge_capture(self, adapter_number, output_file):
        """
        Start a packet capture in uBridge.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        adapter = "bridge{}".format(adapter_number)
        if not self._ubridge_hypervisor or not self._ubridge_hypervisor.is_running():
            raise DockerError("Cannot start the packet capture: uBridge is not running")
        yield from self._ubridge_hypervisor.send('bridge start_capture {name} "{output_file}"'.format(name=adapter, output_file=output_file))

    @asyncio.coroutine
    def _stop_ubridge_capture(self, adapter_number):
        """
        Stop a packet capture in uBridge.

        :param adapter_number: adapter number
        """

        adapter = "bridge{}".format(adapter_number)
        if not self._ubridge_hypervisor or not self._ubridge_hypervisor.is_running():
            raise DockerError("Cannot stop the packet capture: uBridge is not running")
        yield from self._ubridge_hypervisor.send("bridge stop_capture {name}".format(name=adapter))

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

        if self.status == "started":
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

        if self.status == "started":
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
