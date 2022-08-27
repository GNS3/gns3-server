#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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
import pytest
import shutil

from gns3server.compute.qemu.utils.qcow2 import Qcow2, Qcow2Error


def qemu_img():
    """
    Return the path of qemu-img on system.
    We can't use shutil.which because for safety reason we break
    the PATH to avoid test interacting with real binaries
    """
    paths = [
        "/usr/bin/qemu-img",
        "/usr/local/bin/qemu-img"
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def test_valid_base_file():

    qcow2 = Qcow2("tests/resources/empty8G.qcow2")
    assert qcow2.version == 3
    assert qcow2.backing_file is None


def test_valid_linked_file():

    qcow2 = Qcow2("tests/resources/linked.qcow2")
    assert qcow2.version == 3
    assert qcow2.backing_file == "empty8G.qcow2"


def test_invalid_file():

    with pytest.raises(Qcow2Error):
        Qcow2("tests/resources/nvram_iou")


def test_invalid_empty_file(tmpdir):

    open(str(tmpdir / 'a'), 'w+').close()
    with pytest.raises(Qcow2Error):
        Qcow2(str(tmpdir / 'a'))


@pytest.mark.skipif(qemu_img() is None, reason="qemu-img is not available")
async def test_rebase(loop, tmpdir):

    shutil.copy("tests/resources/empty8G.qcow2", str(tmpdir / "empty16G.qcow2"))
    shutil.copy("tests/resources/linked.qcow2", str(tmpdir / "linked.qcow2"))
    qcow2 = Qcow2(str(tmpdir / "linked.qcow2"))
    assert qcow2.version == 3
    assert qcow2.backing_file == "empty8G.qcow2"
    await qcow2.rebase(qemu_img(), str(tmpdir / "empty16G.qcow2"), "qcow2")
    assert qcow2.backing_file == str(tmpdir / "empty16G.qcow2")
