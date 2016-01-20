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
import functools
import types
import time
import atexit

from .web.route import Route
from .web.request_handler import RequestHandler
from .config import Config
from .modules import MODULES
from .modules.port_manager import PortManager

# do not delete this import
import gns3server.handlers

import logging
log = logging.getLogger(__name__)


class Server:

    def __init__(self, host, port):

        self._host = host
        self._port = port
        self._loop = None
        self._handler = None
        self._start_time = time.time()
        self._port_manager = PortManager(host)

    @staticmethod
    def instance(host=None, port=None):
        """
        Singleton to return only one instance of Server.

        :returns: instance of Server
        """

        if not hasattr(Server, "_instance") or Server._instance is None:
            assert host is not None
            assert port is not None
            Server._instance = Server(host, port)
        return Server._instance

    @asyncio.coroutine
    def _run_application(self, handler, ssl_context=None):

        try:
            server = yield from self._loop.create_server(handler, self._host, self._port, ssl=ssl_context)
        except OSError as e:
            log.critical("Could not start the server: {}".format(e))
            self._loop.stop()
            return
        return server

    @asyncio.coroutine
    def shutdown_server(self):
        """
        Cleanly shutdown the server.
        """

        if self._handler:
            yield from self._handler.finish_connections()
            self._handler = None

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

        self._loop.stop()

    def _signal_handling(self):

        def signal_handler(signame):
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

    def _reload_hook(self):

        @asyncio.coroutine
        def reload():

            log.info("Reloading")
            yield from self.shutdown_server()
            os.execv(sys.executable, [sys.executable] + sys.argv)

        # code extracted from tornado
        for module in sys.modules.values():
            # Some modules play games with sys.modules (e.g. email/__init__.py
            # in the standard library), and occasionally this can cause strange
            # failures in getattr.  Just ignore anything that's not an ordinary
            # module.
            if not isinstance(module, types.ModuleType):
                continue
            path = getattr(module, "__file__", None)
            if not path:
                continue
            if path.endswith(".pyc") or path.endswith(".pyo"):
                path = path[:-1]
            modified = os.stat(path).st_mtime
            if modified > self._start_time:
                log.debug("File {} has been modified".format(path))
                asyncio.async(reload())
        self._loop.call_later(1, self._reload_hook)

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
        yield from embed(globals(), locals(), return_asyncio_coroutine=True, patch_stdout=True)

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

    def run(self):
        """
        Starts the server.
        """

        logger = logging.getLogger("asyncio")
        logger.setLevel(logging.ERROR)

        server_config = Config.instance().get_section_config("Server")
        if sys.platform.startswith("win"):
            # use the Proactor event loop on Windows
            loop = asyncio.ProactorEventLoop()

            # Add a periodic callback to give a chance to process signals on Windows
            # because asyncio.add_signal_handler() is not supported yet on that platform
            # otherwise the loop runs outside of signal module's ability to trap signals.
            def wakeup():
                loop.call_later(0.5, wakeup)
            loop.call_later(0.5, wakeup)
            asyncio.set_event_loop(loop)

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

        app = aiohttp.web.Application()
        for method, route, handler in Route.get_routes():
            log.debug("Adding route: {} {}".format(method, route))
            app.router.add_route(method, route, handler)
        for module in MODULES:
            log.debug("Loading module {}".format(module.__name__))
            m = module.instance()
            m.port_manager = self._port_manager

        log.info("Starting server on {}:{}".format(self._host, self._port))
        self._handler = app.make_handler(handler=RequestHandler)
        server = self._run_application(self._handler, ssl_context)
        self._loop.run_until_complete(server)
        self._signal_handling()
        self._exit_handling()

        if server_config.getboolean("live"):
            log.info("Code live reload is enabled, watching for file changes")
            self._loop.call_later(1, self._reload_hook)

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
            if self._handler and self._loop.is_running():
                self._loop.run_until_complete(self._handler.finish_connections())
            server.close()
            if self._loop.is_running():
                self._loop.run_until_complete(app.finish())
