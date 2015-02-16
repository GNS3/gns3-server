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


import asyncio
import pytest

from gns3server.utils.asyncio import wait_run_in_executor, subprocess_check_output


def test_wait_run_in_executor(loop):

    def change_var(param):
        return param

    exec = wait_run_in_executor(change_var, "test")
    result = loop.run_until_complete(asyncio.async(exec))
    assert result == "test"


def test_exception_wait_run_in_executor(loop):

    def raise_exception():
        raise Exception("test")

    exec = wait_run_in_executor(raise_exception)
    with pytest.raises(Exception):
        result = loop.run_until_complete(asyncio.async(exec))


def test_subprocess_check_output(loop, tmpdir, restore_original_path):

    path = str(tmpdir / "test")
    with open(path, "w+") as f:
        f.write("TEST")
    exec = subprocess_check_output("cat", path)
    result = loop.run_until_complete(asyncio.async(exec))
    assert result == "TEST"
