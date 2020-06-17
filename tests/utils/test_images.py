# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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

import os
import sys
import threading
from unittest.mock import patch


from gns3server.utils import force_unix_path
from gns3server.utils.images import md5sum, remove_checksum, images_directories, list_images


def test_images_directories(tmpdir):

    path1 = tmpdir / "images1" / "QEMU" / "test1.bin"
    path1.write("1", ensure=True)
    path1 = force_unix_path(str(path1))

    path2 = tmpdir / "images2" / "test2.bin"
    path2.write("1", ensure=True)
    path2 = force_unix_path(str(path2))

    with patch("gns3server.config.Config.get_section_config", return_value={
            "images_path": str(tmpdir / "images1"),
            "additional_images_path": "/tmp/null24564;{}".format(tmpdir / "images2"),
            "local": False}):

        # /tmp/null24564 is ignored because doesn't exists
        res = images_directories("qemu")
        assert res[0] == force_unix_path(str(tmpdir / "images1" / "QEMU"))
        assert res[1] == force_unix_path(str(tmpdir / "images2"))
        assert res[2] == force_unix_path(str(tmpdir / "images1"))
        assert len(res) == 3


def test_md5sum(tmpdir):

    fake_img = str(tmpdir / 'hello载')

    with open(fake_img, 'w+') as f:
        f.write('hello')

    assert md5sum(fake_img) == '5d41402abc4b2a76b9719d911017c592'
    with open(str(tmpdir / 'hello载.md5sum')) as f:
        assert f.read() == '5d41402abc4b2a76b9719d911017c592'


def test_md5sum_stopped_event(tmpdir):

    fake_img = str(tmpdir / 'hello_stopped')
    with open(fake_img, 'w+') as f:
        f.write('hello')

    event = threading.Event()
    event.set()

    assert md5sum(fake_img, stopped_event=event) is None
    assert not os.path.exists(str(tmpdir / 'hello_stopped.md5sum'))


def test_md5sum_existing_digest(tmpdir):

    fake_img = str(tmpdir / 'hello')

    with open(fake_img, 'w+') as f:
        f.write('hello')

    with open(str(tmpdir / 'hello.md5sum'), 'w+') as f:
        f.write('aaaaa02abc4b2a76b9719d911017c592')

    assert md5sum(fake_img) == 'aaaaa02abc4b2a76b9719d911017c592'


def test_md5sum_existing_digest_but_missing_image(tmpdir):

    fake_img = str(tmpdir / 'hello')

    with open(str(tmpdir / 'hello.md5sum'), 'w+') as f:
        f.write('aaaaa02abc4b2a76b9719d911017c592')

    assert md5sum(fake_img) is None


def test_md5sum_none(tmpdir):

    assert md5sum(None) is None


def test_remove_checksum(tmpdir):

    with open(str(tmpdir / 'hello.md5sum'), 'w+') as f:
        f.write('aaaaa02abc4b2a76b9719d911017c592')
    remove_checksum(str(tmpdir / 'hello'))

    assert not os.path.exists(str(tmpdir / 'hello.md5sum'))

    remove_checksum(str(tmpdir / 'not_exists'))


def test_list_images(tmpdir):

    path1 = tmpdir / "images1" / "IOS" / "test1.image"
    path1.write(b'\x7fELF\x01\x02\x01', ensure=True)
    path1 = force_unix_path(str(path1))

    path2 = tmpdir / "images2" / "test2.image"
    path2.write(b'\x7fELF\x01\x02\x01', ensure=True)
    path2 = force_unix_path(str(path2))

    # Invalid image because not a valid elf file
    path = tmpdir / "images2" / "test_invalid.image"
    path.write(b'NOTANELF', ensure=True)

    if sys.platform.startswith("linux"):
        path3 = tmpdir / "images1" / "IOU" / "test3.bin"
        path3.write(b'\x7fELF\x01\x02\x01', ensure=True)
        path3 = force_unix_path(str(path3))

    path4 = tmpdir / "images1" / "QEMU" / "test4.qcow2"
    path4.write("1", ensure=True)
    path4 = force_unix_path(str(path4))

    path5 = tmpdir / "images1" / "QEMU" / "test4.qcow2.md5sum"
    path5.write("1", ensure=True)
    path5 = force_unix_path(str(path5))

    with patch("gns3server.config.Config.get_section_config", return_value={
            "images_path": str(tmpdir / "images1"),
            "additional_images_path": "/tmp/null24564;{}".format(str(tmpdir / "images2")),
            "local": False}):

        assert list_images("dynamips") == [
            {
                'filename': 'test1.image',
                'filesize': 7,
                'md5sum': 'b0d5aa897d937aced5a6b1046e8f7e2e',
                'path': 'test1.image'
            },
            {
                'filename': 'test2.image',
                'filesize': 7,
                'md5sum': 'b0d5aa897d937aced5a6b1046e8f7e2e',
                'path': str(path2)
            }
        ]

        if sys.platform.startswith("linux"):
            assert list_images("iou") == [
                {
                    'filename': 'test3.bin',
                    'filesize': 7,
                    'md5sum': 'b0d5aa897d937aced5a6b1046e8f7e2e',
                    'path': 'test3.bin'
                }
            ]

        assert list_images("qemu") == [
            {
                'filename': 'test4.qcow2',
                'filesize': 1,
                'md5sum': 'c4ca4238a0b923820dcc509a6f75849b',
                'path': 'test4.qcow2'
            }
        ]
