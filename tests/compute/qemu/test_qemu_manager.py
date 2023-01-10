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

import os
import stat
import pytest
import platform
import sys

from gns3server.compute.qemu import Qemu
from gns3server.compute.qemu.qemu_error import QemuError
from tests.utils import asyncio_patch

from unittest.mock import patch, MagicMock


@pytest.fixture
def fake_qemu_img_binary(tmpdir):

    if sys.platform.startswith("win"):
        bin_path = str(tmpdir / "qemu-img.EXE")
    else:
        bin_path = str(tmpdir / "qemu-img")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


@pytest.mark.asyncio
async def test_get_qemu_version():

    with asyncio_patch("gns3server.compute.qemu.subprocess_check_output", return_value="QEMU emulator version 2.2.0, Copyright (c) 2003-2008 Fabrice Bellard"):
        version = await Qemu.get_qemu_version("/tmp/qemu-test")
        assert version == "2.2.0"


@pytest.mark.asyncio
async def test_binary_list(monkeypatch, tmpdir):

    monkeypatch.setenv("PATH", str(tmpdir))
    files_to_create = ["qemu-system-x86", "qemu-system-x42", "qemu-kvm", "hello", "qemu-system-x86_64-spice"]

    for file_to_create in files_to_create:
        path = os.path.join(os.environ["PATH"], file_to_create)
        with open(path, "w+") as f:
            f.write("1")
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    with asyncio_patch("gns3server.compute.qemu.subprocess_check_output", return_value="QEMU emulator version 2.2.0, Copyright (c) 2003-2008 Fabrice Bellard") as mock:
        version = "2.2.0"

        qemus = await Qemu.binary_list()

        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x86"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-kvm"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x42"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "hello"), "version": version} not in qemus

        qemus = await Qemu.binary_list(["x86"])

        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x86"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-kvm"), "version": version} not in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x42"), "version": version} not in qemus
        assert {"path": os.path.join(os.environ["PATH"], "hello"), "version": version} not in qemus

        qemus = await Qemu.binary_list(["x86", "x42"])

        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x86"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-kvm"), "version": version} not in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x42"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "hello"), "version": version} not in qemus


# @pytest.mark.asyncio
# async def test_img_binary_list(monkeypatch, tmpdir):
#
#     monkeypatch.setenv("PATH", str(tmpdir))
#     files_to_create = ["qemu-img", "qemu-io", "qemu-system-x86", "qemu-system-x42", "qemu-kvm", "hello"]
#
#     for file_to_create in files_to_create:
#         path = os.path.join(os.environ["PATH"], file_to_create)
#         with open(path, "w+") as f:
#             f.write("1")
#         os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
#
#     with asyncio_patch("gns3server.compute.qemu.subprocess_check_output", return_value="qemu-img version 2.2.0, Copyright (c) 2004-2008 Fabrice Bellard") as mock:
#         qemus = await Qemu.img_binary_list()
#
#         version = "2.2.0"
#
#         assert {"path": os.path.join(os.environ["PATH"], "qemu-img"), "version": version} in qemus
#         assert {"path": os.path.join(os.environ["PATH"], "qemu-io"), "version": version} not in qemus
#         assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x86"), "version": version} not in qemus
#         assert {"path": os.path.join(os.environ["PATH"], "qemu-kvm"), "version": version} not in qemus
#         assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x42"), "version": version} not in qemus
#         assert {"path": os.path.join(os.environ["PATH"], "hello"), "version": version} not in qemus


def test_get_legacy_vm_workdir():

    assert Qemu.get_legacy_vm_workdir(42, "bla") == os.path.join("qemu", "vm-42")


@pytest.mark.asyncio
async def test_get_kvm_archs_kvm_ok():

    with patch("os.path.exists", return_value=True):
        archs = await Qemu.get_kvm_archs()
        if platform.machine() == 'x86_64':
            assert archs == ['x86_64', 'i386']
        else:
            assert archs == [platform.machine()]

    with patch("os.path.exists", return_value=False):
        archs = await Qemu.get_kvm_archs()
        assert archs == []
