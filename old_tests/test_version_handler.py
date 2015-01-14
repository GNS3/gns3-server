from tornado.testing import AsyncHTTPTestCase
from tornado.escape import json_decode
from gns3server.server import VersionHandler
from gns3server.version import __version__
import tornado.web

"""
Tests for the web server version handler
"""


class TestVersionHandler(AsyncHTTPTestCase):

    URL = "/version"

    def get_app(self):

        return tornado.web.Application([(self.URL, VersionHandler)])

    def test_endpoint(self):
        """
        Tests if the response HTTP code is 200 (success)
        """

        self.http_client.fetch(self.get_url(self.URL), self.stop)
        response = self.wait()
        assert response.code == 200

    def test_received_version(self):
        """
        Tests if the returned content type is JSON and
        if the received version is the same as the server
        """

        self.http_client.fetch(self.get_url(self.URL), self.stop)
        response = self.wait()
        assert response.headers['Content-Type'].startswith('application/json')
        assert response.body
        body = json_decode(response.body)
        assert body['version'] == __version__
