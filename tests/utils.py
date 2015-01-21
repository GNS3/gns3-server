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
from unittest.mock import patch
from gns3server.modules.project_manager import ProjectManager
from gns3server.modules.port_manager import PortManager


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
        future.set_result(self.kwargs["return_value"])
        return future


def asyncio_patch(function, *args, **kwargs):
    return _asyncio_patch(function, *args, **kwargs)


@pytest.fixture(scope="session")
def port_manager():
    return PortManager("127.0.0.1", False)


@pytest.fixture(scope="function")
def free_console_port(request, port_manager):
    # In case of already use ports we will raise an exception
    port = port_manager.get_free_console_port()
    # We release the port immediately in order to allow
    # the test do whatever the test want
    port_manager.release_console_port(port)
    return port
