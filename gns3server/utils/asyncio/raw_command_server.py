# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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

import re
import copy
import asyncio
import asyncio.subprocess

import logging
log = logging.getLogger(__name__)

READ_SIZE = 4096


class AsyncioRawCommandServer:
    """
    Expose a process on the network his stdoud and stdin will be forward
    on network
    """

    def __init__(self, command, replaces=[]):
        """
        :param command: Command to run
        :param replaces: List of tuple to replace in the output ex: [(b":8080", b":6000")]
        """
        self._command = command
        self._replaces = replaces
        # We limit number of process
        self._lock = asyncio.Semaphore(value=4)

    @asyncio.coroutine
    def run(self, network_reader, network_writer):
        yield from self._lock.acquire()
        process = yield from asyncio.subprocess.create_subprocess_exec(*self._command,
                                                                       stdout=asyncio.subprocess.PIPE,
                                                                       stderr=asyncio.subprocess.STDOUT,
                                                                       stdin=asyncio.subprocess.PIPE)
        try:
            yield from self._process(network_reader, network_writer, process.stdout, process.stdin)
        except ConnectionResetError:
            network_writer.close()
        if process.returncode is None:
            process.kill()
        yield from process.wait()
        self._lock.release()

    @asyncio.coroutine
    def _process(self, network_reader, network_writer, process_reader, process_writer):
        replaces = []
        # Server host from the client point of view
        host = network_writer.transport.get_extra_info("sockname")[0]
        for replace in self._replaces:
            if b'{{HOST}}' in replace[1]:
                replaces.append((replace[0], replace[1].replace(b'{{HOST}}', host.encode()), ))
            else:
                replaces.append((replace[0], replace[1], ))

        network_read = asyncio.async(network_reader.read(READ_SIZE))
        reader_read = asyncio.async(process_reader.read(READ_SIZE))
        timeout = 30

        while True:
            done, pending = yield from asyncio.wait(
                [
                    network_read,
                    reader_read
                ],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED)
            if len(done) == 0:
                raise ConnectionResetError()
            for coro in done:
                data = coro.result()
                if coro == network_read:
                    if network_reader.at_eof():
                        raise ConnectionResetError()

                    network_read = asyncio.async(network_reader.read(READ_SIZE))

                    process_writer.write(data)
                    yield from process_writer.drain()
                elif coro == reader_read:
                    if process_reader.at_eof():
                        raise ConnectionResetError()

                    reader_read = asyncio.async(process_reader.read(READ_SIZE))

                    for replace in replaces:
                        data = data.replace(replace[0], replace[1])
                    timeout = 2  # We reduce the timeout when the process start to return stuff to avoid problem with server not closing the connection

                    network_writer.write(data)
                    yield from network_writer.drain()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()

    command = ["nc", "localhost", "80"]
    server = AsyncioRawCommandServer(command, replaces=[(b"work", b"{{HOST}}", )])
    coro = asyncio.start_server(server.run, '0.0.0.0', 4444, loop=loop)
    s = loop.run_until_complete(coro)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    # Close the server
    s.close()
    loop.run_until_complete(s.wait_closed())
    loop.close()
