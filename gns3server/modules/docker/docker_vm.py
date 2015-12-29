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

from ...ubridge.hypervisor import Hypervisor
from .docker_error import DockerError
from ..base_vm import BaseVM
from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIOUDP
from ...utils.asyncio.telnet_server import AsyncioTelnetServer

import logging
log = logging.getLogger(__name__)


class DockerVM(BaseVM):
    """Docker container implementation.

    :param name: Docker container name
    :param vm_id: Docker VM identifier
    :param project: Project instance
    :param manager: Manager instance
    :param image: Docker image
    """

    def __init__(self, name, vm_id, project, manager, image, console=None, start_command=None, adapters=None, environment=None):
        super().__init__(name, vm_id, project, manager, console=console)

        self._image = image
        self._start_command = start_command
        self._environment = environment
        self._cid = None
        self._ethernet_adapters = []
        self._ubridge_hypervisor = None
        self._temporary_directory = None
        self._telnet_server = None
        self._closed = False

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
            "start_command": self.start_command,
            "environment": self.environment
        }

    @property
    def start_command(self):
        return self._start_command

    @start_command.setter
    def start_command(self, command):
        self._start_command = command

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
    def create(self):
        """Creates the Docker container."""
        params = {
            "Name": self._name,
            "Image": self._image,
            "NetworkDisabled": True,
            "Tty": True,
            "OpenStdin": True,
            "StdinOnce": False,
            "HostConfig": {
                "CapAdd": ["ALL"],
                "Privileged": True
            }
        }
        if self._start_command:
            params.update({"Cmd": shlex.split(self._start_command)})

        if self._environment:
            params.update({"Env": [e.strip() for e in self._environment.split("\n")]})

        images = [i["image"] for i in (yield from self.manager.list_images())]
        if self._image not in images:
            log.info("Image %s is missing pulling it from docker hub", self._image)
            yield from self.pull_image(self._image)

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
        yield from self.remove()
        yield from self.create()

    @asyncio.coroutine
    def start(self):
        """Starts this Docker container."""

        state = yield from self._get_container_state()
        if state == "paused":
            yield from self.unpause()
        else:
            result = yield from self.manager.query("POST", "containers/{}/start".format(self._cid))

            yield from self._start_ubridge()
            for adapter_number in range(0, self.adapters):
                nio = self._ethernet_adapters[adapter_number].get_nio(0)
                if nio:
                    with (yield from self.manager.ubridge_lock):
                        yield from self._add_ubridge_connection(nio, adapter_number)

            yield from self._start_console()

        self.status = "started"
        log.info("Docker container '{name}' [{image}] started listen for telnet on {console}".format(name=self._name, image=self._image, console=self._console))

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

        telnet = AsyncioTelnetServer(reader=output_stream, writer=input_stream)
        self._telnet_server = yield from asyncio.start_server(telnet.run, self._manager.port_manager.console_host, self._console)

        ws = yield from self.manager.websocket_query("containers/{}/attach/ws?stream=1&stdin=1&stdout=1&stderr=1".format(self._cid))
        input_stream.ws = ws

        output_stream.feed_data(self.name.encode() + b" console is now available... Press RETURN to get started.\r\n")

        asyncio.async(self._read_console_output(ws, output_stream))

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
    def stop(self):
        """Stops this Docker container."""

        try:
            if self._ubridge_hypervisor and self._ubridge_hypervisor.is_running():
                yield from self._ubridge_hypervisor.stop()

            state = yield from self._get_container_state()
            if state == "paused":
                yield from self.unpause()

            if self._telnet_server:
                self._telnet_server.close()
                self._telnet_server = None
            # t=5 number of seconds to wait before killing the container
            yield from self.manager.query("POST", "containers/{}/stop".format(self._cid), params={"t": 5})
            log.info("Docker container '{name}' [{image}] stopped".format(
                name=self._name, image=self._image))
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
    def remove(self):
        """Removes this Docker container."""

        try:
            state = yield from self._get_container_state()
            if state == "paused":
                yield from self.unpause()
            if state == "running":
                yield from self.stop()
            yield from self.manager.query("DELETE", "containers/{}".format(self._cid), params={"force": 1})
            log.info("Docker container '{name}' [{image}] removed".format(
                name=self._name, image=self._image))

            if self._console:
                self._manager.port_manager.release_tcp_port(self._console, self._project)
                self._console = None

            for adapter in self._ethernet_adapters:
                if adapter is not None:
                    for nio in adapter.ports.values():
                        if nio and isinstance(nio, NIOUDP):
                            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        # Ignore runtime error because when closing the server
        except RuntimeError as e:
            log.debug("Docker runtime error when closing: {}".format(str(e)))
            return

    @asyncio.coroutine
    def close(self):
        """Closes this Docker container."""

        if self._closed:
            return

        log.debug("Docker container '{name}' [{id}] is closing".format(
            name=self.name, id=self._cid))
        for adapter in self._ethernet_adapters:
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(
                            nio.lport, self._project)

        yield from self.remove()

        log.info("Docker container '{name}' [{id}] closed".format(
            name=self.name, id=self._cid))
        self._closed = True

    @asyncio.coroutine
    def _add_ubridge_connection(self, nio, adapter_number):
        """
        Creates a connection in uBridge.

        :param nio: NIO instance
        :param adapter_number: adapter number
        """
        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise DockerError(
                "Adapter {adapter_number} doesn't exist on Docker container '{name}'".format(name=self.name, adapter_number=adapter_number))

        if nio and isinstance(nio, NIOUDP):
            for index in range(128):
                if "gns3-veth{}ext".format(index) not in psutil.net_if_addrs():
                    adapter.ifc = "eth{}".format(str(index))
                    adapter.host_ifc = "gns3-veth{}ext".format(str(index))
                    adapter.guest_ifc = "gns3-veth{}int".format(str(index))
                    break
            if not hasattr(adapter, "ifc"):
                raise DockerError(
                    "Adapter {adapter_number} couldn't allocate interface on Docker container '{name}'. Too many Docker interfaces already exists".format(
                        name=self.name, adapter_number=adapter_number))
        else:
            raise ValueError("Invalid NIO")

        yield from self._ubridge_hypervisor.send(
            'docker create_veth {hostif} {guestif}'.format(
                guestif=adapter.guest_ifc, hostif=adapter.host_ifc))

        namespace = yield from self._get_namespace()
        log.debug("Move container %s adapter %s to namespace %s", self.name, adapter.guest_ifc, namespace)
        yield from self._ubridge_hypervisor.send(
            'docker move_to_ns {ifc} {ns} eth{adapter}'.format(
                ifc=adapter.guest_ifc, ns=namespace, adapter=adapter_number))

        yield from self._ubridge_hypervisor.send(
            'bridge create bridge{}'.format(adapter_number))
        yield from self._ubridge_hypervisor.send(
            'bridge add_nio_linux_raw bridge{adapter} {ifc}'.format(
                ifc=adapter.host_ifc, adapter=adapter_number))

        if isinstance(nio, NIOUDP):
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
        yield from self._ubridge_hypervisor.send("bridge delete bridge{name}".format(
            name=adapter_number))

        adapter = self._ethernet_adapters[adapter_number]
        yield from self._ubridge_hypervisor.send('docker delete_veth {hostif} {guestif}'.format(guestif=adapter.guest_ifc, hostif=adapter.host_ifc))

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
