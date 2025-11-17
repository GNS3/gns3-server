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
import weakref

# Import encoding now, to avoid implicit import later.
# Implicit import within threads may cause LookupError when standard library is in a ZIP
import encodings.idna

from .route import Route
from ..config import Config
from ..compute import MODULES
from ..compute.port_manager import PortManager
from ..utils.images import list_images
from ..controller import Controller

# do not delete this import
import gns3server.handlers

import logging
log = logging.getLogger(__name__)

if not (aiohttp.__version__.startswith("3.")):
    raise RuntimeError("aiohttp 3.x is required to run the GNS3 server")


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
        self._ssl_context = None

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
            self._server, startup_res = self._loop.run_until_complete(asyncio.gather(srv, self._app.startup()))
        except (RuntimeError, OSError, asyncio.CancelledError) as e:
            log.critical("Could not start the server: {}".format(e))
            return False
        except KeyboardInterrupt:
            return False
        return True

    async def reload_server(self):
        """
        Reload the server.
        """

        await Controller.instance().reload()

    async def shutdown_server(self):
        """
        Cleanly shutdown the server.
        """

        if not self._closing:
            self._closing = True
        else:
            log.warning("Close is already in progress")
            return

        # close websocket connections
        websocket_connections = set(self._app['websockets'])
        if websocket_connections:
            log.info("Closing {} websocket connections...".format(len(websocket_connections)))
        for ws in websocket_connections:
            await ws.close(code=aiohttp.WSCloseCode.GOING_AWAY, message='Server shutdown')

        if self._server:
            self._server.close()
            # await self._server.wait_closed()
        if self._app:
            await self._app.shutdown()
        if self._handler:
            await self._handler.shutdown(2)  # Parameter is timeout
        if self._app:
            await self._app.cleanup()

        await Controller.instance().stop()

        for module in MODULES:
            log.debug("Unloading module {}".format(module.__name__))
            m = module.instance()
            await m.unload()

        if PortManager.instance().tcp_ports:
            log.warning("TCP ports are still used {}".format(PortManager.instance().tcp_ports))

        if PortManager.instance().udp_ports:
            log.warning("UDP ports are still used {}".format(PortManager.instance().udp_ports))

        try:
            tasks = asyncio.all_tasks()
        except AttributeError:
            tasks = asyncio.Task.all_tasks()

        for task in tasks:
            task.cancel()
            try:
                await asyncio.wait_for(task, 1)
            except BaseException:
                pass

        self._loop.stop()

    def ssl_context(self):
        """
        Returns the SSL context for the server.
        """

        return self._ssl_context

    def _signal_handling(self):

        def signal_handler(signame, *args):

            try:
                if signame == "SIGHUP":
                    log.info("Server has got signal {}, reloading...".format(signame))
                    asyncio.ensure_future(self.reload_server())
                else:
                    log.warning("Server has got signal {}, exiting...".format(signame))
                    asyncio.ensure_future(self.shutdown_server())
            except asyncio.CancelledError:
                pass

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

    async def start_shell(self):

        log.error("The embedded shell has been deactivated in this version of GNS3")
        return
        try:
            from ptpython.repl import embed
        except ImportError:
            log.error("Unable to start a shell: the ptpython module must be installed!")
            return
        await embed(globals(), locals(), return_asyncio_coroutine=True, patch_stdout=True, history_filename=".gns3_shell_history")

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

    async def _compute_image_checksums(self):
        """
        Compute image checksums.
        """

        if sys.platform.startswith("darwin") and hasattr(sys, "frozen"):
            # do not compute on macOS because errors
            return
        loop = asyncio.get_event_loop()
        import concurrent.futures
        with concurrent.futures.ProcessPoolExecutor(max_workers=1) as pool:
            try:
                log.info("Computing image checksums...")
                await loop.run_in_executor(pool, list_images, "qemu")
                log.info("Finished computing image checksums")
            except OSError as e:
                log.warning("Could not compute image checksums: {}".format(e))

    async def _on_startup(self, *args):
        """
        Called when the HTTP server start
        """

        await Controller.instance().start()

        # Start computing checksums now because it can take a long time
        # for a large image collection
        await self._compute_image_checksums()

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

        self._ssl_context = None
        if server_config.getboolean("ssl"):
            if sys.platform.startswith("win"):
                log.critical("SSL mode is not supported on Windows")
                raise SystemExit
            self._ssl_context = self._create_ssl_context(server_config)

        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        self._loop = asyncio.get_event_loop()

        if log.getEffectiveLevel() == logging.DEBUG:
            # On debug version we enable info that
            # coroutine is not called in a way await/await
            self._loop.set_debug(True)

        for key, val in os.environ.items():
            log.debug("ENV %s=%s", key, val)

        self._app = aiohttp.web.Application()

        # Keep a list of active websocket connections
        self._app['websockets'] = weakref.WeakSet()

        # Background task started with the server
        self._app.on_startup.append(self._on_startup)

        resource_options = aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods="*",
            max_age=0
        )

        # Allow CORS for this domains
        cors = aiohttp_cors.setup(self._app, defaults={
            # Default web server for web gui dev
            "http://127.0.0.1:3080": resource_options,
            "http://localhost:3080": resource_options,
            "http://127.0.0.1:4200": resource_options,
            "http://localhost:4200": resource_options,
            "http://gns3.github.io": resource_options,
            "https://gns3.github.io": resource_options
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
        if self._run_application(self._handler, self._ssl_context) is False:
            self._loop.stop()
            sys.exit(1)

        self._signal_handling()
        self._exit_handling()

        if server_config.getboolean("shell"):
            asyncio.ensure_future(self.start_shell())

        try:
            self._loop.run_forever()
        except ConnectionResetError:
            log.warning("Connection reset by peer")
        except TypeError as e:
            # This is to ignore an asyncio.windows_events exception
            # on Windows when the process gets the SIGBREAK signal
            # TypeError: async() takes 1 positional argument but 3 were given
            log.warning("TypeError exception in the loop {}".format(e))
        finally:
            if self._loop.is_running():
                try:
                    self._loop.run_until_complete(self.shutdown_server())
                except asyncio.CancelledError:
                    pass

