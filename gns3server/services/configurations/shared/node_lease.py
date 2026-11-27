"""Per-node lifecycle ownership: one start, stop, reload, wipe or console apply at a time."""

import asyncio
import inspect
from contextlib import asynccontextmanager
from functools import wraps

from .errors import ConfigurationError


@asynccontextmanager
async def node_lease(node):
    """Own the node's lifecycle. Re-entrant only for the task that holds it (a start that wipes, for example).

    A task started under the lease, such as a process-exit callback, waits like any other.
    """
    task = asyncio.current_task()
    if getattr(node, "_startup_lifecycle_owner", None) is task:
        yield
        return
    if not hasattr(node, "_startup_lifecycle_lock"):
        node._startup_lifecycle_lock = asyncio.Lock()
    async with node._startup_lifecycle_lock:
        node._startup_lifecycle_owner = task
        try:
            yield
        finally:
            node._startup_lifecycle_owner = None


def lifecycle_action(method):
    """Run a node method (start, stop, reload, close) while holding the node's lifecycle lease."""

    @wraps(method)
    async def locked(node, *args, **kwargs):
        async with node_lease(node):
            return await method(node, *args, **kwargs)

    return locked


def while_current_process(node, attribute, process, callback):
    """A process-termination callback that does nothing once ``node.<attribute>`` holds another process.

    A reload stops and starts under the lease; the old process's callback queues behind it and would
    otherwise stop the new one.
    """

    async def ended(returncode):
        async with node_lease(node):
            current = getattr(node, attribute, None)
            if current is not None and current is not process:
                return
            result = callback(returncode)
            if inspect.isawaitable(result):
                await result

    return ended


def runtime_replaced(node, instance, proxy):
    """The guest process or its console proxy is no longer the one a piece of work started with."""
    return (
        getattr(node, "_process", None) is not instance
        or getattr(node, "_configuration_console_proxy", None) is not proxy
    )


def runtime_stopped_or_replaced(node, instance, proxy):
    return getattr(node, "status", "started") != "started" or runtime_replaced(node, instance, proxy)


def require_stopped(node):
    """Refuse while the node, its process or a lifecycle operation is still live."""
    if node.status != "stopped":
        raise ConfigurationError("stop_required")
    for name in ("_process", "_iou_process"):
        process = getattr(node, name, None)
        if process is not None and process.returncode is None:
            raise ConfigurationError("stop_required")
    lock = getattr(node, "_execute_lock", None)
    if lock is not None and lock.locked():
        raise ConfigurationError("stop_required")
