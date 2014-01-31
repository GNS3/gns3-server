import uuid
from tornado.testing import AsyncTestCase
from tornado.escape import json_encode, json_decode
from ws4py.client.tornadoclient import TornadoWebSocketClient
import gns3server.jsonrpc as jsonrpc

"""
Tests for JSON-RPC protocol over Websockets
"""


class JSONRPC(AsyncTestCase):

    URL = "ws://127.0.0.1:8000/"

    def test_request(self):

        params = {"echo": "test"}
        request = jsonrpc.JSONRPCRequest("dynamips.echo", params)
        AsyncWSRequest(self.URL, self.io_loop, self.stop, str(request))
        response = self.wait()
        json_response = json_decode(response)
        assert json_response["jsonrpc"] == 2.0
        assert json_response["id"] == request.id
        assert json_response["result"] == params

    def test_request_with_invalid_method(self):

        message = {"echo": "test"}
        request = jsonrpc.JSONRPCRequest("dynamips.non_existent", message)
        AsyncWSRequest(self.URL, self.io_loop, self.stop, str(request))
        response = self.wait()
        json_response = json_decode(response)
        assert json_response["error"].get("code") == -32601
        assert json_response["id"] == request.id

    def test_request_with_invalid_version(self):

        request = {"jsonrpc": 1.0, "method": "dynamips.echo", "id": 1}
        AsyncWSRequest(self.URL, self.io_loop, self.stop, json_encode(request))
        response = self.wait()
        json_response = json_decode(response)
        assert json_response["id"] == None
        assert json_response["error"].get("code") == -32600

    def test_request_with_invalid_json(self):

        request = "my non JSON request"
        AsyncWSRequest(self.URL, self.io_loop, self.stop, request)
        response = self.wait()
        json_response = json_decode(response)
        assert json_response["id"] == None
        assert json_response["error"].get("code") == -32700

    def test_request_with_invalid_jsonrpc_field(self):

        request = {"jsonrpc": "2.0", "method_bogus": "dynamips.echo", "id": 1}
        AsyncWSRequest(self.URL, self.io_loop, self.stop, json_encode(request))
        response = self.wait()
        json_response = json_decode(response)
        assert json_response["id"] == None
        assert json_response["error"].get("code") == -32700

    def test_request_with_no_params(self):

        request = jsonrpc.JSONRPCRequest("dynamips.echo")
        AsyncWSRequest(self.URL, self.io_loop, self.stop, str(request))
        response = self.wait()
        json_response = json_decode(response)
        assert json_response["id"] == request.id
        assert json_response["error"].get("code") == -32602


class AsyncWSRequest(TornadoWebSocketClient):
    """
    Very basic Websocket client for tests
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
