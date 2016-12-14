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


class Device:

    """
    Base device for switches and hubs

    :param name: name for this device
    :param node_id: Node instance identifier
    :param project: Project instance
    :param manager: Parent manager
    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, name, node_id, project, manager, hypervisor=None):

        self._name = name
        self._id = node_id
        self._project = project
        self._manager = manager
        self._hypervisor = hypervisor

    @property
    def hypervisor(self):
        """
        Returns the current hypervisor.

        :returns: hypervisor instance
        """

        return self._hypervisor

    @property
    def project(self):
        """
        Returns the device current project.

        :returns: Project instance.
        """

        return self._project

    @property
    def name(self):
        """
        Returns the name for this device.

        :returns: name
        """

        return self._name

    @name.setter
    def name(self, new_name):
        """
        Sets the name of this device.

        :param new_name: name
        """

        self._name = new_name

    @property
    def id(self):
        """
        Returns the ID for this device.

        :returns: device identifier (string)
        """

        return self._id

    @property
    def manager(self):
        """
        Returns the manager for this device.

        :returns: instance of manager
        """

        return self._manager

    def updated(self):
        """
        Send a updated event
        """
        self.project.emit("node.updated", self)

    def create(self):
        """
        Creates the device.
        """

        raise NotImplementedError

    @property
    def hw_virtualization(self):
        return False
