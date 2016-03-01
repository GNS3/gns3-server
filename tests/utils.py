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
from unittest.mock import patch, MagicMock


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
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        """Used when enter in the with block"""
        self._patcher = patch(self.function, return_value=self._fake_anwser())
        mock_class = self._patcher.start()
        return mock_class

    def __exit__(self, *exc_info):
        """Used when leaving the with block"""
        self._patcher.stop()

    def _fake_anwser(self):
        future = asyncio.Future()
        if "return_value" in self.kwargs:
            future.set_result(self.kwargs["return_value"])
        elif "side_effect" in self.kwargs:
            if isinstance(self.kwargs["side_effect"], Exception):
                future.set_exception(self.kwargs["side_effect"])
            else:
                raise NotImplementedError
        else:
            future.set_result(True)
        return future


def asyncio_patch(function, *args, **kwargs):
    return _asyncio_patch(function, *args, **kwargs)


class AsyncioMagicMock(MagicMock):
    """
    Magic mock returning coroutine
    """
    def __init__(self, return_value=None, **kwargs):
        if return_value:
            future = asyncio.Future()
            future.set_result(return_value)
            kwargs["return_value"] = future
        super().__init__(**kwargs)
