#
# Copyright (C) 2026 GNS3 Technologies Inc.
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

import time
import asyncio

import pytest

from gns3server.utils.notification_queue import NotificationQueue


async def _feed(queue, until, interval=0.02):
    """
    Continuously put dummy events on the queue to simulate sustained load
    (e.g. high marker.match rates).
    """

    seq = 0
    while time.monotonic() < until:
        queue.put_nowait(("dummy", {"seq": seq}, {}))
        seq += 1
        await asyncio.sleep(interval)


@pytest.mark.asyncio
async def test_first_get_returns_ping():

    queue = NotificationQueue()
    action, event, _ = await asyncio.wait_for(queue.get(1), 1)
    assert action == "ping"
    assert "cpu_usage_percent" in event


@pytest.mark.asyncio
async def test_idle_queue_pings_after_timeout():

    queue = NotificationQueue()
    await queue.get(0.3)  # consume the first immediate ping

    start = time.monotonic()
    action, _, _ = await asyncio.wait_for(queue.get(0.3), 1)
    assert action == "ping"
    assert time.monotonic() - start >= 0.25  # had to wait for the idle timeout


@pytest.mark.asyncio
async def test_ping_not_starved_under_sustained_load():
    """
    Regression test: a continuously-fed queue must still emit a ping at least
    every `timeout` seconds. The old idle-timeout-only ping never fired under
    sustained event load, so clients stopped receiving compute statistics
    (no more compute.updated events) until the event flow paused.
    """

    queue = NotificationQueue()
    action, _, _ = await queue.get(0.5)  # consume the first immediate ping
    assert action == "ping"

    until = time.monotonic() + 2.0
    producer = asyncio.create_task(_feed(queue, until))
    try:
        pings = 0
        events = 0
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            action, _, _ = await asyncio.wait_for(queue.get(0.5), 1)
            if action == "ping":
                pings += 1
            else:
                events += 1
        # real events still flow...
        assert events > 0
        # ...and pings interleave roughly every 0.5s instead of starving
        assert pings >= 2
    finally:
        producer.cancel()
