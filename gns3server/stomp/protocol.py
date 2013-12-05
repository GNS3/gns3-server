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
Basic STOMP 1.2 protocol implementation
http://stomp.github.io/stomp-specification-1.2.html
"""

import uuid
from .frame import Frame
from .utils import encode, hasbyte

# Commands server-side
CMD_CONNECTED = 'CONNECTED'
CMD_ERROR = 'ERROR'
CMD_MESSAGE = 'MESSAGE'
CMD_RECEIPT = 'RECEIPT'

# Commands client-side
CMD_STOMP = 'STOMP'
CMD_CONNECT = 'CONNECT'
CMD_DISCONNECT = 'DISCONNECT'
CMD_SEND = 'SEND'

# Commands not supported
CMD_SUBSCRIBE = 'SUBSCRIBE'
CMD_UNSUBSCRIBE = 'UNSUBSCRIBE'
CMD_ACK = 'ACK'
CMD_NACK = 'NACK'
CMD_BEGIN = 'BEGIN'
CMD_ABORT = 'ABORT'

# Headers
HDR_VERSION = 'version'
HDR_SESSION = 'session'
HDR_SERVER = 'server'
HDR_CONTENT_TYPE = 'content-type'
HDR_CONTENT_LENGTH = 'content-length'
HDR_RECEIPT_ID = 'receipt-id'
HDR_MESSAGE = 'message'
HDR_MESSAGE_ID = 'message-id'
HDR_ACCEPT_VERSION = 'accept-version'
HDR_HOST = 'host'
HDR_DESTINATION = 'destination'
HDR_RECEIPT = 'receipt'

# Headers not supported
HDR_HEARTBEAT = 'heart-beat'
HDR_LOGIN = 'login'
HDR_PASSCODE = 'passcode'
HDR_ID = 'id'
HDR_ACK = 'ack'
HDR_SUBSCRIPTION = 'subscription'
HDR_TRANSACTION = 'transaction'


class serverProtocol(object):
        """
        STOMP 1.2 protocol support for servers.
        """

        def __init__(self):

            # STOMP protocol version
            self.version = 1.2

        def connected(self, session=None, server=None):
            """
            Replies to the CONNECT or STOMP command.
            Heart-beat header is not supported.

            :param session: A session identifier that uniquely identifies the session.
            :param server:  A field that contains information about the STOMP server.
            :returns: STOMP Frame object
            """

            # Version header is required
            headers = {HDR_VERSION: self.version}

            if session:
                headers[HDR_SESSION] = session

            # The server-name field consists of a name token followed by an
            # optional version number token. Example: Apache/1.3.9
            if server:
                headers[HDR_SERVER] = server

            return Frame(CMD_CONNECTED, headers).encode()

        def message(self, destination, body, content_type=None, message_id=str(uuid.uuid4())):
            """
            Sends a message to a STOMP client.

            :param destination: Destination string
            :param body: Data to be added in the frame body
            :param content_type: MIME type which describes the format of the body
            :param message_id: Unique identifier for that message
            :returns: STOMP Frame object
            """

            # Destination and message id headers are required
            headers = {HDR_DESTINATION: destination,
                       HDR_MESSAGE_ID: message_id}

            # Subscription is required but not implemented on this server
            headers[HDR_SUBSCRIPTION] = 0

            if content_type:
                headers[HDR_CONTENT_TYPE] = content_type

            body = encode(body)
            if HDR_CONTENT_LENGTH not in headers and hasbyte(0, body):
                headers[HDR_CONTENT_LENGTH] = len(body)

            return Frame(CMD_MESSAGE, headers, body).encode()

        def receipt(self, receipt_id):
            """
            Sends an acknowledgment for client frame that requests a receipt.

            :param receipt_id: Receipt ID to send back to the client
            :returns: STOMP Frame object
            """

            # Receipt ID header is required (the same sent in the client frame)
            headers = {HDR_RECEIPT_ID: receipt_id}
            return Frame(CMD_RECEIPT, headers).encode()

        def error(self, message='', body='', content_type=None):
            """
            Sends an error to the client if something goes wrong.

            :param message: Short description of the error
            :param body: Detailed information
            :param content_type: MIME type which describes the format of the body
            :returns: STOMP Frame object
            """

            headers = {}
            if message:
                headers[HDR_MESSAGE] = message

            if body:
                body = encode(body)
                if HDR_CONTENT_LENGTH not in headers and hasbyte(0, body):
                    headers[HDR_CONTENT_LENGTH] = len(body)
                if content_type:
                    headers[HDR_CONTENT_TYPE] = content_type

            return Frame(CMD_ERROR, headers, body).encode()


class clientProtocol(object):
        """
        STOMP 1.2 protocol support for clients.
        """

        def connect(self, host, accept_version='1.2'):
            """
            Connects to a STOMP server.
            Heart-beat, login and passcode headers are not supported.

            :param host: Host name that the socket was established against.
            :param accept_version: The versions of the STOMP protocol the client supports.
            :returns: STOMP Frame object
            """

            # Currently only STOMP 1.2 is supported (required header)
            headers = {HDR_ACCEPT_VERSION: accept_version}

            if host:
                headers[HDR_HOST] = host

            # The STOMP command is not backward compatible with STOMP 1.0 servers.
            # Clients that use the STOMP frame instead of the CONNECT frame will
            # only be able to connect to STOMP 1.2 servers (as well as some STOMP 1.1 servers.
            return Frame(CMD_STOMP, headers).encode()

        def disconnect(self, receipt=str(uuid.uuid4())):
            """
            Disconnects to a STOMP server.

            :param receipt: unique identifier
            :returns: STOMP Frame object
            """

            # Receipt header is required
            headers = {HDR_RECEIPT: receipt}
            return Frame(CMD_DISCONNECT, headers).encode()

        def send(self, destination, body, content_type=None):
            """
            Sends a message to a destination in the messaging system.
            Transaction header is not supported.
            User defined headers are not supported too (against the protocol specification)

            :param destination: Destination string
            :param body: Data to be added in the frame body
            :param content_type: MIME type which describes the format of the body
            :returns: STOMP Frame object
            """

            # Destination header is required
            headers = {HDR_DESTINATION: destination}

            if content_type:
                headers[HDR_CONTENT_TYPE] = content_type

            body = encode(body)
            if HDR_CONTENT_LENGTH not in headers and hasbyte(0, body):
                headers[HDR_CONTENT_LENGTH] = len(body)

            return Frame(CMD_SEND, headers, body).encode()
