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
from tornado.escape import json_decode
from ..jsonrpc import JSONRPCParseError, JSONRPCInvalidRequest, JSONRPCMethodNotFound

import logging
log = logging.getLogger(__name__)


class JSONRPCWebSocket(tornado.websocket.WebSocketHandler):
    """
    STOMP protocol over Tornado Websockets with message
    routing to ZeroMQ dealer clients.

    :param application: Tornado Application object
    :param request: Tornado Request object
    :param zmq_router: ZeroMQ router socket
    """

    clients = set()
    destinations = {}
    version = 2.0  # only JSON-RPC version 2.0 is supported

    def __init__(self, application, request, zmq_router):
        tornado.websocket.WebSocketHandler.__init__(self, application, request)
        self._session_id = str(uuid.uuid4())
        self.zmq_router = zmq_router

    @property
    def session_id(self):
        """
        Session ID uniquely representing a Websocket client

        :returns: the session id
        """

        return self._session_id

    @classmethod
    def dispatch_message(cls, message):
        """
        Sends a message to Websocket client

        :param message: message from a module (received via ZeroMQ)
        """

        # Module name that is replying
        module = message[0].decode("utf-8")

        # ZMQ responses are encoded in JSON
        # format is a JSON array: [session ID, JSON-RPC response]
        json_message = json_decode(message[1])
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
        log.info("registering {} as a destination for {}".format(destination,
                                                                 module))
        cls.destinations[destination] = module

    def open(self):
        """
        Invoked when a new WebSocket is opened.
        """

        log.info("Websocket client {} connected".format(self.session_id))
        self.clients.add(self)

    def on_message(self, message):
        """
        Handles incoming messages.

        :param message: message received over the Websocket
        """

        log.debug("Received Websocket message: {}".format(message))

        try:
            request = json_decode(message)
            jsonrpc_version = request["jsonrpc"]
            method = request["method"]
            # warning: notifications cannot be sent by a client because check for an "id" here
            request_id = request["id"]
        except:
            return self.write_message(JSONRPCParseError()())

        if jsonrpc_version != self.version:
            return self.write_message(JSONRPCInvalidRequest()())

        if method not in self.destinations:
            return self.write_message(JSONRPCMethodNotFound(request_id)())

        module = self.destinations[method]
        # ZMQ requests are encoded in JSON
        # format is a JSON array: [session ID, JSON-RPC request]
        zmq_request = [self.session_id, request]
        # Route to the correct module
        self.zmq_router.send_string(module, zmq.SNDMORE)
        # Send the encoded JSON request
        self.zmq_router.send_json(zmq_request)

    def on_close(self):
        """
        Invoked when the WebSocket is closed.
        """

        log.info("Websocket client {} disconnected".format(self.session_id))
        self.clients.remove(self)
