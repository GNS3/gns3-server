# -*- coding: utf-8 -*-
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

import io
import types
import asyncio
import unittest.mock


class _asyncio_patch:

    """
    A wrapper around python patch supporting asyncio.
    Like the original patch you can use it as context
    manager (with)

    The original patch source code is the main source of
    inspiration:
    https://hg.python.org/cpython/file/3.4/Lib/unittest/mock.py
    """

    def __init__(self, function, *args, **kwargs):

        self._function = function
        self._aync_magic_mock = AsyncioMagicMock(*args, **kwargs)

    def __enter__(self):
        """Used when enter in the with block"""
        self._patcher = unittest.mock.patch(self._function, new=self._aync_magic_mock)
        mock_class = self._patcher.start()
        return mock_class

    def __exit__(self, *exc_info):
        """Used when leaving the with block"""
        self._patcher.stop()


def asyncio_patch(function, *args, **kwargs):
    return _asyncio_patch(function, *args, **kwargs)

# monkey patch MagicMock,
# FIXME: would probably be better to use asynctest or pytest.asyncio to test our asyncio code
async def async_magic():
    pass

unittest.mock.MagicMock.__await__ = lambda x: async_magic().__await__()


class AsyncioMagicMock(unittest.mock.MagicMock):
    """
    Magic mock returning coroutine
    """

    try:
        __class__ = types.CoroutineType
    except AttributeError:  # Not supported with Python 3.4
        __class__ = types.GeneratorType

    def __init__(self, return_value=None, **kwargs):
        """
        :return_values: Array of return value at each call will return the next
        """
        if return_value is not None:
            future = asyncio.Future()
            future.set_result(return_value)
            kwargs["return_value"] = future
        super().__init__(**kwargs)

    def _get_child_mock(self, **kw):
        """Create the child mocks for attributes and return value.
        By default child mocks will be the same type as the parent.
        Subclasses of Mock may want to override this to customize the way
        child mocks are made.
        For non-callable mocks the callable variant will be used (rather than
        any custom subclass).

        Original code: https://github.com/python/cpython/blob/121f86338111e49c547a55eb7f26db919bfcbde9/Lib/unittest/mock.py
        """
        return AsyncioMagicMock(**kw)


class AsyncioBytesIO(io.BytesIO):
    """
    An async wrapper around io.BytesIO to fake an
    async network connection
    """

    async def read(self, length=-1):
        return super().read(length)

    async def write(self, data):
        return super().write(data)

    async def close(self):
        return super().close()
