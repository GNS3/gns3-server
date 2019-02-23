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

import os
import aiohttp
from contextlib import contextmanager

from ..notification_queue import NotificationQueue


class Notification:
    """
    Manage notification for the controller
    """

    def __init__(self, controller):
        self._controller = controller
        self._project_listeners = {}
        self._controller_listeners = []

    @contextmanager
    def project_queue(self, project_id):
        """
        Get a queue of notifications

        Use it with Python with
        """
        queue = NotificationQueue()
        self._project_listeners.setdefault(project_id, set())
        self._project_listeners[project_id].add(queue)
        try:
            yield queue
        finally:
            self._project_listeners[project_id].remove(queue)

    @contextmanager
    def controller_queue(self):
        """
        Get a queue of notifications

        Use it with Python with
        """
        queue = NotificationQueue()
        self._controller_listeners.append(queue)
        try:
            yield queue
        finally:
            self._controller_listeners.remove(queue)

    def controller_emit(self, action, event):
        """
        Send a notification to clients connected to the controller stream

        :param action: Action name
        :param event: Event to send
        """

        # If use in tests for documentation we save a sample
        if os.environ.get("PYTEST_BUILD_DOCUMENTATION") == "1":
            os.makedirs("docs/api/notifications", exist_ok=True)
            try:
                import json
                data = json.dumps(event, indent=4, sort_keys=True)
                if "MagicMock" not in data:
                    with open(os.path.join("docs/api/notifications", action + ".json"), 'w+') as f:
                        f.write(data)
            except TypeError:  # If we receive a mock as an event it will raise TypeError when using json dump
                pass

        for controller_listener in self._controller_listeners:
            controller_listener.put_nowait((action, event, {}))

    def project_has_listeners(self, project_id):
        """
        :param project_id: Project object
        :returns: True if client listen this project
        """
        return project_id in self._project_listeners and len(self._project_listeners[project_id]) > 0

    async def dispatch(self, action, event, project_id, compute_id):
        """
        Notification received from compute node. Send it directly
        to clients or process it

        :param action: Action name
        :param event: Event to send
        :param compute_id: Compute id of the sender
        """
        if action == "node.updated":
            try:
                # Update controller node data and send the event node.updated
                project = self._controller.get_project(event["project_id"])
                node = project.get_node(event["node_id"])
                await node.parse_node_response(event)

                self.project_emit("node.updated", node.__json__())
            except (aiohttp.web.HTTPNotFound, aiohttp.web.HTTPForbidden):  # Project closing
                return
        elif action == "ping":
             event["compute_id"] = compute_id
             self.project_emit(action, event)
        else:
            self.project_emit(action, event, project_id)

    def project_emit(self, action, event, project_id=None):
        """
        Send a notification to clients scoped by projects

        :param action: Action name
        :param event: Event to send
        """

        # If use in tests for documentation we save a sample
        if os.environ.get("PYTEST_BUILD_DOCUMENTATION") == "1":
            os.makedirs("docs/api/notifications", exist_ok=True)
            try:
                import json
                data = json.dumps(event, indent=4, sort_keys=True)
                if "MagicMock" not in data:
                    with open(os.path.join("docs/api/notifications", action + ".json"), 'w+') as f:
                        f.write(data)
            except TypeError:  # If we receive a mock as an event it will raise TypeError when using json dump
                pass

        if "project_id" in event or project_id:
            self._send_event_to_project(event.get("project_id", project_id), action, event)
        else:
            self._send_event_to_all_projects(action, event)

    def _send_event_to_project(self, project_id, action, event):
        """
        Send an event to all the client listening for notifications for
        this project

        :param project: Project where we need to send the event
        :param action: Action name
        :param event: Event to send
        """
        try:
            project_listeners = self._project_listeners[project_id]
        except KeyError:
            return
        for listener in project_listeners:
            listener.put_nowait((action, event, {}))

    def _send_event_to_all_projects(self, action, event):
        """
        Send an event to all the client listening for notifications on all
        projects

        :param action: Action name
        :param event: Event to send
        """
        for project_listeners in self._project_listeners.values():
            for listener in project_listeners:
                listener.put_nowait((action, event, {}))
