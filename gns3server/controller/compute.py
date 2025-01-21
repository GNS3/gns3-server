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

if sys.version_info >= (3, 11):
    from asyncio import timeout as asynctimeout
else:
    from async_timeout import timeout as asynctimeout

from ..utils import parse_version
from ..utils.asyncio import locking
from ..controller.controller_error import ControllerError
from ..version import __version__, __version_info__


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


class Compute:
    """
    A GNS3 compute.
    """

    def __init__(self, compute_id, controller=None, protocol="http", host="localhost",
                 port=3080, user=None, password=None, name=None, console_host=None, ssl_context=None):
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
        self._notifications = None
        self._closed = False  # Close mean we are destroying the compute node
        self._controller = controller
        self._set_auth(user, password)
        self._cpu_usage_percent = None
        self._memory_usage_percent = None
        self._last_error = None
        self._ssl_context = ssl_context
        self._capabilities = {
            "version": None,
            "node_types": []
        }
        self.name = name
        # Cache of interfaces on remote host
        self._interfaces_cache = None
        self._connection_failure = 0

    def _session(self):
        if self._http_session is None or self._http_session.closed is True:
            self._http_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=None,
                                                                                      force_close=True,
                                                                                      ssl_context=self._ssl_context))
        return self._http_session

    #def __del__(self):
    #
    #   if self._http_session:
    #       self._http_session.close()

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
                try:
                    self._auth = aiohttp.BasicAuth(self._user, self._password, "utf-8")
                except ValueError as e:
                    log.error(str(e))
            else:
                self._password = None
                self._auth = aiohttp.BasicAuth(self._user, "")

    def set_last_error(self, msg):
        """
        Set the last error message for this compute.

        :param msg: message
        """
        self._last_error = msg

    async def interfaces(self):
        """
        Get the list of network on compute
        """
        if not self._interfaces_cache:
            response = await self.get("/network/interfaces")
            self._interfaces_cache = response.json
        return self._interfaces_cache

    async def update(self, **kwargs):
        for kw in kwargs:
            if kw not in ("user", "password"):
                setattr(self, kw, kwargs[kw])
        # It's important to set user and password at the same time
        if "user" in kwargs or "password" in kwargs:
            self._set_auth(kwargs.get("user", self._user), kwargs.get("password", self._password))
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        self._connected = False
        self._controller.notification.controller_emit("compute.updated", self.__json__())
        self._controller.save()

    async def close(self):

        self._connected = False
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        try:
            if self._notifications:
                await self._notifications
        except asyncio.CancelledError:
            pass
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
            "capabilities": self._capabilities,
            "last_error": self._last_error
        }

    async def download_file(self, project, path):
        """
        Read file of a project and download it

        :param project: A project object
        :param path: The path of the file in the project
        :returns: A file stream
        """

        url = self._getUrl("/projects/{}/files/{}".format(project.id, path))
        response = await self._session().request("GET", url, auth=self._auth)
        if response.status == 404:
            raise aiohttp.web.HTTPNotFound(text="File '{}' not found on compute".format(path))
        return response

    async def download_image(self, image_type, image):
        """
        Read file of a project and download it

        :param image_type: Image type
        :param image: The path of the image
        :returns: A file stream
        """

        url = self._getUrl("/{}/images/{}".format(image_type, image))
        response = await self._session().request("GET", url, auth=self._auth)
        if response.status == 404:
            raise aiohttp.web.HTTPNotFound(text="Image '{}' not found on compute".format(image))
        return response

    async def http_query(self, method, path, data=None, dont_connect=False, **kwargs):
        """
        :param dont_connect: If true do not reconnect if not connected
        """

        if not self._connected and not dont_connect:
            if self._id == "vm" and not self._controller.gns3vm.running:
                await self._controller.gns3vm.start()
            await self.connect()
        if not self._connected and not dont_connect:
            raise ComputeError("Cannot connect to compute '{}' with request {} {}".format(self._name, method, path))
        response = await self._run_http_query(method, path, data=data, **kwargs)
        return response

    async def _try_reconnect(self):
        """
        We catch error during reconnect
        """
        try:
            await self.connect()
        except aiohttp.web.HTTPConflict:
            pass

    @locking
    async def connect(self):
        """
        Check if remote server is accessible
        """

        if not self._connected and not self._closed and self.host:
            try:
                log.info("Connecting to compute '{}'".format(self._id))
                response = await self._run_http_query("GET", "/capabilities")
            except ComputeError as e:
                log.warning("Cannot connect to compute '{}': {}".format(self._id, e))
                # Try to reconnect after 5 seconds if server unavailable only if not during tests (otherwise we create a ressource usage bomb)
                if not hasattr(sys, "_called_from_test") or not sys._called_from_test:
                    self._connection_failure += 1
                    # After 5 failure we close the project using the compute to avoid sync issues
                    if self._connection_failure == 10:
                        log.error("Could not connect to compute '{}' after multiple attempts: {}".format(self._id, e))
                        await self._controller.close_compute_projects(self)
                    asyncio.get_event_loop().call_later(5, lambda: asyncio.ensure_future(self._try_reconnect()))
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
                msg = "The server {} is not a GNS3 server".format(self._id)
                log.error(msg)
                await self._http_session.close()
                raise aiohttp.web.HTTPConflict(text=msg)
            self._capabilities = response.json

            if response.json["version"].split("-")[0] != __version__.split("-")[0]:
                if self._name.startswith("GNS3 VM"):
                    msg = "GNS3 version {} is not the same as the GNS3 VM version {}. Please upgrade the GNS3 VM.".format(__version__,
                                                                                                                          response.json["version"])
                else:
                    msg = "GNS3 controller version {} is not the same as compute {} version {}".format(__version__,
                                                                                                       self._name,
                                                                                                       response.json["version"])
                if __version_info__[3] == 0:
                    # Stable release
                    log.error(msg)
                    await self._http_session.close()
                    self._last_error = msg
                    raise aiohttp.web.HTTPConflict(text=msg)
                elif parse_version(__version__)[:2] != parse_version(response.json["version"])[:2]:
                    # We don't allow different major version to interact even with dev build
                    log.error(msg)
                    await self._http_session.close()
                    self._last_error = msg
                    raise aiohttp.web.HTTPConflict(text=msg)
                else:
                    msg = "{}\nUsing different versions may result in unexpected problems. Please use at your own risk.".format(msg)
                    self._controller.notification.controller_emit("log.warning", {"message": msg})

            self._notifications = asyncio.gather(self._connect_notification())
            self._connected = True
            self._connection_failure = 0
            self._last_error = None
            self._controller.notification.controller_emit("compute.updated", self.__json__())

    async def _connect_notification(self):
        """
        Connect to the notification stream
        """

        ws_url = self._getUrl("/notifications/ws")
        try:
            async with self._session().ws_connect(ws_url, auth=self._auth, heartbeat=10) as ws:
                log.info("Connected to compute '{}' WebSocket '{}'".format(self._id, ws_url))
                async for response in ws:
                    if response.type == aiohttp.WSMsgType.TEXT:
                        msg = json.loads(response.data)
                        action = msg.pop("action")
                        event = msg.pop("event")
                        project_id = msg.pop("project_id", None)
                        if action == "ping":
                            self._cpu_usage_percent = event["cpu_usage_percent"]
                            self._memory_usage_percent = event["memory_usage_percent"]
                            #FIXME: slow down number of compute events
                            self._controller.notification.controller_emit("compute.updated", self.__json__())
                        else:
                            await self._controller.notification.dispatch(action, event, project_id=project_id, compute_id=self.id)
                    else:
                        if response.type == aiohttp.WSMsgType.CLOSE:
                            await ws.close()
                        elif response.type == aiohttp.WSMsgType.ERROR:
                            log.error("Error received on compute '{}' WebSocket '{}': {}".format(self._id, ws_url, ws.exception()))
                        elif response.type == aiohttp.WSMsgType.CLOSED:
                            pass
                        break
        except aiohttp.ClientError as e:
            log.error("Client response error received on compute '{}' WebSocket '{}': {}".format(self._id, ws_url,e))
        finally:
            self._connected = False
            log.info("Connection closed to compute '{}' WebSocket '{}'".format(self._id, ws_url))

        # Try to reconnect after 1 second if server unavailable only if not during tests (otherwise we create a ressources usage bomb)
        if not hasattr(sys, "_called_from_test") or not sys._called_from_test:
            asyncio.get_event_loop().call_later(1, lambda: asyncio.ensure_future(self.connect()))

        self._cpu_usage_percent = None
        self._memory_usage_percent = None
        self._controller.notification.controller_emit("compute.updated", self.__json__())

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

    def get_url(self, path):
        """ Returns URL for specific path at Compute"""
        return self._getUrl(path)

    async def _run_http_query(self, method, path, data=None, timeout=120, raw=False):
        async with asynctimeout(delay=timeout):
            url = self._getUrl(path)
            headers = {}
            headers['content-type'] = 'application/json'
            chunked = None
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
                else:
                    data = json.dumps(data).encode("utf-8")
        try:
            log.debug("Attempting request to compute: {method} {url} {headers}".format(method=method, url=url, headers=headers))
            response = await self._session().request(method, url, headers=headers, data=data, auth=self._auth, chunked=chunked, timeout=timeout)
        except asyncio.TimeoutError:
            raise ComputeError("Timeout error for {} call to {} after {}s".format(method, url, timeout))
        except (aiohttp.ClientError, aiohttp.ServerDisconnectedError, ValueError, KeyError, socket.gaierror) as e:
            #  aiohttp 2.3.1 raises socket.gaierror when cannot find host
            raise ComputeError(str(e))
        body = await response.read()
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
                raise NotImplementedError("{} status code is not supported for {} '{}'".format(response.status, method, url))
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

    async def get(self, path, **kwargs):
        return (await self.http_query("GET", path, **kwargs))

    async def post(self, path, data={}, **kwargs):
        response = await self.http_query("POST", path, data, **kwargs)
        return response

    async def put(self, path, data={}, **kwargs):
        response = await self.http_query("PUT", path, data, **kwargs)
        return response

    async def delete(self, path, **kwargs):
        return (await self.http_query("DELETE", path, **kwargs))

    async def forward(self, method, type, path, data=None):
        """
        Forward a call to the emulator on compute
        """
        try:
            action = "/{}/{}".format(type, path)
            res = await self.http_query(method, action, data=data, timeout=None)
        except aiohttp.ServerDisconnectedError:
            log.error("Connection lost to %s during %s %s", self._id, method, action)
            raise aiohttp.web.HTTPGatewayTimeout()
        return res.json

    async def images(self, type):
        """
        Return the list of images available for this type on the compute node.
        """
        images = []

        res = await self.http_query("GET", "/{}/images".format(type), timeout=None)
        images = res.json

        try:
            if type in ["qemu", "dynamips", "iou"]:
                #for local_image in list_images(type):
                #    if local_image['filename'] not in [i['filename'] for i in images]:
                #        images.append(local_image)
                images = sorted(images, key=itemgetter('filename'))
            else:
                images = sorted(images, key=itemgetter('image'))
        except OSError as e:
            raise ComputeError("Cannot list images: {}".format(str(e)))
        return images

    async def list_files(self, project):
        """
        List files in the project on computes
        """
        path = "/projects/{}/files".format(project.id)
        res = await self.http_query("GET", path, timeout=None)
        return res.json

    async def get_ip_on_same_subnet(self, other_compute):
        """
        Try to find the best ip for communication from one compute
        to another

        :returns: Tuple (ip_for_this_compute, ip_for_other_compute)
        """
        if other_compute == self:
            return (self.host_ip, self.host_ip)

        # Perhaps the user has correct network gateway, we trust him
        if (self.host_ip not in ('0.0.0.0', '127.0.0.1') and other_compute.host_ip not in ('0.0.0.0', '127.0.0.1')):
            return (self.host_ip, other_compute.host_ip)

        this_compute_interfaces = await self.interfaces()
        other_compute_interfaces = await other_compute.interfaces()

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
