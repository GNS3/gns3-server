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
JSON-RPC protocol over Websockets.
"""

import zmq
import uuid
import tornado.websocket
from .auth_handler import GNS3WebSocketBaseHandler
from tornado.escape import json_decode
from ..jsonrpc import JSONRPCParseError
from ..jsonrpc import JSONRPCInvalidRequest
from ..jsonrpc import JSONRPCMethodNotFound
from ..jsonrpc import JSONRPCNotification
from ..jsonrpc import JSONRPCCustomError

import logging
log = logging.getLogger(__name__)


class JSONRPCWebSocket(GNS3WebSocketBaseHandler):
    """
    STOMP protocol over Tornado Websockets with message
    routing to ZeroMQ dealer clients.

    :param application: Tornado Application instance
    :param request: Tornado Request instance
    :param zmq_router: ZeroMQ router socket
    """

    clients = set()
    destinations = {}
    version = 2.0  # only JSON-RPC version 2.0 is supported

    def __init__(self, application, request, zmq_router):
        tornado.websocket.WebSocketHandler.__init__(self, application, request)
        self._session_id = str(uuid.uuid4())
        self.zmq_router = zmq_router

    def check_origin(self, origin):
        return True

    @property
    def session_id(self):
        """
        Session ID uniquely representing a Websocket client

        :returns: the session id
        """

        return self._session_id

    @classmethod
    def dispatch_message(cls, stream, message):
        """
        Sends a message to Websocket client

        :param message: message from a module (received via ZeroMQ)
        """

        # Module name that is replying
        module = message[0].decode("utf-8")

        # ZMQ responses are encoded in JSON
        # format is a JSON array: [session ID, JSON-RPC response]
        try:
            json_message = json_decode(message[1])
        except ValueError as e:
            stream.send_string("Cannot decode message!")
            log.critical("Couldn't decode message: {}".format(e))
            return

        session_id = json_message[0]
        jsonrpc_response = json_message[1]

        log.debug("Received message from module {}: {}".format(module, json_message))

        for client in cls.clients:
            if client.session_id == session_id:
                client.write_message(jsonrpc_response)

    @classmethod
    def register_destination(cls, destination, module):
        """
        Registers a destination handled by a module.
        Used to route requests to the right module.

        :param destination: destination string
        :param module: module string
        """

        # Make sure the destination is not already registered
        # by another module for instance
        assert destination not in cls.destinations
        if destination.startswith("builtin"):
            log.debug("registering {} as a built-in destination".format(destination))
        else:
            log.debug("registering {} as a destination for the {} module".format(destination, module))
        cls.destinations[destination] = module

    def open(self):
        """
        Invoked when a new WebSocket is opened.
        """

        log.info("Websocket client {} connected".format(self.session_id))

        authenticated_user = self.get_current_user()

        if authenticated_user:
            self.clients.add(self)
            log.info("Websocket authenticated user: %s" % (authenticated_user))
        else:
            self.close()
            log.info("Websocket non-authenticated user attempt: %s" % (authenticated_user))

    def on_message(self, message):
        """
        Handles incoming messages.

        :param message: message received over the Websocket
        """

        log.debug("Received Websocket message: {}".format(message))

        if self.zmq_router.closed:
            # no need to proceed, the ZeroMQ router has been closed.
            return

        try:
            request = json_decode(message)
            jsonrpc_version = request["jsonrpc"]
            method = request["method"]
            # This is a JSON-RPC notification if request_id is None
            request_id = request.get("id")
        except:
            return self.write_message(JSONRPCParseError()())

        if jsonrpc_version != self.version:
            return self.write_message(JSONRPCInvalidRequest()())

        if len(self.clients) > 1:
            #TODO: multiple client support
            log.warn("GNS3 server doesn't support multiple clients yet")
            return self.write_message(JSONRPCCustomError(-3200,
                                                         "There are {} clients connected, the GNS3 server cannot handle multiple clients yet".format(len(self.clients)),
                                                         request_id)())

        if method not in self.destinations:
            if request_id:
                log.warn("JSON-RPC method not found: {}".format(method))
                return self.write_message(JSONRPCMethodNotFound(request_id)())
            else:
                # This is a notification, silently ignore this error...
                return

        if method.startswith("builtin") and request_id:
            log.info("calling built-in method {}".format(method))
            self.destinations[method](self, request_id, request.get("params"))
            return

        module = self.destinations[method]
        # ZMQ requests are encoded in JSON
        # format is a JSON array: [session ID, JSON-RPC request]
        zmq_request = [self.session_id, request]
        # Route to the correct module
        self.zmq_router.send_string(module, zmq.SNDMORE)
        # Send the JSON request
        self.zmq_router.send_json(zmq_request)

    def on_close(self):
        """
        Invoked when the WebSocket is closed.
        """

        log.info("Websocket client {} disconnected".format(self.session_id))
        self.clients.remove(self)

        # Reset the modules if there are no clients anymore
        # Modules must implement a reset destination
        if not self.clients and not self.zmq_router.closed:
            for destination, module in self.destinations.items():
                if destination.endswith("reset"):
                    # Route to the correct module
                    self.zmq_router.send_string(module, zmq.SNDMORE)
                    # Send the JSON request
                    notification = JSONRPCNotification(destination)()
                    self.zmq_router.send_json([self.session_id, notification])
