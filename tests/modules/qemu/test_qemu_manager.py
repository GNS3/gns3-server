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
import asyncio
import sys

from gns3server.modules.qemu import Qemu
from tests.utils import asyncio_patch


def test_get_qemu_version(loop):

    with asyncio_patch("gns3server.modules.qemu.subprocess_check_output", return_value="QEMU emulator version 2.2.0, Copyright (c) 2003-2008 Fabrice Bellard") as mock:
        version = loop.run_until_complete(asyncio.async(Qemu.get_qemu_version("/tmp/qemu-test")))
        if sys.platform.startswith("win"):
            assert version == ""
        else:
            assert version == "2.2.0"


def test_binary_list(loop):

    files_to_create = ["qemu-system-x86", "qemu-system-x42", "qemu-kvm", "hello"]

    for file_to_create in files_to_create:
        path = os.path.join(os.environ["PATH"], file_to_create)
        with open(path, "w+") as f:
            f.write("1")
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

    with asyncio_patch("gns3server.modules.qemu.subprocess_check_output", return_value="QEMU emulator version 2.2.0, Copyright (c) 2003-2008 Fabrice Bellard") as mock:
        qemus = loop.run_until_complete(asyncio.async(Qemu.binary_list()))

        if sys.platform.startswith("win"):
            version = ""
        else:
            version = "2.2.0"

        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x86"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-kvm"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "qemu-system-x42"), "version": version} in qemus
        assert {"path": os.path.join(os.environ["PATH"], "hello"), "version": version} not in qemus


def test_get_legacy_vm_workdir():

    assert Qemu.get_legacy_vm_workdir(42, "bla") == os.path.join("qemu", "vm-42")
