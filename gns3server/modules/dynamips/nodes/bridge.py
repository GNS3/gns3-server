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


class Bridge(object):
    """
    Dynamips bridge.

    :param hypervisor: Dynamips hypervisor instance
    :param name: name for this bridge
    """

    def __init__(self, hypervisor, name):

        self._hypervisor = hypervisor
        self._name = '"' + name + '"'  # put name into quotes to protect spaces
        self._hypervisor.send("nio_bridge create {}".format(self._name))
        self._hypervisor.devices.append(self)
        self._nios = []

    @property
    def name(self):
        """
        Returns the current name of this bridge.

        :returns: bridge name
        """

        return self._name[1:-1]  # remove quotes

    @name.setter
    def name(self, new_name):
        """
        Renames this bridge.

        :param new_name: New name for this bridge
        """

        new_name = '"' + new_name + '"'  # put the new name into quotes to protect spaces
        self._hypervisor.send("nio_bridge rename {name} {new_name}".format(name=self._name,
                                                                           new_name=new_name))

        self._name = new_name

    @property
    def hypervisor(self):
        """
        Returns the current hypervisor.

        :returns: hypervisor instance
        """

        return self._hypervisor

    def list(self):
        """
        Returns all bridge instances.

        :returns: list of all bridges
        """

        return self._hypervisor.send("nio_bridge list")

    @property
    def nios(self):
        """
        Returns all the NIOs member of this bridge.

        :returns: nio list
        """

        return self._nios

    def delete(self):
        """
        Deletes this bridge.
        """

        self._hypervisor.send("nio_bridge delete {}".format(self._name))
        self._hypervisor.devices.remove(self)

    def add_nio(self, nio):
        """
        Adds a NIO as new port on this bridge.

        :param nio: NIO instance to add
        """

        self._hypervisor.send("nio_bridge add_nio {name} {nio}".format(name=self._name,
                                                                       nio=nio))
        self._nios.append(nio)

    def remove_nio(self, nio):
        """
        Removes the specified NIO as member of this bridge.

        :param nio: NIO instance to remove
        """

        self._hypervisor.send("nio_bridge remove_nio {name} {nio}".format(name=self._name,
                                                                          nio=nio))
        self._nios.remove(nio)
