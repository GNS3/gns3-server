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


from contextlib import contextmanager
from ..notification_queue import NotificationQueue


class NotificationManager:
    """
    Manage the notification queue where the controller
    will connect to get notifications from computes
    """

    def __init__(self):
        self._listeners = set()

    @contextmanager
    def queue(self):
        """
        Get a queue of notifications

        Use it with Python with
        """
        queue = NotificationQueue()
        self._listeners.add(queue)
        yield queue
        self._listeners.remove(queue)

    def emit(self, action, event, **kwargs):
        """
        Send an event to all the client listening for notifications

        :param action: Action name
        :param event: Event to send
        :param kwargs: Add this meta to the notification (project_id for example)
        """
        for listener in self._listeners:
            listener.put_nowait((action, event, kwargs))

    @staticmethod
    def reset():
        NotificationManager._instance = None

    @staticmethod
    def instance():
        """
        Singleton to return only on instance of NotificationManager.

        :returns: instance of NotificationManager
        """

        if not hasattr(NotificationManager, '_instance') or NotificationManager._instance is None:
            NotificationManager._instance = NotificationManager()
        return NotificationManager._instance
