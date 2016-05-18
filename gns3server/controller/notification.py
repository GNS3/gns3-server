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


class Notification:
    """
    Manage notification for the controller
    """

    def __init__(self, controller):
        self._controller = controller
        self._listeners = {}

    @contextmanager
    def queue(self, project):
        """
        Get a queue of notifications

        Use it with Python with
        """
        queue = NotificationQueue()
        self._listeners.setdefault(project.id, set())
        self._listeners[project.id].add(queue)
        yield queue
        self._listeners[project.id].remove(queue)

    def emit(self, action, event, **kwargs):
        """
        Send a notification to clients scoped by projects

        :param action: Action name
        :param event: Event to send
        :param kwargs: Add this meta to the notification
        """
        if "project_id" in kwargs:
            project_id = kwargs.pop("project_id")
            self._send_event_to_project(project_id, action, event, **kwargs)
        else:
            self._send_event_to_all(action, event, **kwargs)

    def _send_event_to_project(self, project_id, action, event, **kwargs):
        """
        Send an event to all the client listening for notifications for
        this project

        :param project: Project where we need to send the event
        :param action: Action name
        :param event: Event to send
        :param kwargs: Add this meta to the notification
        """
        try:
            project_listeners = self._listeners[project_id]
        except KeyError:
            return
        for listener in project_listeners:
            listener.put_nowait((action, event, kwargs))

    def _send_event_to_all(self, action, event, **kwargs):
        """
        Send an event to all the client listening for notifications on all
        projects

        :param action: Action name
        :param event: Event to send
        :param kwargs: Add this meta to the notification
        """
        for project_listeners in self._listeners.values():
            for listener in project_listeners:
                listener.put_nowait((action, event, kwargs))
