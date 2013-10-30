from tornado.testing import AsyncHTTPTestCase
from gns3server.server import VersionHandler
from gns3server._compat import urlencode
import tornado.web
import json

# URL to test
URL = "/version"


class TestVersionHandler(AsyncHTTPTestCase):

    def get_app(self):
        return tornado.web.Application([(URL, VersionHandler)])

    def test_endpoint(self):
        self.http_client.fetch(self.get_url(URL), self.stop)
        response = self.wait()
        assert response.code == 200

#     def test_post(self):
#         data = urlencode({'test': 'works'})
#         req = tornado.httpclient.HTTPRequest(self.get_url(URL),
#                                              method='POST',
#                                              body=data)
#         self.http_client.fetch(req, self.stop)
#         response = self.wait()
#         assert response.code == 200
# 
#     def test_endpoint_differently(self):
#         self.http_client.fetch(self.get_url(URL), self.stop)
#         response = self.wait()
#         assert(response.headers['Content-Type'].startswith('application/json'))
#         assert(response.body != "")
#         body = json.loads(response.body.decode('utf-8'))
#         assert body['version'] == "0.1.dev"

