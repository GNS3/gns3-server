import uuid
from tornado.testing import AsyncTestCase
from tornado.escape import json_encode, json_decode
from ws4py.client.tornadoclient import TornadoWebSocketClient
from gns3server.stomp import frame as stomp_frame
from gns3server.stomp import protocol as stomp_protocol


class Stomp(AsyncTestCase):

    URL = "ws://127.0.0.1:8000/"

    def setUp(self):

        self.stomp = stomp_protocol.clientProtocol()
        AsyncTestCase.setUp(self)

    def test_connect(self):

        request = self.stomp.connect("localhost")
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_CONNECTED

    def test_protocol_negotiation_failure(self):

        request = self.stomp.connect("localhost", accept_version='1.0')
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_ERROR

    def test_malformed_frame(self):

        request = b""
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_ERROR

    def test_send(self):

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

        frame = stomp_frame.Frame(stomp_protocol.CMD_BEGIN)
        request = frame.encode()
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_ERROR

    def test_disconnect(self):

        myid = str(uuid.uuid4())
        request = self.stomp.disconnect(myid)
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        assert response
        frame = stomp_frame.Frame.parse_frame(response.decode("utf-8"))
        assert frame.cmd == stomp_protocol.CMD_RECEIPT
        assert frame.headers[stomp_protocol.HDR_RECEIPT_ID] == myid


class AsyncWSRequest(TornadoWebSocketClient):

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
