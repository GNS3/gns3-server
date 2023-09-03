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
import threading


async def wait_run_in_executor(func, *args, **kwargs):
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
    await asyncio.wait([future])
    return future.result()


async def cancellable_wait_run_in_executor(func, *args, **kwargs):
    """
    Run blocking code in a different thread and wait
    for the result. Support cancellation.

    :param func: Run this function in a different thread
    :param args: Parameters of the function
    :param kwargs: Keyword parameters of the function
    :returns: Return the result of the function
    """
    stopped_event = threading.Event()
    kwargs["stopped_event"] = stopped_event
    try:
        await wait_run_in_executor(func, *args, **kwargs)
    except asyncio.CancelledError:
        stopped_event.set()


async def subprocess_check_output(*args, cwd=None, env=None, stderr=False):
    """
    Run a command and capture output

    :param *args: List of command arguments
    :param cwd: Current working directory
    :param env: Command environment
    :param stderr: Read on stderr
    :returns: Command output
    """

    if stderr:
        proc = await asyncio.create_subprocess_exec(*args, stderr=asyncio.subprocess.PIPE, cwd=cwd, env=env)
        _, output = await proc.communicate()
    else:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, cwd=cwd, env=env)
        output, _ = await proc.communicate()
    if output is None:
        return ""
    # If we received garbage we ignore invalid characters
    # it should happen only when user try to use another binary
    # and the code of VPCS, dynamips... Will detect it's not the correct binary
    return output.decode("utf-8", errors="ignore")


async def wait_for_process_termination(process, timeout=10):
    """
    Wait for a process terminate, and raise asyncio.TimeoutError in case of
    timeout.

    In theory this can be implemented by just:
    await asyncio.wait_for(self._iou_process.wait(), timeout=100)

    But it's broken before Python 3.4:
    http://bugs.python.org/issue23140

    :param process: An asyncio subprocess
    :param timeout: Timeout in seconds
    """

    if sys.version_info >= (3, 5):
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
        except ProcessLookupError:
            return
    else:
        while timeout > 0:
            if process.returncode is not None:
                return
            await asyncio.sleep(0.1)
            timeout -= 0.1
        raise asyncio.TimeoutError()


async def _check_process(process, termination_callback):
    if not hasattr(sys, "_called_from_test") or not sys._called_from_test:
        returncode = await process.wait()
        if asyncio.iscoroutinefunction(termination_callback):
            await termination_callback(returncode)
        else:
            termination_callback(returncode)


def monitor_process(process, termination_callback):
    """Call termination_callback when a process dies"""

    asyncio.ensure_future(_check_process(process, termination_callback))


async def wait_for_file_creation(path, timeout=60):

    while timeout > 0:
        if os.path.exists(path):
            return
        await asyncio.sleep(0.5)
        timeout -= 0.5
    raise asyncio.TimeoutError()


def locking(f):
    @functools.wraps(f)
    async def wrapper(oself, *args, **kwargs):
        lock_name = "__" + f.__name__ + "_lock"
        if not hasattr(oself, lock_name):
            setattr(oself, lock_name, asyncio.Lock())
        async with getattr(oself, lock_name):
            return await f(oself, *args, **kwargs)

    return wrapper
