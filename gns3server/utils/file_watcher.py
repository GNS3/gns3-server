#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
import os


class FileWatcher:
    """
    Watch for file change and call the callback when something happen
    """

    def __init__(self, path, callback, delay=1):
        if not isinstance(path, str):
            path = str(path)
        self._path = path
        self._callback = callback
        self._delay = delay
        self._closed = False

        try:
            self._mtime = os.stat(path).st_mtime_ns
        except OSError:
            self._mtime = None
        asyncio.get_event_loop().call_later(self._delay, self._check_config_file_change)

    def __del__(self):
        self._closed = True

    def close(self):
        self._closed = True

    def _check_config_file_change(self):
        if self._closed:
            return
        changed = False
        try:
            mtime = os.stat(self._path).st_mtime_ns
            if mtime != self._mtime:
                changed = True
                self._mtime = mtime
        except OSError:
            self._mtime = None
        if changed:
            self._callback(self._path)
        asyncio.get_event_loop().call_later(self._delay, self._check_config_file_change)

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, val):
        self._callback = val
