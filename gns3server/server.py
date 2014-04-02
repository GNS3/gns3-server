# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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

import zmq
from zmq.eventloop import ioloop, zmqstream
ioloop.install()

import sys
import os
import tempfile
import signal
import errno
import functools
import socket
import tornado.ioloop
import tornado.web
import tornado.autoreload
from .config import Config
from .handlers.jsonrpc_websocket import JSONRPCWebSocket
from .handlers.version_handler import VersionHandler
from .handlers.file_upload_handler import FileUploadHandler
from .modules import MODULES

import logging
log = logging.getLogger(__name__)


class Server(object):

    # built-in handlers
    handlers = [(r"/version", VersionHandler),
                (r"/upload", FileUploadHandler)]

    def __init__(self, host, port, ipc=False):

        self._host = host
        self._port = port
        if ipc:
            self._zmq_port = 0  # this forces to use IPC for communications with the ZeroMQ server
        else:
            try:
                # let the OS find an unused port for the ZeroMQ server
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(('127.0.0.1', 0))
                    self._zmq_port = sock.getsockname()[1]
            except socket.error as e:
                log.warn("could not pick up a random port for the ZeroMQ server: {}".format(e))
                self._zmq_port = port + 1  # let's try this server port + 1
        self._ipc = ipc
        self._modules = []

        # get the projects and temp directories from the configuration file (passed to the modules)
        config = Config.instance()
        server_config = config.get_default_section()
        # default projects directory is "~/Documents/GNS3/projects"
        self._projects_dir = os.path.expandvars(os.path.expanduser(server_config.get("projects_directory", "~/Documents/GNS3/projects")))
        self._temp_dir = server_config.get("temporary_directory", tempfile.gettempdir())

        if not os.path.exists(self._projects_dir):
            try:
                os.makedirs(self._projects_dir)
                log.info("projects directory '{}' created".format(self._projects_dir))
            except OSError as e:
                log.error("could not create the projects directory {}: {}".format(self._projects_dir, e))

    def load_modules(self):
        """
        Loads the modules.
        """

        #=======================================================================
        # cwd = os.path.dirname(os.path.abspath(__file__))
        # module_path = os.path.join(cwd, 'modules')
        # log.info("loading modules from {}".format(module_path))
        # module_manager = ModuleManager([module_path])
        # module_manager.load_modules()
        # for module in module_manager.get_all_modules():
        #     instance = module_manager.activate_module(module,
        #                                               "127.0.0.1",  # ZeroMQ server address
        #                                               self._zmq_port,  # ZeroMQ server port
        #                                               projects_dir=self._projects_dir,
        #                                               temp_dir=self._temp_dir)
        #     if not instance:
        #         continue
        #     self._modules.append(instance)
        #     destinations = instance.destinations()
        #     for destination in destinations:
        #         JSONRPCWebSocket.register_destination(destination, module.name)
        #     instance.start()  # starts the new process
        #=======================================================================

        # special built-in destination to stop the server
        JSONRPCWebSocket.register_destination("builtin.stop", self._cleanup)

        for module in MODULES:
            instance = module(module.__name__.lower(),
                              "127.0.0.1",  # ZeroMQ server address
                              self._zmq_port,  # ZeroMQ server port
                              projects_dir=self._projects_dir,
                              temp_dir=self._temp_dir)

            self._modules.append(instance)
            destinations = instance.destinations()
            for destination in destinations:
                JSONRPCWebSocket.register_destination(destination, instance.name)
            instance.start()  # starts the new process

    def run(self):
        """
        Starts the Tornado web server and ZeroMQ server.
        """

        router = self._create_zmq_router()
        # Add our JSON-RPC Websocket handler to Tornado
        self.handlers.extend([(r"/", JSONRPCWebSocket, dict(zmq_router=router))])
        tornado_app = tornado.web.Application(self.handlers,
                                              template_path=os.path.join(os.path.dirname(__file__), "templates"),
                                              debug=True)  # FIXME: debug mode!
        try:
            print("Starting server on {}:{}".format(self._host, self._port))
            tornado_app.listen(self._port, address=self._host)
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:  # socket already in use
                logging.critical("socket in use for port {}".format(self._port))
                raise SystemExit

        ioloop = tornado.ioloop.IOLoop.instance()
        stream = zmqstream.ZMQStream(router, ioloop)
        stream.on_recv_stream(JSONRPCWebSocket.dispatch_message)
        tornado.autoreload.add_reload_hook(functools.partial(self._cleanup, stop=False))

        def signal_handler(signum=None, frame=None):
            log.warning("Server got signal {}, exiting...".format(signum))
            self._cleanup()

        signals = [signal.SIGTERM, signal.SIGINT]
        if not sys.platform.startswith("win"):
            signals.extend([signal.SIGHUP, signal.SIGQUIT])
        else:
            signals.extend([signal.SIGBREAK])
        for sig in signals:
            signal.signal(sig, signal_handler)

        try:
            ioloop.start()
        except (KeyboardInterrupt, SystemExit):
            print("\nExiting...")
            self._cleanup()

    def _create_zmq_router(self):
        """
        Creates the ZeroMQ router socket to send
        requests to modules.

        :returns: ZeroMQ router socket
        """

        context = zmq.Context()
        context.linger = 0
        router = context.socket(zmq.ROUTER)
        if self._ipc:
            try:
                router.bind("ipc:///tmp/gns3.ipc")
            except zmq.error.ZMQError as e:
                log.critical("Could not start ZeroMQ server on ipc:///tmp/gns3.ipc, reason: {}".format(e))
                self._cleanup()
                raise SystemExit
            log.info("ZeroMQ server listening to ipc:///tmp/gns3.ipc")
        else:
            try:
                router.bind("tcp://127.0.0.1:{}".format(self._zmq_port))
            except zmq.error.ZMQError as e:
                log.critical("Could not start ZeroMQ server on 127.0.0.1:{}, reason: {}".format(self._zmq_port, e))
                self._cleanup()
                raise SystemExit
            log.info("ZeroMQ server listening to 127.0.0.1:{}".format(self._zmq_port))
        return router

    def _shutdown(self):
        """
        Shutdowns the I/O loop.
        """

        ioloop = tornado.ioloop.IOLoop.instance()
        ioloop.stop()

    def _cleanup(self, stop=True):
        """
        Shutdowns any running module processes
        and close remaining Tornado ioloop file descriptors

        :param stop: stops the ioloop if True (default)
        """

        # terminate all modules
        for module in self._modules:
            module.join(timeout=1)
            if module.is_alive():
                log.info("terminating {}".format(module.name))
                module.terminate()
                module.join(timeout=1)

        if stop:
            ioloop = tornado.ioloop.IOLoop.instance()
            ioloop.add_callback_from_signal(self._shutdown)
