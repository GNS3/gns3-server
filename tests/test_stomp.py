import uuid
from tornado.testing import AsyncTestCase
from tornado.escape import json_encode, json_decode
from ws4py.client.tornadoclient import TornadoWebSocketClient
from gns3server.stomp import frame as stomp_frame
from gns3server.stomp import protocol as stomp_protocol

"""
Tests STOMP protocol over Websockets
"""


class Stomp(AsyncTestCase):

    URL = "ws://127.0.0.1:8000/"

    def setUp(self):

        self.stomp = stomp_protocol.clientProtocol()
        AsyncTestCase.setUp(self)

    def test_connect(self):
        """
        Sends a STOMP CONNECT frame and
        check for a STOMP CONNECTED frame.
        """

        request = self.stomp.connect("localhost")
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_CONNECTED

    def test_protocol_negotiation_failure(self):
        """
        Sends a STOMP CONNECT frame with protocol version 1.0 required
        and check for a STOMP ERROR sent back by the server which supports
        STOMP version 1.2 only.
        """

        request = self.stomp.connect("localhost", accept_version='1.0')
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_ERROR

    def test_malformed_frame(self):
        """
        Sends an empty frame and check for a STOMP ERROR.
        """

        request = b""
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_ERROR

    def test_send(self):
        """
        Sends a STOMP SEND frame with a message and a destination
        and check for a STOMP MESSAGE with echoed message and destination.
        """

        destination = "dynamips/echo"
        message = {"ping": "test"}
        request = self.stomp.send(destination, json_encode(message), "application/json")
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_MESSAGE
        assert frame.headers[stomp_protocol.HDR_DESTINATION] == destination
        json_reply = json_decode(frame.body)
        assert message == json_reply

    def test_unimplemented_frame(self):
        """
        Sends an STOMP BEGIN frame which is not implemented by the server
        and check for a STOMP ERROR frame.
        """

        frame = stomp_frame.Frame(stomp_protocol.CMD_BEGIN)
        request = frame.encode()
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_ERROR

    def test_disconnect(self):
        """
        Sends a STOMP DISCONNECT frame is a receipt id
        and check for a STOMP RECEIPT frame with the same receipt id
        confirming the disconnection.
        """

        myid = str(uuid.uuid4())
        request = self.stomp.disconnect(myid)
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_RECEIPT
        assert frame.headers[stomp_protocol.HDR_RECEIPT_ID] == myid


class AsyncWSRequest(TornadoWebSocketClient):
    """
    Very basic Websocket client for the tests
    """

    def __init__(self, url, io_loop, callback, message):
        TornadoWebSocketClient.__init__(self, url, io_loop=io_loop)
        self._callback = callback
        self._message = message
        self.connect()

    def opened(self):
        self.send(self._message, binary=False)

    def received_message(self, message):
        self.close()
        if self._callback:
            self._callback(message.data)
