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
import psutil
import json
import psutil


class NotificationQueue(asyncio.Queue):
    """
    Queue returned by the notification manager.
    """

    def __init__(self):
        super().__init__()
        self._first = True

    @asyncio.coroutine
    def get(self, timeout):
        """
        When timeout is expire we send a ping notification with server informations
        """

        # At first get we return a ping so the client receive immediately data
        if self._first:
            self._first = False
            return ("ping", self._getPing(), {})

        try:
            (action, msg, kwargs) = yield from asyncio.wait_for(super().get(), timeout)
        except asyncio.futures.TimeoutError:
            return ("ping", self._getPing(), {})
        return (action, msg, kwargs)

    def _getPing(self):
        """
        Return the content of the ping notification
        """
        msg = {}
        # Non blocking call in order to get cpu usage. First call will return 0
        msg["cpu_usage_percent"] = psutil.cpu_percent(interval=None)
        msg["memory_usage_percent"] = psutil.virtual_memory().percent
        return msg

    @asyncio.coroutine
    def get_json(self, timeout):
        """
        Get a message as a JSON
        """
        (action, msg, kwargs) = yield from self.get(timeout)
        if hasattr(msg, "__json__"):
            msg = {"action": action, "event": msg.__json__()}
        else:
            msg = {"action": action, "event": msg}
        msg.update(kwargs)
        return json.dumps(msg, sort_keys=True)
