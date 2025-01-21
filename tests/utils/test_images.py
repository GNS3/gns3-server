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

    # IOS image in the images directory
    ios_image_1 = tmpdir / "images1" / "IOS" / "ios_image_1.image"
    ios_image_1.write(b'\x7fELF\x01\x02\x01', ensure=True)
    ios_image_1 = force_unix_path(str(ios_image_1))

    # IOS image in an additional images path
    ios_image_2 = tmpdir / "images2" / "ios_image_2.image"
    ios_image_2.write(b'\x7fELF\x01\x02\x01', ensure=True)
    ios_image_2 = force_unix_path(str(ios_image_2))

    # Not a valid elf file
    not_elf_file = tmpdir / "images1" / "IOS" / "not_elf.image"
    not_elf_file.write(b'NOTANELF', ensure=True)
    not_elf_file = force_unix_path(str(not_elf_file))

    # Invalid image because it is very small
    small_file = tmpdir / "images1" / "too_small.image"
    small_file.write(b'1', ensure=True)

    if sys.platform.startswith("linux"):
        # 64-bit IOU image
        iou_image_1 = tmpdir / "images1" / "IOU" / "iou64.bin"
        iou_image_1.write(b'\x7fELF\x02\x01\x01', ensure=True)
        iou_image_1 = force_unix_path(str(iou_image_1))
        # 32-bit IOU image
        iou_image_2 = tmpdir / "images1" / "IOU" / "iou32.bin"
        iou_image_2.write(b'\x7fELF\x01\x01\x01', ensure=True) # 32-bit IOU image
        iou_image_2 = force_unix_path(str(iou_image_2))


    # Qemu image
    qemu_image_1 = tmpdir / "images1" / "QEMU" / "qemu_image.qcow2"
    qemu_image_1.write("1234567", ensure=True)
    qemu_image_1 = force_unix_path(str(qemu_image_1))

    # ELF file inside the Qemu
    elf_file = tmpdir / "images1" / "QEMU" / "elf_file.bin"
    elf_file.write(b'\x7fELF\x02\x01\x01', ensure=True)  # ELF file
    elf_file = force_unix_path(str(elf_file))

    md5sum_file = tmpdir / "images1" / "QEMU" / "image.qcow2.md5sum"
    md5sum_file.write("1", ensure=True)
    md5sum_file = force_unix_path(str(md5sum_file))

    with patch("gns3server.config.Config.get_section_config", return_value={
            "images_path": str(tmpdir / "images1"),
            "additional_images_path": "/tmp/null24564;{}".format(str(tmpdir / "images2")),
            "local": False}):

        assert sorted(list_images("dynamips"), key=lambda k: k['filename']) == [
            {
                'filename': 'ios_image_1.image',
                'filesize': 7,
                'md5sum': 'b0d5aa897d937aced5a6b1046e8f7e2e',
                'path': 'ios_image_1.image'
            },
            {
                'filename': 'ios_image_2.image',
                'filesize': 7,
                'md5sum': 'b0d5aa897d937aced5a6b1046e8f7e2e',
                'path': str(ios_image_2)
            }
        ]

        if sys.platform.startswith("linux"):
            assert sorted(list_images("iou"), key=lambda k: k['filename']) == [
                {
                    'filename': 'iou32.bin',
                    'filesize': 7,
                    'md5sum': 'e573e8f5c93c6c00783f20c7a170aa6c',
                    'path': 'iou32.bin'
                },
                {
                    'filename': 'iou64.bin',
                    'filesize': 7,
                    'md5sum': 'c73626d23469519894d58bc98bee9655',
                    'path': 'iou64.bin'
                },
            ]

        assert sorted(list_images("qemu"), key=lambda k: k['filename']) == [
            {
                'filename': 'qemu_image.qcow2',
                'filesize': 7,
                'md5sum': 'fcea920f7412b5da7be0cf42b8c93759',
                'path': 'qemu_image.qcow2'
            }
        ]
