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


#TODO: make this more generic (not json but *args?)
class BaseModule(object):
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            asyncio.async(cls._instance.run())
        return cls._instance

    def __init__(self):
        self._queue = asyncio.Queue()

    @classmethod
    def destroy(cls):
        future = asyncio.Future()
        cls._instance._queue.put_nowait((future, None, ))
        yield from asyncio.wait([future])
        cls._instance = None

    @asyncio.coroutine
    def put(self, json):

        future = asyncio.Future()
        self._queue.put_nowait((future, json, ))
        yield from asyncio.wait([future])
        return future.result()

    @asyncio.coroutine
    def run(self):

        while True:
            future, json = yield from self._queue.get()
            if json is None:
                future.set_result(True)
                break
            try:
                result = yield from self.process(json)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)

    @asyncio.coroutine
    def process(self, json):
        raise NotImplementedError
