from tornado.testing import AsyncHTTPTestCase
#from gns3server.plugins.dynamips import Dynamips
#from gns3server._compat import urlencode
from functools import partial
import tornado.web
import json
import tempfile


# class TestVMHandler(AsyncHTTPTestCase):
#
#     def setUp(self):
#
#         AsyncHTTPTestCase.setUp(self)
#         self.post_request = partial(self.http_client.fetch,
#                                     self.get_url("/api/vms/dynamips"),
#                                     self.stop,
#                                     method="POST")
#
#     def get_app(self):
#         return tornado.web.Application(Dynamips().handlers())
#
#     def test_endpoint(self):
#         self.http_client.fetch(self.get_url("/api/vms/dynamips"), self.stop)
#         response = self.wait()
#         assert response.code == 200
#
#     def test_upload(self):
#
#         try:
#             from poster.encode import multipart_encode
#         except ImportError:
#             # poster isn't available for Python 3, let's just ignore the test
#             return
#
#         file_to_upload = tempfile.NamedTemporaryFile()
#         data, headers = multipart_encode({"file1": file_to_upload})
#         body = ""
#         for d in data:
#             body += d
#
#         response = self.fetch('/api/vms/dynamips/storage/upload',
#                               headers=headers,
#                               body=body,
#                               method='POST')
#
#         assert response.code == 200
#
#     def get_new_ioloop(self):
#         return tornado.ioloop.IOLoop.instance()
#
#     def test_create_vm(self):
#
#         post_data = {"name": "R1",
#                      "platform": "c3725",
#                      "console": 2000,
#                      "aux": 3000,
#                      "image": "c3725.bin",
#                      "ram": 128}
#
#         self.post_request(body=json.dumps(post_data))
#         response = self.wait()
#         assert(response.headers['Content-Type'].startswith('application/json'))
#         expected = {"success": True}
#         assert response.body.decode("utf-8") == json.dumps(expected)
