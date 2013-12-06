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
STOMP protocol over Websockets
"""

import zmq
import uuid
import tornado.websocket
from tornado.escape import json_decode
from ..version import __version__
from ..stomp import frame as stomp_frame
from ..stomp import protocol as stomp_protocol

import logging
log = logging.getLogger(__name__)


class StompWebSocket(tornado.websocket.WebSocketHandler):
    """
    STOMP protocol over Tornado Websockets with message
    routing to ZeroMQ dealer clients.

    :param application: Tornado Application object
    :param request: Tornado Request object
    :param zmq_router: ZeroMQ router socket
    """

    clients = set()
    destinations = {}
    stomp = stomp_protocol.serverProtocol()

    def __init__(self, application, request, zmq_router):
        tornado.websocket.WebSocketHandler.__init__(self, application, request)
        self._session_id = str(uuid.uuid4())
        self._connected = False
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

        # ZMQ requests are encoded in JSON
        # format is a JSON array: [session ID, destination, JSON dict]
        json_message = json_decode(message[1])
        session_id = json_message[0]
        destination = json_message[1]
        content = json_message[2]

        log.debug("Received message from module {}: {}".format(module,
                                                               json_message))

        stomp_msg = cls.stomp.message(destination,
                                      content,
                                      "application/json")
        for client in cls.clients:
            if client.session_id == session_id:
                client.write_message(stomp_msg)

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

    def stomp_handle_connect(self, frame):
        """
        Handles a STOMP CONNECT frame and returns a STOMP CONNECTED frame.

        :param frame: received STOMP CONNECT frame (object)
        """

        if not stomp_protocol.HDR_ACCEPT_VERSION in frame.headers or \
        not str(self.stomp.version) in frame.headers[stomp_protocol.HDR_ACCEPT_VERSION]:
            self.stomp_error("STOMP version error",
                             "Supported protocol version is {}".format(self.stomp.version),)
        else:
            self.write_message(self.stomp.connected(self.session_id,
                                                    'gns3server/' + __version__))
            self._connected = True

    def stomp_handle_send(self, frame):
        """
        Handles a STOMP SEND frame and dispatches it to the right module
        based on the destination.

        :param frame: received STOMP SEND frame (object)
        """

        if stomp_protocol.HDR_DESTINATION not in frame.headers:
            self.stomp_error("No destination header in SEND frame")
            return

        destination = frame.headers[stomp_protocol.HDR_DESTINATION]
        if not destination:
            self.stomp_error("Destination header is empty in SEND frame")
            return

        if destination not in self.destinations:
            self.stomp_error("Destination {} doesn't exist".format(destination))
            return

        if not frame.body:
            self.stomp_error("SEND frame has no body")
            return

        module = self.destinations[destination]
        # ZMQ requests are encoded in JSON
        # format is a JSON array: [session ID, destination, JSON dict]
        zmq_request = [self.session_id, destination, frame.body]
        # Route to the correct module
        self.zmq_router.send_string(module, zmq.SNDMORE)
        # Send the encoded JSON request
        self.zmq_router.send_json(zmq_request)

    def stomp_handle_disconnect(self, frame):
        """
        Sends an STOMP RECEIPT frame back to the client when receiving a disconnection
        request and close the connection.

        :param frame: received STOMP DISCONNECT frame (object)
        """

        if stomp_protocol.HDR_RECEIPT not in frame.headers:
            self.stomp_error("No receipt header in DISCONNECT frame")
            return

        receipt = self.stomp.receipt(frame.headers[stomp_protocol.HDR_RECEIPT])
        self.write_message(receipt)
        self.close()
        log.info("Websocket client {} gracefully disconnected".format(self.session_id))
        self.clients.remove(self)

    def stomp_error(self, short_description='', detailed_info='', content_type="text/plain"):
        """
        Sends an STOMP error message back to the client and close the connection.

        :param short_description: short description of the error
        :param detailed_info: detailed description of the error
        :param content_type: MIME type which describes the format of the detailed info
        """

        error = self.stomp.error(short_description, detailed_info, content_type)
        self.write_message(error)
        self.close()
        log.warning("Websocket client {} disconnected on an error: {}".format(self.session_id,
                                                                              short_description))
        self.clients.remove(self)

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
            frame = stomp_frame.Frame.parse_frame(message)
        except Exception:
            self.stomp_error("Malformed STOMP frame")
            return

        if frame.cmd == stomp_protocol.CMD_STOMP or frame.cmd == stomp_protocol.CMD_CONNECT:
            self.stomp_handle_connect(frame)

        # Do not enforce that the client must have send a
        # STOMP CONNECT frame for now (need to refactor unit tests)
        #elif not self._connected:
        #    self.stomp_error("Not connected")

        elif frame.cmd == stomp_protocol.CMD_SEND:
            self.stomp_handle_send(frame)

        elif frame.cmd == stomp_protocol.CMD_DISCONNECT:
            self.stomp_handle_disconnect(frame)

        else:
            self.stomp_error("STOMP frame not implemented")

    def on_close(self):
        """
        Invoked when the WebSocket is closed.
        """

        log.info("Websocket client {} disconnected".format(self.session_id))
        self.clients.remove(self)
