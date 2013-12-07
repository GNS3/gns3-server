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
Set up and run the server
"""

import zmq
from zmq.eventloop import ioloop, zmqstream
ioloop.install()

import os
import signal
import errno
import functools
import socket
import tornado.ioloop
import tornado.web
import tornado.autoreload
from .handlers.stomp_websocket import StompWebSocket
from .handlers.version_handler import VersionHandler
from .module_manager import ModuleManager

import logging
log = logging.getLogger(__name__)


class Server(object):

    # built-in handlers
    handlers = [(r"/version", VersionHandler)]

    def __init__(self, host, port, ipc=False):

        self._host = host
        self._port = port
        if ipc:
            self._zmq_port = 0  # this forces module to use IPC for communications
        else:
            self._zmq_port = port + 1  # this server port + 1
        self._ipc = ipc
        self._modules = []

    def load_modules(self):
        """
        Loads the modules
        """

        cwd = os.path.dirname(os.path.abspath(__file__))
        module_path = os.path.join(cwd, 'modules')
        log.info("loading modules from {}".format(module_path))
        module_manager = ModuleManager([module_path])
        module_manager.load_modules()
        for module in module_manager.get_all_modules():
            instance = module_manager.activate_module(module, ("127.0.0.1", self._zmq_port))
            self._modules.append(instance)
            destinations = instance.destinations()
            for destination in destinations:
                StompWebSocket.register_destination(destination, module.name)
            instance.start()  # starts the new process

    def run(self):
        """
        Starts the Tornado web server and ZeroMQ server
        """

        router = self._create_zmq_router()
        # Add our Stomp Websocket handler to Tornado
        self.handlers.extend([(r"/", StompWebSocket, dict(zmq_router=router))])
        tornado_app = tornado.web.Application(self.handlers, debug=True)  # FIXME: debug mode!
        try:
            print("Starting server on port {}".format(self._port))
            tornado_app.listen(self._port)
        except socket.error as e:
            if e.errno == errno.EADDRINUSE:  # socket already in use
                logging.critical("socket in use for port {}".format(self._port))
                raise SystemExit

        ioloop = tornado.ioloop.IOLoop.instance()
        stream = zmqstream.ZMQStream(router, ioloop)
        stream.on_recv(StompWebSocket.dispatch_message)
        tornado.autoreload.add_reload_hook(functools.partial(self._cleanup, stop=False))

        def signal_handler(signum=None, frame=None):
            log.warning("Got signal {}, exiting...".format(signum))
            self._cleanup()

        for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
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

    def _cleanup(self, stop=True):
        """
        Shutdowns running module processes
        and close remaining Tornado ioloop file descriptors

        :param stop: Stop the ioloop if True (default)
        """

        # terminate all modules
        for module in self._modules:
            log.info("terminating {}".format(module.name))
            module.terminate()
            module.join(timeout=1)

        ioloop = tornado.ioloop.IOLoop.instance()
        # close any fd that would have remained open...
        for fd in ioloop._handlers.keys():
            try:
                os.close(fd)
            except Exception:
                pass

        if stop:
            ioloop.stop()
