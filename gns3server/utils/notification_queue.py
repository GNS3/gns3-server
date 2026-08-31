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

import asyncio
import json
import time
import psutil

from gns3server.utils.cpu_percent import CpuPercent
from gns3server.utils.path import get_default_project_directory

import logging

log = logging.getLogger(__name__)


class NotificationQueue(asyncio.Queue):
    """
    Queue returned by the notification manager.
    """

    def __init__(self):
        super().__init__()
        self._first = True
        self._last_ping = None

    async def get(self, timeout):
        """
        Return a notification, or a ping notification with server information
        at least every `timeout` seconds. The ping used to be generated only
        when the queue was idle for the full timeout, which starved it under
        sustained event load (e.g. high marker.match rates): clients stopped
        receiving compute statistics until the event flow paused.
        """

        # At first get we return a ping so the client immediately receives data
        if self._first:
            self._first = False
            return self._ping()

        while True:
            now = time.monotonic()
            if self._last_ping is None or now - self._last_ping >= timeout:
                return self._ping()
            try:
                (action, msg, kwargs) = await asyncio.wait_for(super().get(), timeout - (now - self._last_ping))
                return (action, msg, kwargs)
            except asyncio.TimeoutError:
                continue  # the ping deadline has been reached

    def _ping(self):
        """
        Build a ping notification and stamp the ping deadline.
        """

        self._last_ping = time.monotonic()
        return ("ping", self._getPing(), {})

    def _getPing(self):
        """
        Return the content of the ping notification
        """
        msg = {"cpu_usage_percent": 0, "memory_usage_percent": 0, "disk_usage_percent": 0}
        # Non blocking call in order to get cpu usage. First call will return 0
        try:
            msg["cpu_usage_percent"] = CpuPercent.get(interval=None)
            msg["memory_usage_percent"] = psutil.virtual_memory().percent
            msg["disk_usage_percent"] = psutil.disk_usage(get_default_project_directory()).percent
        except OSError as e:
            log.warning(f"Could not get CPU and memory usage from psutil: {e}")
        return msg

    async def get_json(self, timeout):
        """
        Get a message as a JSON
        """
        (action, msg, kwargs) = await self.get(timeout)
        if hasattr(msg, "asdict"):
            msg = {"action": action, "event": msg.asdict()}
        else:
            msg = {"action": action, "event": msg}
        msg.update(kwargs)
        return json.dumps(msg, sort_keys=True)
