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
import socket
import tornado.ioloop
import tornado.web
import tornado.autoreload
import pkg_resources
from os.path import expanduser
import base64
import uuid

from pkg_resources import parse_version
from .config import Config
from .handlers.jsonrpc_websocket import JSONRPCWebSocket
from .handlers.version_handler import VersionHandler
from .handlers.file_upload_handler import FileUploadHandler
from .handlers.auth_handler import LoginHandler
from .builtins.server_version import server_version
from .builtins.interfaces import interfaces
from .modules import MODULES

import logging
log = logging.getLogger(__name__)

class Server(object):

    # built-in handlers
    handlers = [(r"/version", VersionHandler),
                (r"/upload", FileUploadHandler),
                (r"/login", LoginHandler)]

    def __init__(self, host, port, ipc=False):

        self._host = host
        self._port = port
        self._router = None
        self._stream = None

        if ipc:
            self._zmq_port = 0  # this forces to use IPC for communications with the ZeroMQ server
        else:
            # communication between the ZeroMQ server and the modules (ZeroMQ dealers)
            # is IPv4 and local (127.0.0.1)
            try:
                # let the OS find an unused port for the ZeroMQ server
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(("127.0.0.1", 0))
                    self._zmq_port = sock.getsockname()[1]
            except OSError as e:
                log.critical("server cannot listen to {}: {}".format(self._host, e))
                raise SystemExit
        self._ipc = ipc
        self._modules = []

        # get the projects and temp directories from the configuration file (passed to the modules)
        config = Config.instance()
        server_config = config.get_default_section()
        # default projects directory is "~/GNS3/projects"
        self._projects_dir = os.path.expandvars(os.path.expanduser(server_config.get("projects_directory", "~/GNS3/projects")))
        self._temp_dir = server_config.get("temporary_directory", tempfile.gettempdir())

        try:
            os.makedirs(self._projects_dir)
            log.info("projects directory '{}' created".format(self._projects_dir))
        except FileExistsError:
            pass
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

        # special built-in to return the server version
        JSONRPCWebSocket.register_destination("builtin.version", server_version)
        # special built-in to return the available interfaces on this host
        JSONRPCWebSocket.register_destination("builtin.interfaces", interfaces)

        for module in MODULES:
            instance = module(module.__name__.lower(),
                              "127.0.0.1",  # ZeroMQ server address
                              self._zmq_port,  # ZeroMQ server port
                              host=self._host,  # server host address
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

        settings = {
            "debug":True,
            "cookie_secret": base64.b64encode(uuid.uuid4().bytes + uuid.uuid4().bytes),
            "login_url": "/login",
        }

        ssl_options = {}

        try:
            cloud_config = Config.instance().get_section_config("CLOUD_SERVER")

            cloud_settings = {

                "required_user" : cloud_config['WEB_USERNAME'],
                "required_pass" : cloud_config['WEB_PASSWORD'],
            }

            settings.update(cloud_settings)

            if cloud_config["SSL_ENABLED"] == "yes":
                ssl_options = {
                    "certfile" : cloud_config["SSL_CRT"],
                    "keyfile" : cloud_config["SSL_KEY"],
                }

                log.info("Certs found - starting in SSL mode")
        except KeyError:
           log.info("Missing cloud.conf - disabling HTTP auth and SSL")


        router = self._create_zmq_router()
        # Add our JSON-RPC Websocket handler to Tornado
        self.handlers.extend([(r"/", JSONRPCWebSocket, dict(zmq_router=router))])
        if hasattr(sys, "frozen"):
            templates_dir = "templates"
        else:
            templates_dir = pkg_resources.resource_filename("gns3server", "templates")
        tornado_app = tornado.web.Application(self.handlers,
                                              template_path=templates_dir,
                                              **settings)  # FIXME: debug mode!

        try:
            print("Starting server on {}:{} (Tornado v{}, PyZMQ v{}, ZMQ v{})".format(self._host,
                                                                                      self._port,
                                                                                      tornado.version,
                                                                                      zmq.__version__,
                                                                                      zmq.zmq_version()))
            kwargs = {"address": self._host}

            if ssl_options:
                kwargs["ssl_options"] = ssl_options

            if parse_version(tornado.version) >= parse_version("3.1"):
                kwargs["max_buffer_size"] = 524288000  # 500 MB file upload limit
            tornado_app.listen(self._port, **kwargs)
        except OSError as e:
            if e.errno == errno.EADDRINUSE:  # socket already in use
                logging.critical("socket in use for {}:{}".format(self._host, self._port))
                self._cleanup(graceful=False)

        ioloop = tornado.ioloop.IOLoop.instance()
        self._stream = zmqstream.ZMQStream(router, ioloop)
        self._stream.on_recv_stream(JSONRPCWebSocket.dispatch_message)
        tornado.autoreload.add_reload_hook(self._reload_callback)

        def signal_handler(signum=None, frame=None):
            try:
                log.warning("Server got signal {}, exiting...".format(signum))
                self._cleanup(signum)
            except RuntimeError:
                # to ignore logging exception: RuntimeError: reentrant call inside <_io.BufferedWriter name='<stderr>'>
                pass

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
        self._router = context.socket(zmq.ROUTER)
        if self._ipc:
            try:
                self._router.bind("ipc:///tmp/gns3.ipc")
            except zmq.error.ZMQError as e:
                log.critical("Could not start ZeroMQ server on ipc:///tmp/gns3.ipc, reason: {}".format(e))
                self._cleanup(graceful=False)
                raise SystemExit
            log.info("ZeroMQ server listening to ipc:///tmp/gns3.ipc")
        else:
            try:
                self._router.bind("tcp://127.0.0.1:{}".format(self._zmq_port))
            except zmq.error.ZMQError as e:
                log.critical("Could not start ZeroMQ server on 127.0.0.1:{}, reason: {}".format(self._zmq_port, e))
                self._cleanup(graceful=False)
                raise SystemExit
            log.info("ZeroMQ server listening to 127.0.0.1:{}".format(self._zmq_port))
        return self._router

    def stop_module(self, module):
        """
        Stop a given module.

        :param module: module name
        """

        if not self._router.closed:
            self._router.send_string(module, zmq.SNDMORE)
            self._router.send_string("stop")

    def _reload_callback(self):
        """
        Callback for the Tornado reload hook.
        """

        for module in self._modules:
            if module.is_alive():
                module.terminate()
                module.join(timeout=1)

    def _shutdown(self):
        """
        Shutdowns the I/O loop and the ZeroMQ stream & socket.
        """

        if self._stream and not self._stream.closed:
            # close the ZeroMQ stream
            self._stream.close()

        if self._router and not self._router.closed:
            # close the ZeroMQ router socket
            self._router.close()

        ioloop = tornado.ioloop.IOLoop.instance()
        ioloop.stop()

    def _cleanup(self, signum=None, graceful=True):
        """
        Shutdowns any running module processes
        and adds a callback to stop the event loop & ZeroMQ

        :param signum: signal number (if called by a signal handler)
        :param graceful: gracefully stop the modules
        """

        # terminate all modules
        for module in self._modules:
            if module.is_alive() and graceful:
                log.info("stopping {}".format(module.name))
                self.stop_module(module.name)
                module.join(timeout=3)
            if module.is_alive():
                # just kill the module if it is still alive.
                log.info("terminating {}".format(module.name))
                module.terminate()
                module.join(timeout=1)

        ioloop = tornado.ioloop.IOLoop.instance()
        if signum:
            ioloop.add_callback_from_signal(self._shutdown)
        else:
            ioloop.add_callback(self._shutdown)
