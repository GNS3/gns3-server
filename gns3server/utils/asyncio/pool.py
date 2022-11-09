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

import sys
import asyncio


class Pool():
    """
    Limit concurrency for running parallel tasks
    """

    def __init__(self, concurrency=5):
        self._tasks = []
        self._concurrency = concurrency

    def append(self, task, *args, **kwargs):
        self._tasks.append((task, args, kwargs))

    async def join(self):
        """
        Wait for all task to finish
        """
        pending = set()
        exceptions = set()
        while len(self._tasks) > 0 or len(pending) > 0:
            while len(self._tasks) > 0 and len(pending) < self._concurrency:
                task, args, kwargs = self._tasks.pop(0)
                if sys.version_info >= (3, 7):
                    t = asyncio.create_task(task(*args, **kwargs))
                else:
                    t = asyncio.get_event_loop().create_task(task(*args, **kwargs))
                pending.add(t)
            (done, pending) = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task.exception():
                    exceptions.add(task.exception())
        if len(exceptions) > 0:
            raise exceptions.pop()


def main():
    async def task(id):
        print("Run", id)
        await asyncio.sleep(0.5)

    pool = Pool(concurrency=5)
    for i in range(1, 20):
        pool.append(task, i)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(pool.join())


if __name__ == '__main__':
    main()
