import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from gns3server.services.configurations.shared.node_lease import (
    lifecycle_action,
    node_lease,
    runtime_replaced,
    runtime_stopped_or_replaced,
    while_current_process,
)


@pytest.mark.asyncio
async def test_the_owning_task_may_enter_its_lease_again():
    node = SimpleNamespace()
    async with asyncio.timeout(1):
        async with node_lease(node):
            async with node_lease(node):
                pass


@pytest.mark.asyncio
async def test_a_task_started_under_the_lease_waits_for_its_release():
    """A process-exit callback is such a task: it must not stop a node that is still starting."""
    order = []

    class Node:
        @lifecycle_action
        async def start(self):
            callback = asyncio.ensure_future(self.stop())
            for _ in range(3):
                await asyncio.sleep(0)
            order.append("started")
            return callback

        @lifecycle_action
        async def stop(self):
            order.append("stopped")

    callback = await Node().start()
    await asyncio.wait_for(callback, 1)
    assert order == ["started", "stopped"]


@pytest.mark.asyncio
@pytest.mark.parametrize("replaced", [False, True])
async def test_a_process_exit_callback_ignores_a_process_that_was_replaced(replaced):
    """Reload stops and starts under the lease: the old process's callback must not stop the new one."""
    node = SimpleNamespace(_process="old")
    callback = AsyncMock()
    ended = while_current_process(node, "_process", "old", callback)
    async with node_lease(node):
        waiting = asyncio.create_task(ended(1))
        await asyncio.sleep(0)
        callback.assert_not_awaited()
        if replaced:
            node._process = "new"
    await waiting
    assert callback.await_count == (0 if replaced else 1)


@pytest.mark.asyncio
async def test_a_process_exit_callback_still_runs_after_the_handle_was_cleared():
    node = SimpleNamespace(_iou_process=None)
    callback = MagicMock()
    await while_current_process(node, "_iou_process", "old", callback)(0)
    callback.assert_called_once_with(0)


@pytest.mark.parametrize(
    "changes,replaced,stopped",
    [
        ({}, False, False),
        ({"_process": object()}, True, True),
        ({"_configuration_console_proxy": object()}, True, True),
        ({"_configuration_console_proxy": None}, True, True),
        ({"status": "stopped"}, False, True),
    ],
    ids=["same", "new_process", "new_proxy", "proxy_gone", "stopped"],
)
def test_a_node_is_replaced_when_its_process_or_proxy_changes_and_stopped_when_it_is_not_started(
    changes, replaced, stopped
):
    process, proxy = object(), object()
    node = SimpleNamespace(
        **{"status": "started", "_process": process, "_configuration_console_proxy": proxy, **changes}
    )
    assert runtime_replaced(node, process, proxy) is replaced
    assert runtime_stopped_or_replaced(node, process, proxy) is stopped
