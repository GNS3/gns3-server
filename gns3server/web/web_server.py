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
import asyncio
import aiohttp
import aiohttp_cors
import functools
import time
import atexit

from .route import Route
from ..config import Config
from ..compute import MODULES
from ..compute.port_manager import PortManager
from ..compute.qemu import Qemu
from ..controller import Controller


# do not delete this import
import gns3server.handlers

import logging
log = logging.getLogger(__name__)

if not aiohttp.__version__.startswith("1.3"):
    raise RuntimeError("You need aiohttp 1.3 for running GNS3")


class WebServer:

    def __init__(self, host, port):

        self._host = host
        self._port = port
        self._loop = None
        self._handler = None
        self._server = None
        self._app = None
        self._start_time = time.time()
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
            srv = self._loop.create_server(handler, self._host, self._port, ssl=ssl_context)
            self._server, startup_res = self._loop.run_until_complete(asyncio.gather(srv, self._app.startup(), loop=self._loop))
        except (OSError, asyncio.CancelledError) as e:
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

        if PortManager.instance().tcp_ports:
            log.warning("TCP ports are still used {}".format(PortManager.instance().tcp_ports))

        if PortManager.instance().udp_ports:
            log.warning("UDP ports are still used {}".format(PortManager.instance().udp_ports))

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

    @asyncio.coroutine
    def _on_startup(self, *args):
        """
        Called when the HTTP server start
        """
        yield from Controller.instance().start()
        # Because with a large image collection
        # without md5sum already computed we start the
        # computing with server start
        asyncio.async(Qemu.instance().list_images())

    def run(self):
        """
        Starts the server.
        """

        server_logger = logging.getLogger('aiohttp.server')
        # In debug mode we don't use the standard request log but a more complete in response.py
        if log.getEffectiveLevel() == logging.DEBUG:
            server_logger.setLevel(logging.CRITICAL)

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
        # Background task started with the server
        self._app.on_startup.append(self._on_startup)

        # Allow CORS for this domains
        cors = aiohttp_cors.setup(self._app, defaults={
            # Default web server for web gui dev
            "http://127.0.0.1:8080": aiohttp_cors.ResourceOptions(expose_headers="*", allow_headers="*"),
            "http://localhost:8080": aiohttp_cors.ResourceOptions(expose_headers="*", allow_headers="*"),
            "http://gns3.github.io": aiohttp_cors.ResourceOptions(expose_headers="*", allow_headers="*")
        })

        PortManager.instance().console_host = self._host

        for method, route, handler in Route.get_routes():
            log.debug("Adding route: {} {}".format(method, route))
            cors.add(self._app.router.add_route(method, route, handler))
        for module in MODULES:
            log.debug("Loading module {}".format(module.__name__))
            m = module.instance()
            m.port_manager = PortManager.instance()

        log.info("Starting server on {}:{}".format(self._host, self._port))

        self._handler = self._app.make_handler()
        if self._run_application(self._handler, ssl_context) is False:
            self._loop.stop()
            return

        self._signal_handling()
        self._exit_handling()

        if server_config.getboolean("shell"):
            asyncio.async(self.start_shell())

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
