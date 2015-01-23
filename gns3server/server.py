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

from .web.route import Route
from .config import Config
from .modules import MODULES
from .modules.port_manager import PortManager

# TODO: get rid of * have something generic to automatically import handlers so the routes can be found
from gns3server.handlers import *

import logging
log = logging.getLogger(__name__)


class Server:

    def __init__(self, host, port, console_bind_to_any):

        self._host = host
        self._port = port
        self._loop = None
        self._start_time = time.time()
        self._port_manager = PortManager(host, console_bind_to_any)

        # TODO: server config file support, to be reviewed
        # # get the projects and temp directories from the configuration file (passed to the modules)
        # config = Config.instance()
        # server_config = config.get_default_section()
        # # default projects directory is "~/GNS3/projects"
        # self._projects_dir = os.path.expandvars(os.path.expanduser(server_config.get("projects_directory", "~/GNS3/projects")))
        # self._temp_dir = server_config.get("temporary_directory", tempfile.gettempdir())
        #
        # try:
        #     os.makedirs(self._projects_dir)
        #     log.info("projects directory '{}' created".format(self._projects_dir))
        # except FileExistsError:
        #     pass
        # except OSError as e:
        #     log.error("could not create the projects directory {}: {}".format(self._projects_dir, e))

    @asyncio.coroutine
    def _run_application(self, app):

        server = yield from self._loop.create_server(app.make_handler(), self._host, self._port)
        return server

    def _stop_application(self):
        """
        Cleanup the modules (shutdown running emulators etc.)
        """

        for module in MODULES:
            log.debug("Unloading module {}".format(module.__name__))
            m = module.instance()
            self._loop.run_until_complete(m.unload())
        self._loop.stop()

    def _signal_handling(self):

        def signal_handler(signame):
            log.warning("Server has got signal {}, exiting...".format(signame))
            self._stop_application()

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

        def reload():

            log.info("Reloading")
            self._stop_application()
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
                reload()
        self._loop.call_later(1, self._reload_hook)

    def run(self):
        """
        Starts the server.
        """

        logger = logging.getLogger("asyncio")
        logger.setLevel(logging.WARNING)

        if sys.platform.startswith("win"):
            # use the Proactor event loop on Windows
            asyncio.set_event_loop(asyncio.ProactorEventLoop())

        # TODO: SSL support for Rackspace cloud integration (here or with nginx for instance).
        self._loop = asyncio.get_event_loop()
        app = aiohttp.web.Application()
        for method, route, handler in Route.get_routes():
            log.debug("Adding route: {} {}".format(method, route))
            app.router.add_route(method, route, handler)
        for module in MODULES:
            log.debug("Loading module {}".format(module.__name__))
            m = module.instance()
            m.port_manager = self._port_manager

        log.info("Starting server on {}:{}".format(self._host, self._port))
        self._loop.run_until_complete(self._run_application(app))
        self._signal_handling()

        # FIXME: remove it in production or in tests
        self._loop.call_later(1, self._reload_hook)
        self._loop.run_forever()
