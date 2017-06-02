#!/usr/bin/env python
#
# Copyright (C) 2017 GNS3 Technologies Inc.
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
import inspect

from .telnet_server import AsyncioTelnetServer


class EmbedShell:
    """
    An asynchronous shell use for stuff like EthernetSwitch console
    or built in VPCS
    """

    def __init__(self, reader=None, writer=None, loop=None, welcome_message=None):
        self._loop = loop
        self._reader = reader
        self._writer = writer
        self._prompt = '> '
        self._welcome_message = welcome_message

    @property
    def writer(self):
        return self._writer

    @writer.setter
    def writer(self, val):
        self._writer = val

    @property
    def reader(self):
        return self._reader

    @reader.setter
    def reader(self, val):
        self._reader = val

    @property
    def prompt(self):
        return self._prompt

    @prompt.setter
    def prompt(self, val):
        self._prompt = val

    @asyncio.coroutine
    def help(self, *args):
        """
        Show help
        """
        res = ''
        if len(args) == 0:
            res = 'Help:\n'
        for name, value in inspect.getmembers(self):
            if not inspect.isgeneratorfunction(value):
                continue
            if name.startswith('_') or (len(args) and name != args[0]) or name == 'run':
                continue
            doc = inspect.getdoc(value)
            res += name
            if len(args) and doc:
                res += ': ' + doc
            elif doc:
                res += ': ' + doc.split('\n')[0]
            res += '\n'
        if len(args) == 0:
            res += '\nhelp command for details about a command\n'
        return res

    @asyncio.coroutine
    def _parse_command(self, text):
        cmd = text.split(' ')
        found = False
        if cmd[0] == '?':
            cmd[0] = 'help'
        for (name, meth) in inspect.getmembers(self):
            if name == cmd[0]:
                cmd.pop(0)
                res = yield from meth(*cmd)
                found = True
                break
        if not found:
            res = ('Command not found {}'.format(cmd[0]) + (yield from self.help()))
        return res

    @asyncio.coroutine
    def run(self):
        if self._welcome_message:
            self._writer.feed_data(self._welcome_message.encode())
        while True:
            self._writer.feed_data(self._prompt.encode())
            result = yield from self._reader.readline()
            result = result.decode().strip('\n')
            res = yield from self._parse_command(result)
            self._writer.feed_data(res.encode())


def create_telnet_shell(shell, loop=None):
    """
    Run a shell application with a telnet frontend

    :param application: An EmbedShell instance
    :param loop: The event loop
    :returns: Telnet server
    """
    class Stream(asyncio.StreamReader):

        def write(self, data):
            self.feed_data(data)

        @asyncio.coroutine
        def drain(self):
            pass
    shell.reader = Stream()
    shell.writer = Stream()
    if loop is None:
        loop = asyncio.get_event_loop()
    loop.create_task(shell.run())
    return AsyncioTelnetServer(reader=shell.writer, writer=shell.reader, binary=False, echo=False)


def create_stdin_shell(shell, loop=None):
    """
    Run a shell application with a stdin frontend

    :param application: An EmbedShell instance
    :param loop: The event loop
    :returns: Telnet server
    """
    @asyncio.coroutine
    def feed_stdin(loop, reader):
        while True:
            line = yield from loop.run_in_executor(None, sys.stdin.readline)
            reader.feed_data(line.encode())

    @asyncio.coroutine
    def read_stdout(writer):
        while True:
            c = yield from writer.read(1)
            print(c.decode(), end='')
            sys.stdout.flush()

    reader = asyncio.StreamReader()
    writer = asyncio.StreamReader()
    shell.reader = reader
    shell.writer = writer
    if loop is None:
        loop = asyncio.get_event_loop()

    reader_task = loop.create_task(feed_stdin(loop, reader))
    writer_task = loop.create_task(read_stdout(writer))
    shell_task = loop.create_task(shell.run())
    return asyncio.gather(shell_task, writer_task, reader_task)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    class Demo(EmbedShell):

        @asyncio.coroutine
        def hello(self, *args):
            """
            Hello world

            This command accept arguments: hello tutu will display tutu
            """
            if len(args):
                return ' '.join(args)
            else:
                return 'world\n'

    # Demo using telnet
    # server = create_telnet_shell(Demo())
    # coro = asyncio.start_server(server.run, '127.0.0.1', 4444, loop=loop)
    # s = loop.run_until_complete(coro)
    # try:
    #     loop.run_forever()
    # except KeyboardInterrupt:
    #     pass

    # Demo using stdin
    loop.run_until_complete(create_stdin_shell(Demo()))
    loop.close()
