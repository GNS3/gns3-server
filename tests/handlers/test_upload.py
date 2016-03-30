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
import pytest
import os
import tarfile
from unittest.mock import patch


from gns3server.config import Config


@pytest.yield_fixture(autouse=True)
def restore_working_dir():
    directory = os.getcwd()
    yield
    os.chdir(directory)


def test_index_upload(server, tmpdir):

    Config.instance().set("Server", "images_path", str(tmpdir))

    open(str(tmpdir / "alpha"), "w+").close()
    open(str(tmpdir / "alpha.md5sum"), "w+").close()
    open(str(tmpdir / ".beta"), "w+").close()

    response = server.get('/upload', api_version=None)
    assert response.status == 200
    html = response.html
    assert "GNS3 Server" in html
    assert "Select & Upload" in html
    assert "alpha" in html
    assert ".beta" not in html
    assert "alpha.md5sum" not in html


def test_upload(server, tmpdir):

    content = ''.join(['a' for _ in range(0, 1025)])

    with open(str(tmpdir / "test"), "w+") as f:
        f.write(content)
    body = aiohttp.FormData()
    body.add_field("type", "QEMU")
    body.add_field("file", open(str(tmpdir / "test"), "rb"), content_type="application/iou", filename="test2")

    Config.instance().set("Server", "images_path", str(tmpdir))

    response = server.post('/upload', api_version=None, body=body, raw=True)

    assert "test2" in response.body.decode("utf-8")

    with open(str(tmpdir / "QEMU" / "test2")) as f:
        assert f.read() == content

    with open(str(tmpdir / "QEMU" / "test2.md5sum")) as f:
        checksum = f.read()
        assert checksum == "ae187e1febee2a150b64849c32d566ca"


def test_upload_previous_checksum(server, tmpdir):

    content = ''.join(['a' for _ in range(0, 1025)])

    with open(str(tmpdir / "test"), "w+") as f:
        f.write(content)
    body = aiohttp.FormData()
    body.add_field("type", "QEMU")
    body.add_field("file", open(str(tmpdir / "test"), "rb"), content_type="application/iou", filename="test2")

    Config.instance().set("Server", "images_path", str(tmpdir))

    os.makedirs(str(tmpdir / "QEMU"))

    with open(str(tmpdir / "QEMU" / "test2.md5sum"), 'w+') as f:
        f.write("FAKE checksum")

    response = server.post('/upload', api_version=None, body=body, raw=True)

    assert "test2" in response.body.decode("utf-8")

    with open(str(tmpdir / "QEMU" / "test2")) as f:
        assert f.read() == content

    with open(str(tmpdir / "QEMU" / "test2.md5sum")) as f:
        checksum = f.read()
        assert checksum == "ae187e1febee2a150b64849c32d566ca"


def test_upload_images_backup(server, tmpdir):
    Config.instance().set("Server", "images_path", str(tmpdir / 'images'))
    os.makedirs(str(tmpdir / 'images' / 'IOU'))
    # An old IOU image that we need to replace
    with open(str(tmpdir / 'images' / 'IOU' / 'b.img'), 'w+') as f:
        f.write('bad')

    os.makedirs(str(tmpdir / 'old' / 'QEMU'))
    with open(str(tmpdir / 'old' / 'QEMU' / 'a.img'), 'w+') as f:
        f.write('hello')
    os.makedirs(str(tmpdir / 'old' / 'IOU'))
    with open(str(tmpdir / 'old' / 'IOU' / 'b.img'), 'w+') as f:
        f.write('world')

    os.chdir(str(tmpdir / 'old'))
    with tarfile.open(str(tmpdir / 'test.tar'), 'w') as tar:
        tar.add('.', recursive=True)

    body = aiohttp.FormData()
    body.add_field('type', 'IMAGES')
    body.add_field('file', open(str(tmpdir / 'test.tar'), 'rb'), content_type='application/x-gtar', filename='test.tar')
    response = server.post('/upload', api_version=None, body=body, raw=True)
    assert response.status == 200

    with open(str(tmpdir / 'images' / 'QEMU' / 'a.img')) as f:
        assert f.read() == 'hello'
    with open(str(tmpdir / 'images' / 'IOU' / 'b.img')) as f:
        assert f.read() == 'world'

    assert 'a.img' in response.body.decode('utf-8')
    assert 'b.img' in response.body.decode('utf-8')
    assert not os.path.exists(str(tmpdir / 'images' / 'archive.tar'))


def test_upload_projects_backup(server, tmpdir):
    Config.instance().set("Server", "projects_path", str(tmpdir / 'projects'))
    os.makedirs(str(tmpdir / 'projects' / 'b'))
    # An old b image that we need to replace
    with open(str(tmpdir / 'projects' / 'b' / 'b.img'), 'w+') as f:
        f.write('bad')

    os.makedirs(str(tmpdir / 'old' / 'a'))
    with open(str(tmpdir / 'old' / 'a' / 'a.img'), 'w+') as f:
        f.write('hello')
    os.makedirs(str(tmpdir / 'old' / 'b'))
    with open(str(tmpdir / 'old' / 'b' / 'b.img'), 'w+') as f:
        f.write('world')

    os.chdir(str(tmpdir / 'old'))
    with tarfile.open(str(tmpdir / 'test.tar'), 'w') as tar:
        tar.add('.', recursive=True)

    body = aiohttp.FormData()
    body.add_field('type', 'PROJECTS')
    body.add_field('file', open(str(tmpdir / 'test.tar'), 'rb'), content_type='application/x-gtar', filename='test.tar')
    response = server.post('/upload', api_version=None, body=body, raw=True)
    assert response.status == 200

    with open(str(tmpdir / 'projects' / 'a' / 'a.img')) as f:
        assert f.read() == 'hello'
    with open(str(tmpdir / 'projects' / 'b' / 'b.img')) as f:
        assert f.read() == 'world'

    assert 'a.img' not in response.body.decode('utf-8')
    assert 'b.img' not in response.body.decode('utf-8')
    assert not os.path.exists(str(tmpdir / 'projects' / 'archive.tar'))


def test_backup_images(server, tmpdir, loop):
    Config.instance().set('Server', 'images_path', str(tmpdir))

    os.makedirs(str(tmpdir / 'QEMU'))
    with open(str(tmpdir / 'QEMU' / 'a.img'), 'w+') as f:
        f.write('hello')
    with open(str(tmpdir / 'QEMU' / 'b.img'), 'w+') as f:
        f.write('world')

    response = server.get('/backup/images.tar', api_version=None, raw=True)
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
    assert open(os.path.join('QEMU', 'a.img')).read() == 'hello'

    assert os.path.exists(os.path.join('QEMU', 'b.img'))
    assert open(os.path.join('QEMU', 'b.img')).read() == 'world'


def test_backup_projects(server, tmpdir, loop):
    Config.instance().set('Server', 'projects_path', str(tmpdir))

    os.makedirs(str(tmpdir / 'a'))
    with open(str(tmpdir / 'a' / 'a.gns3'), 'w+') as f:
        f.write('hello')
    os.makedirs(str(tmpdir / 'b'))
    with open(str(tmpdir / 'b' / 'b.gns3'), 'w+') as f:
        f.write('world')

    response = server.get('/backup/projects.tar', api_version=None, raw=True)
    assert response.status == 200
    assert response.headers['CONTENT-TYPE'] == 'application/x-gtar'

    with open(str(tmpdir / 'projects.tar'), 'wb+') as f:
        f.write(response.body)

    tar = tarfile.open(str(tmpdir / 'projects.tar'), 'r')
    os.makedirs(str(tmpdir / 'extract'))
    os.chdir(str(tmpdir / 'extract'))
    # Extract to current working directory
    tar.extractall()
    tar.close()

    assert os.path.exists(os.path.join('a', 'a.gns3'))
    assert open(os.path.join('a', 'a.gns3')).read() == 'hello'

    assert os.path.exists(os.path.join('b', 'b.gns3'))
    assert open(os.path.join('b', 'b.gns3')).read() == 'world'
