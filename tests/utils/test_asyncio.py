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
import sys
from unittest.mock import MagicMock

from gns3server.utils.asyncio import wait_run_in_executor, subprocess_check_output, wait_for_process_termination, locking
from tests.utils import AsyncioMagicMock


async def test_wait_run_in_executor():

    def change_var(param):
        return param

    result = await wait_run_in_executor(change_var, "test")
    assert result == "test"


async def test_exception_wait_run_in_executor():

    def raise_exception():
        raise Exception("test")

    with pytest.raises(Exception):
        await wait_run_in_executor(raise_exception)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Not supported on Windows")
async def test_subprocess_check_output(loop, tmpdir):

    path = str(tmpdir / "test")
    result = await subprocess_check_output("echo", "-n", path)
    assert result == path


async def test_lock_decorator():
    """
    The test check if the the second call to method_to_lock wait for the
    first call to finish
    """

    class TestLock:

        def __init__(self):
            self._test_val = 0

        @locking
        async def method_to_lock(self):
            result = self._test_val
            await asyncio.sleep(0.1)
            self._test_val += 1
            return result

    i = TestLock()
    res = set(await asyncio.gather(i.method_to_lock(), i.method_to_lock()))
    assert res == set((0, 1,))  # We use a set to test this to avoid order issue
