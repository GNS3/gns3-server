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


import functools
import asyncio
import sys
import os


@asyncio.coroutine
def wait_run_in_executor(func, *args, **kwargs):
    """
    Run blocking code in a different thread and wait
    for the result.

    :param func: Run this function in a different thread
    :param args: Parameters of the function
    :param kwargs: Keyword parameters of the function
    :returns: Return the result of the function
    """

    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    yield from asyncio.wait([future])
    return future.result()


@asyncio.coroutine
def subprocess_check_output(*args, cwd=None, env=None):
    """
    Run a command and capture output

    :param *args: List of command arguments
    :param cwd: Current working directory
    :param env: Command environment
    :returns: Command output
    """

    proc = yield from asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, cwd=cwd, env=env)
    output = yield from proc.stdout.read()
    if output is None:
        return ""
    # If we received garbage we ignore invalid characters
    # it should happens only when user try to use another binary
    # and the code of VPCS, dynamips... Will detect it's not the correct binary
    return output.decode("utf-8", errors="ignore")


@asyncio.coroutine
def wait_for_process_termination(process, timeout=10):
    """
    Wait for a process terminate, and raise asyncio.TimeoutError in case of
    timeout.

    In theory this can be implemented by just:
    yield from asyncio.wait_for(self._iou_process.wait(), timeout=100)

    But it's broken before Python 3.4:
    http://bugs.python.org/issue23140

    :param process: An asyncio subprocess
    :param timeout: Timeout in seconds
    """

    if sys.version_info >= (3, 5):
        try:
            yield from asyncio.wait_for(process.wait(), timeout=timeout)
        except ProcessLookupError:
            return
    else:
        while timeout > 0:
            if process.returncode is not None:
                return
            yield from asyncio.sleep(0.1)
            timeout -= 0.1
        raise asyncio.TimeoutError()


@asyncio.coroutine
def _check_process(process, termination_callback):
    if not hasattr(sys, "_called_from_test") or not sys._called_from_test:
        returncode = yield from process.wait()
        if asyncio.iscoroutinefunction(termination_callback):
            yield from termination_callback(returncode)
        else:
            termination_callback(returncode)


def monitor_process(process, termination_callback):
    """Call termination_callback when a process dies"""

    asyncio.async(_check_process(process, termination_callback))


@asyncio.coroutine
def wait_for_file_creation(path, timeout=10):

    while timeout > 0:
        if os.path.exists(path):
            return
        yield from asyncio.sleep(0.5)
        timeout -= 0.5
    raise asyncio.TimeoutError()


@asyncio.coroutine
def wait_for_named_pipe_creation(pipe_path, timeout=60):

    import win32pipe
    import pywintypes

    while timeout > 0:
        try:
            win32pipe.WaitNamedPipe(pipe_path, 1)
        except pywintypes.error:
            yield from asyncio.sleep(0.5)
            timeout -= 0.5
        else:
            return
    raise asyncio.TimeoutError()


def locked_coroutine(f):
    """
    Method decorator that replace asyncio.coroutine that warranty
    that this specific method of this class instance will not we
    executed twice at the same time
    """
    @asyncio.coroutine
    def new_function(*args, **kwargs):

        # In the instance of the class we will store
        # a lock has an attribute.
        lock_var_name = "__" + f.__name__ + "_lock"
        if not hasattr(args[0], lock_var_name):
            setattr(args[0], lock_var_name, asyncio.Lock())

        with (yield from getattr(args[0], lock_var_name)):
            return (yield from f(*args, **kwargs))

    return new_function
