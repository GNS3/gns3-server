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
Set up and run the server.
"""

import os
import sys
import signal
import socket
import json
import ipaddress
import asyncio
import threading
import aiohttp
import aiohttp_cors
import functools
import time
import atexit

from .route import Route
from .request_handler import RequestHandler
from ..config import Config
from ..compute import MODULES
from ..compute.port_manager import PortManager
from ..controller import Controller
from ..version import __version__


# do not delete this import
import gns3server.handlers

import logging
log = logging.getLogger(__name__)


class WebServer:

    def __init__(self, host, port):

        self._host = host
        self._port = port
        self._loop = None
        self._handler = None
        self._server = None
        self._app = None
        self._start_time = time.time()
        self._port_manager = PortManager(host)
        self._running = False
        self._closing = False

    @staticmethod
    def instance(host=None, port=None):
        """
        Singleton to return only one instance of Server.

        :returns: instance of Server
        """

        if not hasattr(WebServer, "_instance") or WebServer._instance is None:
            assert host is not None
            assert port is not None
            WebServer._instance = WebServer(host, port)
        return WebServer._instance

    def _run_application(self, handler, ssl_context=None):
        try:
            self._server = self._loop.run_until_complete(self._loop.create_server(handler, self._host, self._port, ssl=ssl_context))
        except OSError as e:
            log.critical("Could not start the server: {}".format(e))
            return False
        return True

    @asyncio.coroutine
    def shutdown_server(self):
        """
        Cleanly shutdown the server.
        """

        if not self._closing:
            self._closing = True
        else:
            log.warning("Close is already in progress")
            return

        if self._server:
            self._server.close()
            yield from self._server.wait_closed()
        if self._app:
            yield from self._app.shutdown()
        if self._handler:
            yield from self._handler.finish_connections(2)  # Parameter is timeout
        if self._app:
            yield from self._app.cleanup()

        yield from Controller.instance().stop()

        for module in MODULES:
            log.debug("Unloading module {}".format(module.__name__))
            m = module.instance()
            yield from m.unload()

        if self._port_manager.tcp_ports:
            log.warning("TCP ports are still used {}".format(self._port_manager.tcp_ports))

        if self._port_manager.udp_ports:
            log.warning("UDP ports are still used {}".format(self._port_manager.udp_ports))

        for task in asyncio.Task.all_tasks():
            task.cancel()
            try:
                yield from asyncio.wait_for(task, 1)
            except:
                pass

        self._loop.stop()

    def _signal_handling(self):

        def signal_handler(signame, *args):
            log.warning("Server has got signal {}, exiting...".format(signame))
            asyncio.async(self.shutdown_server())

        signals = ["SIGTERM", "SIGINT"]
        if sys.platform.startswith("win"):
            signals.extend(["SIGBREAK"])
        else:
            signals.extend(["SIGHUP", "SIGQUIT"])

        for signal_name in signals:
            callback = functools.partial(signal_handler, signal_name)
            if sys.platform.startswith("win"):
                # add_signal_handler() is not yet supported on Windows
                signal.signal(getattr(signal, signal_name), callback)
            else:
                self._loop.add_signal_handler(getattr(signal, signal_name), callback)

    def _create_ssl_context(self, server_config):

        import ssl
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        certfile = server_config["certfile"]
        certkey = server_config["certkey"]
        try:
            ssl_context.load_cert_chain(certfile, certkey)
        except FileNotFoundError:
            log.critical("Could not find the SSL certfile or certkey")
            raise SystemExit
        except ssl.SSLError as e:
            log.critical("SSL error: {}".format(e))
            raise SystemExit
        log.info("SSL is enabled")
        return ssl_context

    @asyncio.coroutine
    def start_shell(self):
        try:
            from ptpython.repl import embed
        except ImportError:
            log.error("Unable to start a shell: the ptpython module must be installed!")
            return
        yield from embed(globals(), locals(), return_asyncio_coroutine=True, patch_stdout=True, history_filename=".gns3_shell_history")

    def _exit_handling(self):
        """
        Makes sure the asyncio loop is closed.
        """

        def close_asyncio_loop():
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except AttributeError:
                pass
            if loop is not None:
                loop.close()

        atexit.register(close_asyncio_loop)

    def _udp_server_discovery(self):
        """
        UDP multicast and broadcast server discovery (Linux only)
        """

        import ctypes
        uint32_t = ctypes.c_uint32
        in_addr_t = uint32_t

        class in_addr(ctypes.Structure):
            _fields_ = [('s_addr', in_addr_t)]

        class in_pktinfo(ctypes.Structure):
            _fields_ = [('ipi_ifindex', ctypes.c_int),
                        ('ipi_spec_dst', in_addr),
                        ('ipi_addr', in_addr)]

        IP_PKTINFO = 8
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            membership = socket.inet_aton("239.42.42.1") + socket.inet_aton("0.0.0.0")
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_IP, IP_PKTINFO, 1)
            try:
                sock.bind(("", self._port))
            except OSError as e:
                log.error("UDP server discovery could not bind on port {}: {}".format(self._port, e))
                return

            log.info("UDP server discovery started on port {}".format(self._port))
            while self._loop.is_running():
                try:
                    data, ancdata, _, address = sock.recvmsg(255, socket.CMSG_LEN(255))
                except OSError as e:
                    log.error("Error while receiving UDP server discovery request: {}".format(e))
                    continue
                cmsg_level, cmsg_type, cmsg_data = ancdata[0]
                if cmsg_level == socket.SOL_IP and cmsg_type == IP_PKTINFO:
                    pktinfo = in_pktinfo.from_buffer_copy(cmsg_data)
                    request_address = ipaddress.IPv4Address(memoryview(pktinfo.ipi_addr).tobytes())
                    receiving_interface = socket.if_indextoname(pktinfo.ipi_ifindex)
                    log.debug("UDP server discovery request received on {} using {}".format(receiving_interface,
                                                                                            request_address))
                    local_address = ipaddress.IPv4Address(memoryview(pktinfo.ipi_spec_dst).tobytes())
                    if self._host != "0.0.0.0" and self._host != str(local_address):
                        log.debug("Ignoring UDP discovery request received on {} instead of {}".format(local_address,
                                                                                                       self._host))
                        continue
                    server_info = {"version": __version__,
                                   "ip": str(local_address),
                                   "port": self._port}
                    data = json.dumps(server_info)
                    sock.sendto(data.encode(), address)
                    log.debug("Sent server info to {}:{} {}".format(address[0], address[1], data))
                time.sleep(1)  # this is to prevent too many request to slow down the server
        log.debug("UDP server discovery stopped")

    def run(self):
        """
        Starts the server.
        """

        logger = logging.getLogger("asyncio")
        logger.setLevel(logging.ERROR)

        if sys.platform.startswith("win"):
            loop = asyncio.get_event_loop()
            # Add a periodic callback to give a chance to process signals on Windows
            # because asyncio.add_signal_handler() is not supported yet on that platform
            # otherwise the loop runs outside of signal module's ability to trap signals.

            def wakeup():
                loop.call_later(0.5, wakeup)
            loop.call_later(0.5, wakeup)

        server_config = Config.instance().get_section_config("Server")

        ssl_context = None
        if server_config.getboolean("ssl"):
            if sys.platform.startswith("win"):
                log.critical("SSL mode is not supported on Windows")
                raise SystemExit
            ssl_context = self._create_ssl_context(server_config)

        self._loop = asyncio.get_event_loop()
        # Asyncio will raise error if coroutine is not called
        self._loop.set_debug(True)

        for key, val in os.environ.items():
            log.debug("ENV %s=%s", key, val)

        self._app = aiohttp.web.Application()
        # Allow CORS for this domains
        cors = aiohttp_cors.setup(self._app, defaults={
            # Default web server for web gui dev
            "http://127.0.0.1:8080": aiohttp_cors.ResourceOptions(expose_headers="*", allow_headers="*"),
            "http://localhost:8080": aiohttp_cors.ResourceOptions(expose_headers="*", allow_headers="*"),
            "http://gns3.github.io": aiohttp_cors.ResourceOptions(expose_headers="*", allow_headers="*")
        })
        for method, route, handler in Route.get_routes():
            log.debug("Adding route: {} {}".format(method, route))
            cors.add(self._app.router.add_route(method, route, handler))
        for module in MODULES:
            log.debug("Loading module {}".format(module.__name__))
            m = module.instance()
            m.port_manager = self._port_manager

        log.info("Starting server on {}:{}".format(self._host, self._port))
        self._handler = self._app.make_handler(handler=RequestHandler)
        if self._run_application(self._handler, ssl_context) is False:
            self._loop.stop()
            return

        self._signal_handling()
        self._exit_handling()

        controller_start = asyncio.async(Controller.instance().start())

        if server_config.getboolean("shell"):
            asyncio.async(self.start_shell())

        if sys.platform.startswith("linux") and server_config.getboolean("server_discovery"):
            # UDP discovery is only supported on Linux
            udp_server_discovery = threading.Thread(target=self._udp_server_discovery, daemon=True)
            udp_server_discovery.start()

        try:
            self._loop.run_forever()
        except TypeError as e:
            # This is to ignore an asyncio.windows_events exception
            # on Windows when the process gets the SIGBREAK signal
            # TypeError: async() takes 1 positional argument but 3 were given
            log.warning("TypeError exception in the loop {}".format(e))
        finally:
            if self._loop.is_running():
                self._loop.run_until_complete(self.shutdown_server())
