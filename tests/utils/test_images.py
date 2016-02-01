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

from gns3server.utils.images import md5sum, remove_checksum


def test_md5sum(tmpdir):
    fake_img = str(tmpdir / 'hello载')

    with open(fake_img, 'w+') as f:
        f.write('hello')

    assert md5sum(fake_img) == '5d41402abc4b2a76b9719d911017c592'
    with open(str(tmpdir / 'hello载.md5sum')) as f:
        assert f.read() == '5d41402abc4b2a76b9719d911017c592'


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
