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


from ...base_vm import BaseVM


class Device(BaseVM):
    """
    Base device for switches and hubs

    :param name: name for this bridge
    :param vm_id: Node instance identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, name, node_id, project, manager, hypervisor=None):

        super().__init__(name, node_id, project, manager)
        self._hypervisor = hypervisor

    @property
    def hypervisor(self):
        """
        Returns the current hypervisor.

        :returns: hypervisor instance
        """

        return self._hypervisor

    def start(self):

        pass  # Dynamips switches and hubs are always on

    def stop(self):

        pass  # Dynamips switches and hubs are always on
