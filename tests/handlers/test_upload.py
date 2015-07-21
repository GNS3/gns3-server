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
import asyncio
import os
import tarfile
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


def test_backup_images(server, tmpdir, loop):
    Config.instance().set('Server', 'images_path', str(tmpdir))

    os.makedirs(str(tmpdir / 'QEMU'))
    with open(str(tmpdir / 'QEMU' / 'a.img'), 'w+') as f:
        f.write('hello')
    with open(str(tmpdir / 'QEMU' / 'b.img'), 'w+') as f:
        f.write('world')

    response = server.get('/upload/backup/images.tar', api_version=None, raw=True)
    assert response.status == 200
    assert response.headers['CONTENT-TYPE'] == 'application/x-gtar'

    with open(str(tmpdir / 'images.tar'), 'wb+') as f:
        print(len(response.body))
        f.write(response.body)

    tar = tarfile.open(str(tmpdir / 'images.tar'), 'r')
    os.makedirs(str(tmpdir / 'extract'))
    os.chdir(str(tmpdir / 'extract'))
    # Extract to current working directory
    tar.extractall()
    tar.close()

    assert os.path.exists(os.path.join('QEMU', 'a.img'))
    open(os.path.join('QEMU', 'a.img')).read() == 'hello'

    assert os.path.exists(os.path.join('QEMU', 'b.img'))
    open(os.path.join('QEMU', 'b.img')).read() == 'world'


def test_backup_projects(server, tmpdir, loop):
    Config.instance().set('Server', 'projects_path', str(tmpdir))

    os.makedirs(str(tmpdir / 'a'))
    with open(str(tmpdir / 'a' / 'a.gns3'), 'w+') as f:
        f.write('hello')
    os.makedirs(str(tmpdir / 'b'))
    with open(str(tmpdir / 'b' / 'b.gns3'), 'w+') as f:
        f.write('world')

    response = server.get('/upload/backup/projects.tar', api_version=None, raw=True)
    assert response.status == 200
    assert response.headers['CONTENT-TYPE'] == 'application/x-gtar'

    with open(str(tmpdir / 'projects.tar'), 'wb+') as f:
        print(len(response.body))
        f.write(response.body)

    tar = tarfile.open(str(tmpdir / 'projects.tar'), 'r')
    os.makedirs(str(tmpdir / 'extract'))
    os.chdir(str(tmpdir / 'extract'))
    # Extract to current working directory
    tar.extractall()
    tar.close()

    assert os.path.exists(os.path.join('a', 'a.gns3'))
    open(os.path.join('a', 'a.gns3')).read() == 'hello'

    assert os.path.exists(os.path.join('b', 'b.gns3'))
    open(os.path.join('b', 'b.gns3')).read() == 'world'
