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
Base class (interface) for modules
"""

import os
import sys
import traceback
import gns3server.jsonrpc as jsonrpc
import multiprocessing
import zmq
import signal

from gns3server.config import Config
from jsonschema import validate, ValidationError

import logging
log = logging.getLogger(__name__)


class IModule(multiprocessing.Process):
    """
    Module interface.

    :param name: module name
    :param args: arguments for the module
    :param kwargs: named arguments for the module
    """

    modules = {}

    def __init__(self, name, *args, **kwargs):

        config = Config.instance()
        server_config = config.get_default_section()
        self._images_dir = os.path.expandvars(os.path.expanduser(server_config.get("upload_directory", "~/GNS3/images")))
        multiprocessing.Process.__init__(self, name=name)
        self._context = None
        self._ioloop = None
        self._stream = None
        self._dealer = None
        self._zmq_host = args[0]  # ZeroMQ server address
        self._zmq_port = args[1]  # ZeroMQ server port
        self._current_session = None
        self._current_destination = None
        self._current_call_id = None
        self._stopping = False

    def _setup(self):
        """
        Sets up PyZMQ and creates the stream to handle requests
        """

        self._context = zmq.Context()
        self._ioloop = zmq.eventloop.ioloop.IOLoop.instance()
        self._stream = self._create_stream(self._zmq_host, self._zmq_port, self._decode_request)

    def _create_stream(self, host=None, port=0, callback=None):
        """
        Creates a new ZMQ stream.

        :returns: ZMQ stream instance
        """

        self._dealer = self._context.socket(zmq.DEALER)
        self._dealer.setsockopt(zmq.IDENTITY, self.name.encode("utf-8"))
        if host and port:
            log.info("ZeroMQ client ({}) connecting to {}:{}".format(self.name, host, port))
            try:
                self._dealer.connect("tcp://{}:{}".format(host, port))
            except zmq.error.ZMQError as e:
                log.critical("Could not connect to ZeroMQ server on {}:{}, reason: {}".format(host, port, e))
                raise SystemExit
        else:
            log.info("ZeroMQ client ({}) connecting to ipc:///tmp/gns3.ipc".format(self.name))
            try:
                self._dealer.connect("ipc:///tmp/gns3.ipc")
            except zmq.error.ZMQError as e:
                log.critical("Could not connect to ZeroMQ server on ipc:///tmp/gns3.ipc, reason: {}".format(e))
                raise SystemExit

        stream = zmq.eventloop.zmqstream.ZMQStream(self._dealer, self._ioloop)
        if callback:
            stream.on_recv(callback)
        return stream

    def add_periodic_callback(self, callback, time):
        """
        Adds a periodic callback to the ioloop.

        :param callback: callback to be called
        :param time: frequency when the callback is executed
        """

        periodic_callback = zmq.eventloop.ioloop.PeriodicCallback(callback, time, self._ioloop)
        return periodic_callback

    def run(self):
        """
        Starts the event loop
        """

        def signal_handler(signum=None, frame=None):
            log.warning("Module {} got signal {}, exiting...".format(self.name, signum))
            self.stop(signum)

        signals = [signal.SIGTERM, signal.SIGINT]
        if not sys.platform.startswith("win"):
            signals.extend([signal.SIGHUP, signal.SIGQUIT])
        else:
            signals.extend([signal.SIGBREAK])
        for sig in signals:
            signal.signal(sig, signal_handler)

        log.info("{} module running with PID {}".format(self.name, self.pid))
        self._setup()
        try:
            self._ioloop.start()
        except KeyboardInterrupt:
            return

        log.info("{} module has stopped".format(self.name))

    def _shutdown(self):
        """
        Shutdowns the I/O loop and the ZeroMQ stream & socket
        """

        self._ioloop.stop()

        if self._stream and not self._stream.closed:
            # close the zeroMQ stream
            self._stream.close()

        if self._dealer and not self._dealer.closed:
            # close the ZeroMQ dealer socket
            self._dealer.close()

    def stop(self, signum=None):
        """
        Adds a callback to stop the event loop & ZeroMQ.

        :param signum: signal number (if called by the signal handler)
        """

        if not self._stopping:
            self._stopping = True
            if signum:
                self._ioloop.add_callback_from_signal(self._shutdown)
            else:
                self._ioloop.add_callback(self._shutdown)

    def send_response(self, results):
        """
        Sends a response back to the requester.

        :param results: JSON results to the ZeroMQ server
        """

        jsonrpc_response = jsonrpc.JSONRPCResponse(results, self._current_call_id)()

        # add session to the response
        response = [self._current_session, jsonrpc_response]
        log.debug("ZeroMQ client ({}) sending: {}".format(self.name, response))
        self._stream.send_json(response)

    def send_param_error(self):
        """
        Sends a param error back to the requester.
        """

        jsonrpc_response = jsonrpc.JSONRPCInvalidParams(self._current_call_id)()

        # add session to the response
        response = [self._current_session, jsonrpc_response]
        log.info("ZeroMQ client ({}) sending JSON-RPC param error for call id {}".format(self.name, self._current_call_id))
        self._stream.send_json(response)

    def send_internal_error(self):
        """
        Sends a param error back to the requester.
        """

        jsonrpc_response = jsonrpc.JSONRPCInternalError()()

        # add session to the response
        response = [self._current_session, jsonrpc_response]
        log.critical("ZeroMQ client ({}) sending JSON-RPC internal error".format(self.name))
        self._stream.send_json(response)

    def send_custom_error(self, message, code=-3200):
        """
        Sends a custom error back to the requester.
        """

        jsonrpc_response = jsonrpc.JSONRPCCustomError(code, message, self._current_call_id)()

        # add session to the response
        response = [self._current_session, jsonrpc_response]
        log.info("ZeroMQ client ({}) sending JSON-RPC custom error: {} for call id {}".format(self.name,
                                                                                              message,
                                                                                              self._current_call_id))
        self._stream.send_json(response)

    def send_notification(self, destination, results):
        """
        Sends a notification

        :param destination: destination (or method)
        :param results: JSON results to the ZeroMQ router
        """

        jsonrpc_response = jsonrpc.JSONRPCNotification(destination, results)()

        # add session to the response
        response = [self._current_session, jsonrpc_response]
        log.debug("ZeroMQ client ({}) sending: {}".format(self.name, response))
        self._stream.send_json(response)

    def _decode_request(self, request):
        """
        Decodes the request to JSON.

        :param request: request from ZeroMQ server
        """

        # server is shutting down, do not process
        # more request
        if self._stopping:
            return

        # handle special request to stop the module
        # e.g. useful on Windows where the
        # SIGBREAK signal cound't be propagated
        if request[0] == b"stop":
            self.stop()
            return

        try:
            request = zmq.utils.jsonapi.loads(request[0])
        except ValueError:
            self._current_session = None
            self.send_internal_error()
            return

        log.debug("ZeroMQ client ({}) received: {}".format(self.name, request))
        self._current_session = request[0]
        self._current_call_id = request[1].get("id")
        destination = request[1].get("method")
        params = request[1].get("params")

        if destination not in self.modules[self.name]:
            self.send_internal_error()
            return

        log.debug("Routing request to {}: {}".format(destination, request[1]))

        try:
            self.modules[self.name][destination](self, params)
        except Exception as e:
            log.error("uncaught exception {type}".format(type=type(e)), exc_info=1)
            exc_type, exc_value, exc_tb = sys.exc_info()
            lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            tb = "".join(lines)
            self.send_custom_error("uncaught exception {type}: {string}\n{tb}".format(type=type(e),
                                                                                      string=str(e),
                                                                                      tb=tb))

    def validate_request(self, request, schema):
        """
        Validates a request.

        :param request: request (JSON-RPC params)
        :param schema: JSON-SCHEMA to validate the request

        :returns: True or False
        """

        # check if we have a request
        if request is None:
            self.send_param_error()
            return False
        log.debug("received request {}".format(request))

        # validate the request
        try:
            validate(request, schema)
        except ValidationError as e:
            self.send_custom_error("request validation error: {}".format(e))
            return False
        return True

    def destinations(self):
        """
        Destinations handled by this module.

        :returns: list of destinations
        """

        if not self.name in self.modules:
            log.warn("no destinations found for module {}".format(self.name))
            return []
        return self.modules[self.name].keys()

    @classmethod
    def route(cls, destination):
        """
        Decorator to register a destination routed to a method

        :param destination: destination to be routed
        """

        def wrapper(method):
            module = destination.split(".")[0]
            if not module in cls.modules:
                cls.modules[module] = {}
            cls.modules[module][destination] = method
            return method
        return wrapper

    @property
    def images_directory(self):

        return self._images_dir
