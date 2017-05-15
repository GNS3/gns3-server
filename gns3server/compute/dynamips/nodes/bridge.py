# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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

"""
Interface for Dynamips NIO bridge module ("nio_bridge").
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L538
"""

import asyncio
from .device import Device


class Bridge(Device):

    """
    Dynamips bridge.

    :param name: name for this bridge
    :param node_id: Node instance identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, name, node_id, project, manager, hypervisor=None):

        super().__init__(name, node_id, project, manager, hypervisor)
        self._nios = []

    @asyncio.coroutine
    def create(self):

        if self._hypervisor is None:
            module_workdir = self.project.module_working_directory(self.manager.module_name.lower())
            self._hypervisor = yield from self.manager.start_new_hypervisor(working_dir=module_workdir)

        yield from self._hypervisor.send('nio_bridge create "{}"'.format(self._name))
        self._hypervisor.devices.append(self)

    @asyncio.coroutine
    def set_name(self, new_name):
        """
        Renames this bridge.

        :param new_name: New name for this bridge
        """

        yield from self._hypervisor.send('nio_bridge rename "{name}" "{new_name}"'.format(name=self._name,
                                                                                          new_name=new_name))

        self._name = new_name

    @property
    def nios(self):
        """
        Returns all the NIOs member of this bridge.

        :returns: nio list
        """

        return self._nios

    @asyncio.coroutine
    def delete(self):
        """
        Deletes this bridge.
        """

        if self._hypervisor and self in self._hypervisor.devices:
            self._hypervisor.devices.remove(self)
        if self._hypervisor and not self._hypervisor.devices:
            yield from self._hypervisor.send('nio_bridge delete "{}"'.format(self._name))

    @asyncio.coroutine
    def add_nio(self, nio):
        """
        Adds a NIO as new port on this bridge.

        :param nio: NIO instance to add
        """

        yield from self._hypervisor.send('nio_bridge add_nio "{name}" {nio}'.format(name=self._name, nio=nio))
        self._nios.append(nio)

    @asyncio.coroutine
    def remove_nio(self, nio):
        """
        Removes the specified NIO as member of this bridge.

        :param nio: NIO instance to remove
        """
        if self._hypervisor:
            yield from self._hypervisor.send('nio_bridge remove_nio "{name}" {nio}'.format(name=self._name, nio=nio))
        self._nios.remove(nio)

    @property
    def hw_virtualization(self):
        return False
