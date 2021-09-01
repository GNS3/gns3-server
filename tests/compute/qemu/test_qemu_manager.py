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
import sys
import pytest
import platform

from gns3server.compute.qemu import Qemu
from gns3server.compute.qemu.qemu_error import QemuError
from tests.utils import asyncio_patch

from unittest.mock import patch, MagicMock


@pytest.fixture
def fake_qemu_img_binary(tmpdir):

    bin_path = str(tmpdir / "qemu-img")
    with open(bin_path, "w+") as f:
        f.write("1")
    os.chmod(bin_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return bin_path


async def test_get_qemu_version():

    with asyncio_patch("gns3server.compute.qemu.subprocess_check_output", return_value="QEMU emulator version 2.2.0, Copyright (c) 2003-2008 Fabrice Bellard"):
        version = await Qemu.get_qemu_version("/tmp/qemu-test")
        if sys.platform.startswith("win"):
            assert version == ""
        else:
            assert version == "2.2.0"


async def test_binary_list(monkeypatch, tmpdir):

    monkeypatch.setenv("PATH", str(tmpdir))
    files_to_create = ["qemu-system-x86", "qemu-system-x42", "qemu-kvm", "hello", "qemu-system-x86_64-spice"]

    for file_to_create in files_to_create:
        path = os.path.join(os.environ["PATH"], file_to_create)
        with open(path, "w+") as f:
            f.write("1")
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    with asyncio_patch("gns3server.compute.qemu.subprocess_check_output", return_value="QEMU emulator version 2.2.0, Copyright (c) 2003-2008 Fabrice Bellard") as mock:
        if sys.platform.startswith("win"):
            version = ""
        else:
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


async def test_img_binary_list(monkeypatch, tmpdir):

    monkeypatch.setenv("PATH", str(tmpdir))
    files_to_create = ["qemu-img", "qemu-io", "qemu-system-x86", "qemu-system-x42", "qemu-kvm", "hello"]

    for file_to_create in files_to_create:
        path = os.path.join(os.environ["PATH"], file_to_create)
        with open(path, "w+") as f:
            f.write("1")
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    with asyncio_patch("gns3server.compute.qemu.subprocess_check_output", return_value="qemu-img version 2.2.0, Copyright (c) 2004-2008 Fabrice Bellard") as mock:
        qemus = await Qemu.img_binary_list()

        version = "2.2.0"

        assert {"path": os.path.join(os.environ["PATH"], "qemu-img"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-io"), "version": version} not in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x86"), "version": version} not in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-kvm"), "version": version} not in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x42"), "version": version} not in qemus
        assert {"path": os.path.join(os.environ["PATH"], "hello"), "version": version} not in qemus


def test_get_legacy_vm_workdir():

    assert Qemu.get_legacy_vm_workdir(42, "bla") == os.path.join("qemu", "vm-42")


async def test_create_image_abs_path(tmpdir, fake_qemu_img_binary):

    options = {
        "format": "qcow2",
        "preallocation": "metadata",
        "cluster_size": 64,
        "refcount_bits": 12,
        "lazy_refcounts": "off",
        "size": 100
    }
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        await Qemu.instance().create_disk(fake_qemu_img_binary, str(tmpdir / "hda.qcow2"), options)
        args, kwargs = process.call_args
        assert args == (
            fake_qemu_img_binary,
            "create",
            "-f",
            "qcow2",
            "-o",
            "cluster_size=64",
            "-o",
            "lazy_refcounts=off",
            "-o",
            "preallocation=metadata",
            "-o",
            "refcount_bits=12",
            str(tmpdir / "hda.qcow2"),
            "100M"
        )


async def test_create_image_relative_path(tmpdir, fake_qemu_img_binary):

    options = {
        "format": "raw",
        "size": 100
    }
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        with patch("gns3server.compute.qemu.Qemu.get_images_directory", return_value=str(tmpdir)):
            await Qemu.instance().create_disk(fake_qemu_img_binary, "hda.qcow2", options)
            args, kwargs = process.call_args
            assert args == (
                fake_qemu_img_binary,
                "create",
                "-f",
                "raw",
                str(tmpdir / "hda.qcow2"),
                "100M"
            )


async def test_create_image_exist(tmpdir, fake_qemu_img_binary):

    open(str(tmpdir / "hda.qcow2"), "w+").close()
    options = {
        "format": "raw",
        "size": 100
    }
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process:
        with patch("gns3server.compute.qemu.Qemu.get_images_directory", return_value=str(tmpdir)):
            with pytest.raises(QemuError):
                await Qemu.instance().create_disk(fake_qemu_img_binary, "hda.qcow2", options)
                assert not process.called


async def test_create_image_with_not_supported_characters_by_filesystem(tmpdir, fake_qemu_img_binary):

    open(str(tmpdir / "hda.qcow2"), "w+").close()

    options = {
        "format": "raw",
        "size": 100
    }

    # patching os.makedirs is necessary as it depends on already mocked os.path.exists
    with asyncio_patch("asyncio.create_subprocess_exec", return_value=MagicMock()) as process, \
            patch("gns3server.compute.qemu.Qemu.get_images_directory", return_value=str(tmpdir)), \
            patch("os.path.exists", side_effect=UnicodeEncodeError('error', u"", 1, 2, 'Emulated Unicode Err')),\
            patch("os.makedirs"):

        with pytest.raises(QemuError):
            await Qemu.instance().create_disk(fake_qemu_img_binary, "hda.qcow2", options)
            assert not process.called


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
