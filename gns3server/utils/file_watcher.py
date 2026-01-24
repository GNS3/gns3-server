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

import zlib
import asyncio
import os


class FileWatcher:
    """
    Watch for file change and call the callback when something happens

    :param paths: A path or a list of file to watch
    :param delay: Delay between file check (seconds)
    :param strategy: File change strategy (mtime: modification time, hash: hash compute)
    """

    def __init__(self, paths, callback, delay=1, strategy='mtime'):
        self._paths = []
        if not isinstance(paths, list):
            paths = [paths]
        for path in paths:
            if not isinstance(path, str):
                path = str(path)
            self._paths.append(path)

        self._callback = callback
        self._delay = delay
        self._closed = False
        self._strategy = strategy

        if self._strategy == 'mtime':
            # Store modification time
            self._mtime = {}
            for path in self._paths:
                try:
                    self._mtime[path] = os.stat(path).st_mtime_ns
                except OSError:
                    self._mtime[path] = None
        else:
            # Store hash
            self._hashed = {}
            for path in self._paths:
                try:
                    # Alder32 is a fast but insecure hash algorithm
                    self._hashed[path] = zlib.adler32(open(path, 'rb').read())
                except OSError:
                    self._hashed[path] = None

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.call_later(self._delay, self._check_config_file_change)

    def __del__(self):
        self._closed = True

    def close(self):
        self._closed = True

    def _check_config_file_change(self):
        if self._closed:
            return
        changed = False

        for path in self._paths:
            if self._strategy == 'mtime':
                try:
                    mtime = os.stat(path).st_mtime_ns
                    if mtime != self._mtime[path]:
                        changed = True
                        self._mtime[path] = mtime
                except OSError:
                    self._mtime[path] = None
            else:
                try:
                    hashc = zlib.adler32(open(path, 'rb').read())
                    if hashc != self._hashed[path]:
                        changed = True
                        self._hashed[path] = hashc
                except OSError:
                    self._hashed[path] = None
            if changed:
                self._callback(path)
        asyncio.get_event_loop().call_later(self._delay, self._check_config_file_change)

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, val):
        self._callback = val
