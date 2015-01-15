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
from .vm_error import VMError
from .attic import find_unused_port

import logging
log = logging.getLogger(__name__)


class BaseVM:
    _allocated_console_ports = []

    def __init__(self, name, identifier, port_manager):
        self._loop = asyncio.get_event_loop()
        self._allocate_console()
        self._queue = asyncio.Queue()
        self._name = name
        self._id = identifier
        self._created = asyncio.Future()
        self._worker = asyncio.async(self._run())
        self._port_manager = port_manager
        log.info("{type} device {name} [id={id}] has been created".format(
            type=self.__class__.__name__,
            name=self._name,
            id=self._id))

    def _allocate_console(self):
        if not self._console:
            # allocate a console port
            try:
                self._console = find_unused_port(self._console_start_port_range,
                                                 self._console_end_port_range,
                                                 self._console_host,
                                                 ignore_ports=self._allocated_console_ports)
            except Exception as e:
                raise VMError(e)

        if self._console in self._allocated_console_ports:
            raise VMError("Console port {} is already used by another device".format(self._console))
        self._allocated_console_ports.append(self._console)


    @property
    def console(self):
        """
        Returns the TCP console port.

        :returns: console port (integer)
        """

        return self._console

    @console.setter
    def console(self, console):
        """
        Sets the TCP console port.

        :param console: console port (integer)
        """

        if console in self._allocated_console_ports:
            raise VMError("Console port {} is already used by another VM device".format(console))

        self._allocated_console_ports.remove(self._console)
        self._console = console
        self._allocated_console_ports.append(self._console)
        log.info("{type} {name} [id={id}]: console port set to {port}".format(
                                                                            type=self.__class__.__name__,
                                                                            name=self._name,
                                                                            id=self._id,
                                                                            port=console))
    @property
    def id(self):
        """
        Returns the unique ID for this VM.

        :returns: id (integer)
        """

        return self._id

    @property
    def name(self):
        """
        Returns the name for this VM.

        :returns: name (string)
        """

        return self._name

    @asyncio.coroutine
    def _execute(self, subcommand, args):
        """Called when we receive an event"""
        raise NotImplementedError

    @asyncio.coroutine
    def _create(self):
        """Called when the run loop start"""
        raise NotImplementedError

    @asyncio.coroutine
    def _run(self, timeout=60):

        try:
            yield from self._create()
            self._created.set_result(True)
        except VMError as e:
            self._created.set_exception(e)
            return

        while True:
            future, subcommand, args = yield from self._queue.get()
            try:
                try:
                    yield from asyncio.wait_for(self._execute(subcommand, args), timeout=timeout)
                except asyncio.TimeoutError:
                    raise VMError("{} has timed out after {} seconds!".format(subcommand, timeout))
                future.set_result(True)
            except Exception as e:
                future.set_exception(e)

    def wait_for_creation(self):
        return self._created

    @asyncio.coroutine
    def start(self):
        """
        Starts the VM process.
        """
        raise NotImplementedError

    def put(self, *args):
        """
        Add to the processing queue of the VM

        :returns: future
        """

        future = asyncio.Future()
        try:
            args.insert(0, future)
            self._queue.put_nowait(args)
        except asyncio.qeues.QueueFull:
            raise VMError("Queue is full")
        return future
