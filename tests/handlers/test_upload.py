# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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


import aiohttp
import os
from unittest.mock import patch
from gns3server.config import Config

def test_index_upload(server):
    response = server.get('/upload', api_version=None)
    assert response.status == 200
    html = response.html
    assert "GNS3 Server" in html
    assert "Select & Upload" in html


def test_upload(server, tmpdir):

    with open(str(tmpdir / "test"), "w+") as f:
        f.write("TEST")
    body = aiohttp.FormData()
    body.add_field("type", "QEMU")
    body.add_field("file", open(str(tmpdir / "test"), "rb"), content_type="application/iou", filename="test2")

    Config.instance().set("Server", "images_path", str(tmpdir))
    response = server.post('/upload', api_version=None, body=body, raw=True)

    with open(str(tmpdir / "QEMU" / "test2")) as f:
        assert f.read() == "TEST"

    assert "test2" in response.body.decode("utf-8")
