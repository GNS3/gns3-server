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
Hub object that uses the Bridge interface to create a hub with ports.
"""

from __future__ import unicode_literals
from .bridge import Bridge
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class Hub(Bridge):
    """
    Dynamips hub (based on Bridge)

    :param hypervisor: Dynamips hypervisor object
    :param name: name for this hub
    """

    _instance_count = 1

    def __init__(self, hypervisor, name):

        # create an unique ID
        self._id = Hub._instance_count
        Hub._instance_count += 1

        # let's create a unique name if none has been chosen
        if not name:
            name_id = self._id
            while True:
                name = "Hub" + str(name_id)
                # check if the name has already been allocated to another switch
                if name not in self._allocated_names:
                    break
                name_id += 1

        self._allocated_names.append(name)
        self._mapping = {}
        Bridge.__init__(self, hypervisor, name)

        log.info("Ethernet hub {name} [id={id}] has been created".format(name=self._name,
                                                                         id=self._id))

    @classmethod
    def reset(cls):
        """
        Resets the instance count and the allocated names list.
        """

        cls._instance_count = 1
        cls._allocated_names.clear()

    @property
    def id(self):
        """
        Returns the unique ID for this Ethernet switch.

        :returns: id (integer)
        """

        return self._id

    @property
    def mapping(self):
        """
        Returns port mapping

        :returns: mapping list
        """

        return self._mapping

    def delete(self):
        """
        Deletes this hub.
        """

        Bridge.delete(self)
        log.info("Ethernet hub {name} [id={id}] has been deleted".format(name=self._name,
                                                                         id=self._id))

    def add_nio(self, nio, port):
        """
        Adds a NIO as new port on this hub.

        :param nio: NIO object to add
        :param port: port to allocate for the NIO
        """

        if port in self._mapping:
            raise DynamipsError("Port {} isn't free".format(port))

        Bridge.add_nio(self, nio)

        log.info("Ethernet hub {name} [id={id}]: NIO {nio} bound to port {port}".format(name=self._name,
                                                                                        id=self._id,
                                                                                        nio=nio,
                                                                                        port=port))
        self._mapping[port] = nio

    def remove_nio(self, port):
        """
        Removes the specified NIO as member of this hub.

        :param port: allocated port

        :returns: the NIO that was bound to the allocated port
        """

        if port not in self._mapping:
            raise DynamipsError("Port {} is not allocated".format(port))

        nio = self._mapping[port]
        Bridge.remove_nio(self, nio)

        log.info("Ethernet switch {name} [id={id}]: NIO {nio} removed from port {port}".format(name=self._name,
                                                                                               id=self._id,
                                                                                               nio=nio,
                                                                                               port=port))

        del self._mapping[port]
        return nio
