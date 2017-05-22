#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import ipaddress
import aiohttp
import asyncio
import socket
import json
import uuid
import sys
import io
from operator import itemgetter

from ..utils import parse_version
from ..utils.images import list_images
from ..utils.asyncio import locked_coroutine
from ..controller.controller_error import ControllerError
from ..version import __version__


import logging
log = logging.getLogger(__name__)


class ComputeError(ControllerError):
    pass


class ComputeConflict(aiohttp.web.HTTPConflict):
    """
    Raise when the compute send a 409 that we can handle

    :param response: The response of the compute
    """

    def __init__(self, response):
        super().__init__(text=response["message"])
        self.response = response


class Timeout(aiohttp.Timeout):
    """
    Could be removed with aiohttp 0.22 that support None timeout
    """

    def __enter__(self):
        if self._timeout:
            return super().__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._timeout:
            return super().__exit__(exc_type, exc_val, exc_tb)
        return self


class Compute:
    """
    A GNS3 compute.
    """

    def __init__(self, compute_id, controller=None, protocol="http", host="localhost", port=3080, user=None, password=None, name=None, console_host=None):
        self._http_session = None
        assert controller is not None
        log.info("Create compute %s", compute_id)

        if compute_id is None:
            self._id = str(uuid.uuid4())
        else:
            self._id = compute_id

        self.protocol = protocol
        self._console_host = console_host
        self.host = host
        self.port = port
        self._user = None
        self._password = None
        self._connected = False
        self._closed = False  # Close mean we are destroying the compute node
        self._controller = controller
        self._set_auth(user, password)
        self._cpu_usage_percent = None
        self._memory_usage_percent = None
        self._capabilities = {
            "version": None,
            "node_types": []
        }
        self.name = name
        # Websocket for notifications
        self._ws = None

        # Cache of interfaces on remote host
        self._interfaces_cache = None

        self._connection_failure = 0

    def _session(self):
        if self._http_session is None or self._http_session.closed is True:
            self._http_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=None, force_close=True))
        return self._http_session

    def __del__(self):
        if self._http_session:
            self._http_session.close()

    def _set_auth(self, user, password):
        """
        Set authentication parameters
        """
        if user is None or len(user.strip()) == 0:
            self._user = None
            self._password = None
            self._auth = None
        else:
            self._user = user.strip()
            if password:
                self._password = password.strip()
                self._auth = aiohttp.BasicAuth(self._user, self._password, "utf-8")
            else:
                self._password = None
                self._auth = aiohttp.BasicAuth(self._user, "")

    @asyncio.coroutine
    def interfaces(self):
        """
        Get the list of network on compute
        """
        if not self._interfaces_cache:
            response = yield from self.get("/network/interfaces")
            self._interfaces_cache = response.json
        return self._interfaces_cache

    @asyncio.coroutine
    def update(self, **kwargs):
        for kw in kwargs:
            if kw not in ("user", "password"):
                setattr(self, kw, kwargs[kw])
        # It's important to set user and password at the same time
        if "user" in kwargs or "password" in kwargs:
            self._set_auth(kwargs.get("user", self._user), kwargs.get("password", self._password))
        if self._http_session:
            self._http_session.close()
        self._connected = False
        self._controller.notification.emit("compute.updated", self.__json__())
        self._controller.save()

    @asyncio.coroutine
    def close(self):
        self._connected = False
        if self._http_session:
            self._http_session.close()
        if self._ws:
            yield from self._ws.close()
            self._ws = None
        self._closed = True

    @property
    def name(self):
        """
        :returns: Compute name
        """
        return self._name

    @name.setter
    def name(self, name):
        if name is not None:
            self._name = name
        else:
            if self._user:
                user = self._user
                # Due to random user generated by 1.4 it's common to have a very long user
                if len(user) > 14:
                    user = user[:11] + "..."
                self._name = "{}://{}@{}:{}".format(self._protocol, user, self._host, self._port)
            else:
                self._name = "{}://{}:{}".format(self._protocol, self._host, self._port)

    @property
    def connected(self):
        """
        :returns: True if compute node is connected
        """
        return self._connected

    @property
    def id(self):
        """
        :returns: Compute identifier (string)
        """
        return self._id

    @property
    def host(self):
        """
        :returns: Compute host (string)
        """
        return self._host

    @property
    def host_ip(self):
        """
        Return the IP associated to the host
        """
        try:
            return socket.gethostbyname(self._host)
        except socket.gaierror:
            return '0.0.0.0'

    @host.setter
    def host(self, host):
        self._host = host
        if self._console_host is None:
            self._console_host = host

    @property
    def console_host(self):
        return self._console_host

    @property
    def port(self):
        """
        :returns: Compute port (integer)
        """
        return self._port

    @port.setter
    def port(self, port):
        self._port = port

    @property
    def protocol(self):
        """
        :returns: Compute protocol (string)
        """
        return self._protocol

    @protocol.setter
    def protocol(self, protocol):
        self._protocol = protocol

    @property
    def user(self):
        return self._user

    @user.setter
    def user(self, value):
        self._set_auth(value, self._password)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        self._set_auth(self._user, value)

    @property
    def cpu_usage_percent(self):
        return self._cpu_usage_percent

    @property
    def memory_usage_percent(self):
        return self._memory_usage_percent

    def __json__(self, topology_dump=False):
        """
        :param topology_dump: Filter to keep only properties require for saving on disk
        """
        if topology_dump:
            return {
                "compute_id": self._id,
                "name": self._name,
                "protocol": self._protocol,
                "host": self._host,
                "port": self._port
            }
        return {
            "compute_id": self._id,
            "name": self._name,
            "protocol": self._protocol,
            "host": self._host,
            "port": self._port,
            "user": self._user,
            "connected": self._connected,
            "cpu_usage_percent": self._cpu_usage_percent,
            "memory_usage_percent": self._memory_usage_percent,
            "capabilities": self._capabilities
        }

    @asyncio.coroutine
    def download_file(self, project, path):
        """
        Read file of a project and download it

        :param project: A project object
        :param path: The path of the file in the project
        :returns: A file stream
        """

        url = self._getUrl("/projects/{}/files/{}".format(project.id, path))
        response = yield from self._session().request("GET", url, auth=self._auth)
        if response.status == 404:
            raise aiohttp.web.HTTPNotFound(text="{} not found on compute".format(path))
        return response

    @asyncio.coroutine
    def stream_file(self, project, path):
        """
        Read file of a project and stream it

        :param project: A project object
        :param path: The path of the file in the project
        :returns: A file stream
        """

        # Due to Python 3.4 limitation we can't use with and asyncio
        # https://www.python.org/dev/peps/pep-0492/
        # that why we wrap the answer
        class StreamResponse:

            def __init__(self, response):
                self._response = response

            def __enter__(self):
                return self._response.content

            def __exit__(self):
                self._response.close()

        url = self._getUrl("/projects/{}/stream/{}".format(project.id, path))
        response = yield from self._session().request("GET", url, auth=self._auth, timeout=None)
        if response.status == 404:
            raise aiohttp.web.HTTPNotFound(text="{} not found on compute".format(path))
        return StreamResponse(response)

    @asyncio.coroutine
    def http_query(self, method, path, data=None, dont_connect=False, **kwargs):
        """
        :param dont_connect: If true do not reconnect if not connected
        """
        if not self._connected and not dont_connect:
            if self._id == "vm" and not self._controller.gns3vm.running:
                yield from self._controller.gns3vm.start()

            yield from self.connect()
        if not self._connected and not dont_connect:
            raise ComputeError("Can't connect to {}".format(self._name))
        response = yield from self._run_http_query(method, path, data=data, **kwargs)
        return response

    @asyncio.coroutine
    def _try_reconnect(self):
        """
        We catch error during reconnect
        """
        try:
            yield from self.connect()
        except aiohttp.web.HTTPConflict:
            pass

    @locked_coroutine
    def connect(self):
        """
        Check if remote server is accessible
        """
        if not self._connected and not self._closed:
            try:
                response = yield from self._run_http_query("GET", "/capabilities")
            except ComputeError:
                # Try to reconnect after 2 seconds if server unavailable only if not during tests (otherwise we create a ressources usage bomb)
                if not hasattr(sys, "_called_from_test") or not sys._called_from_test:
                    self._connection_failure += 1
                    # After 5 failure we close the project using the compute to avoid sync issues
                    if self._connection_failure == 5:
                        log.warning("Can't connect to compute %s", self._id)
                        yield from self._controller.close_compute_projects(self)

                    asyncio.get_event_loop().call_later(2, lambda: asyncio.async(self._try_reconnect()))

                return
            except aiohttp.web.HTTPNotFound:
                raise aiohttp.web.HTTPConflict(text="The server {} is not a GNS3 server or it's a 1.X server".format(self._id))
            except aiohttp.web.HTTPUnauthorized:
                raise aiohttp.web.HTTPConflict(text="Invalid auth for server {}".format(self._id))
            except aiohttp.web.HTTPServiceUnavailable:
                raise aiohttp.web.HTTPConflict(text="The server {} is unavailable".format(self._id))
            except ValueError:
                raise aiohttp.web.HTTPConflict(text="Invalid server url for server {}".format(self._id))

            if "version" not in response.json:
                self._http_session.close()
                raise aiohttp.web.HTTPConflict(text="The server {} is not a GNS3 server".format(self._id))
            self._capabilities = response.json
            if parse_version(__version__)[:2] != parse_version(response.json["version"])[:2]:
                self._http_session.close()
                raise aiohttp.web.HTTPConflict(text="The server {} versions are not compatible {} != {}".format(self._id, __version__, response.json["version"]))

            self._notifications = asyncio.gather(self._connect_notification())
            self._connected = True
            self._connection_failure = 0
            self._controller.notification.emit("compute.updated", self.__json__())

    @asyncio.coroutine
    def _connect_notification(self):
        """
        Connect to the notification stream
        """
        try:
            self._ws = yield from self._session().ws_connect(self._getUrl("/notifications/ws"), auth=self._auth)
        except (aiohttp.errors.WSServerHandshakeError, aiohttp.errors.ClientResponseError):
            self._ws = None
        while self._ws is not None:
            try:
                response = yield from self._ws.receive()
            except aiohttp.errors.WSServerHandshakeError:
                self._ws = None
                break
            if response.tp == aiohttp.MsgType.closed or response.tp == aiohttp.MsgType.error or response.data is None:
                self._connected = False
                break
            msg = json.loads(response.data)
            action = msg.pop("action")
            event = msg.pop("event")

            if action == "ping":
                self._cpu_usage_percent = event["cpu_usage_percent"]
                self._memory_usage_percent = event["memory_usage_percent"]
                self._controller.notification.emit("compute.updated", self.__json__())
            else:
                yield from self._controller.notification.dispatch(action, event, compute_id=self.id)
        if self._ws:
            yield from self._ws.close()

        # Try to reconnect after 1 seconds if server unavailable only if not during tests (otherwise we create a ressources usage bomb)
        if not hasattr(sys, "_called_from_test") or not sys._called_from_test:
            asyncio.get_event_loop().call_later(1, lambda: asyncio.async(self.connect()))
        self._ws = None
        self._cpu_usage_percent = None
        self._memory_usage_percent = None
        self._controller.notification.emit("compute.updated", self.__json__())

    def _getUrl(self, path):
        host = self._host
        # IPV6
        if host:
            # IPV6
            if ":" in host:
                # Reduce IPV6 to his simple form
                host = str(ipaddress.IPv6Address(host))
                if host == "::":
                    host = "::1"
                host = "[{}]".format(host)
            elif host == "0.0.0.0":
                host = "127.0.0.1"
        return "{}://{}:{}/v2/compute{}".format(self._protocol, host, self._port, path)

    @asyncio.coroutine
    def _run_http_query(self, method, path, data=None, timeout=20, raw=False):
        with Timeout(timeout):
            url = self._getUrl(path)
            headers = {}
            headers['content-type'] = 'application/json'
            chunked = False
            if data == {}:
                data = None
            elif data is not None:
                if hasattr(data, '__json__'):
                    data = json.dumps(data.__json__())
                elif isinstance(data, aiohttp.streams.EmptyStreamReader):
                    data = None
                # Stream the request
                elif isinstance(data, aiohttp.streams.StreamReader) or isinstance(data, bytes):
                    chunked = True
                    headers['content-type'] = 'application/octet-stream'
                # If the data is an open file we will iterate on it
                elif isinstance(data, io.BufferedIOBase):
                    chunked = True
                    headers['content-type'] = 'application/octet-stream'

                    def send_data(f):
                        while True:
                            chunk = f.read(4096)
                            if not chunk:
                                break
                            yield chunk

                    data = send_data(data)
                else:
                    data = json.dumps(data)
        try:
            response = yield from self._session().request(method, url, headers=headers, data=data, auth=self._auth, chunked=chunked, timeout=timeout)
        except asyncio.TimeoutError as e:
            raise ComputeError("Timeout error when connecting to {}".format(url))
        except (aiohttp.errors.ClientOSError, aiohttp.errors.ClientRequestError, aiohttp.errors.ServerDisconnectedError, aiohttp.ClientResponseError, ValueError) as e:
            raise ComputeError(str(e))
        body = yield from response.read()
        if body and not raw:
            body = body.decode()

        if response.status >= 300:
            # Try to decode the GNS3 error
            if body and not raw:
                try:
                    msg = json.loads(body)["message"]
                except (KeyError, ValueError):
                    msg = body
            else:
                msg = ""

            if response.status == 400:
                raise aiohttp.web.HTTPBadRequest(text="Bad request {} {}".format(url, body))
            elif response.status == 401:
                raise aiohttp.web.HTTPUnauthorized(text="Invalid authentication for compute {}".format(self.id))
            elif response.status == 403:
                raise aiohttp.web.HTTPForbidden(text=msg)
            elif response.status == 404:
                raise aiohttp.web.HTTPNotFound(text="{} {} not found".format(method, path))
            elif response.status == 408 or response.status == 504:
                raise aiohttp.web.HTTPRequestTimeout(text="{} {} request timeout".format(method, path))
            elif response.status == 409:
                try:
                    raise ComputeConflict(json.loads(body))
                # If the 409 doesn't come from a GNS3 server
                except ValueError:
                    raise aiohttp.web.HTTPConflict(text=msg)
            elif response.status == 500:
                raise aiohttp.web.HTTPInternalServerError(text="Internal server error {}".format(url))
            elif response.status == 503:
                raise aiohttp.web.HTTPServiceUnavailable(text="Service unavailable {} {}".format(url, body))
            else:
                raise NotImplementedError("{} status code is not supported".format(response.status))
        if body and len(body):
            if raw:
                response.body = body
            else:
                try:
                    response.json = json.loads(body)
                except ValueError:
                    raise aiohttp.web.HTTPConflict(text="The server {} is not a GNS3 server".format(self._id))
        else:
            response.json = {}
            response.body = b""
        return response

    @asyncio.coroutine
    def get(self, path, **kwargs):
        return (yield from self.http_query("GET", path, **kwargs))

    @asyncio.coroutine
    def post(self, path, data={}, **kwargs):
        response = yield from self.http_query("POST", path, data, **kwargs)
        return response

    @asyncio.coroutine
    def put(self, path, data={}, **kwargs):
        response = yield from self.http_query("PUT", path, data, **kwargs)
        return response

    @asyncio.coroutine
    def delete(self, path, **kwargs):
        return (yield from self.http_query("DELETE", path, **kwargs))

    @asyncio.coroutine
    def forward(self, method, type, path, data=None):
        """
        Forward a call to the emulator on compute
        """
        try:
            action = "/{}/{}".format(type, path)
            res = yield from self.http_query(method, action, data=data, timeout=None)
        except aiohttp.errors.DisconnectedError:
            log.error("Connection lost to %s during %s %s", self._id, method, action)
            raise aiohttp.web.HTTPGatewayTimeout()
        return res.json

    @asyncio.coroutine
    def images(self, type):
        """
        Return the list of images available for this type on controller
        and on the compute node.
        """
        images = []

        res = yield from self.http_query("GET", "/{}/images".format(type), timeout=None)
        images = res.json

        try:
            if type in ["qemu", "dynamips", "iou"]:
                for local_image in list_images(type):
                    if local_image['filename'] not in [i['filename'] for i in images]:
                        images.append(local_image)
                images = sorted(images, key=itemgetter('filename'))
            else:
                images = sorted(images, key=itemgetter('image'))
        except OSError as e:
            raise ComputeError("Can't list images: {}".format(str(e)))
        return images

    @asyncio.coroutine
    def list_files(self, project):
        """
        List files in the project on computes
        """
        path = "/projects/{}/files".format(project.id)
        res = yield from self.http_query("GET", path, timeout=120)
        return res.json

    @asyncio.coroutine
    def get_ip_on_same_subnet(self, other_compute):
        """
        Try to found the best ip for communication from one compute
        to another

        :returns: Tuple (ip_for_this_compute, ip_for_other_compute)
        """
        if other_compute == self:
            return (self.host_ip, self.host_ip)

        # Perhaps the user has correct network gateway, we trust him
        if (self.host_ip not in ('0.0.0.0', '127.0.0.1') and other_compute.host_ip not in ('0.0.0.0', '127.0.0.1')):
            return (self.host_ip, other_compute.host_ip)

        this_compute_interfaces = yield from self.interfaces()
        other_compute_interfaces = yield from other_compute.interfaces()

        # Sort interface to put the compute host in first position
        # we guess that if user specified this host it could have a reason (VMware Nat / Host only interface)
        this_compute_interfaces = sorted(this_compute_interfaces, key=lambda i: i["ip_address"] != self.host_ip)
        other_compute_interfaces = sorted(other_compute_interfaces, key=lambda i: i["ip_address"] != other_compute.host_ip)

        for this_interface in this_compute_interfaces:
            # Skip if no ip or no netmask (vbox when stopped set a null netmask)
            if len(this_interface["ip_address"]) == 0 or this_interface["netmask"] is None:
                continue
            # Ignore 169.254 network because it's for Windows special purpose
            if this_interface["ip_address"].startswith("169.254."):
                continue

            this_network = ipaddress.ip_network("{}/{}".format(this_interface["ip_address"], this_interface["netmask"]), strict=False)

            for other_interface in other_compute_interfaces:
                if len(other_interface["ip_address"]) == 0 or other_interface["netmask"] is None:
                    continue

                # Avoid stuff like 127.0.0.1
                if other_interface["ip_address"] == this_interface["ip_address"]:
                    continue

                other_network = ipaddress.ip_network("{}/{}".format(other_interface["ip_address"], other_interface["netmask"]), strict=False)
                if this_network.overlaps(other_network):
                    return (this_interface["ip_address"], other_interface["ip_address"])

        raise ValueError("No common subnet for compute {} and {}".format(self.name, other_compute.name))
