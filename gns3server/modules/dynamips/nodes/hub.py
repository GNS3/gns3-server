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

import os
from .bridge import Bridge
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class Hub(Bridge):
    """
    Dynamips hub (based on Bridge)

    :param hypervisor: Dynamips hypervisor instance
    :param name: name for this hub
    """

    _instances = []

    def __init__(self, hypervisor, name):

        # find an instance identifier (0 < id <= 4096)
        self._id = 0
        for identifier in range(1, 4097):
            if identifier not in self._instances:
                self._id = identifier
                self._instances.append(self._id)
                break

        if self._id == 0:
            raise DynamipsError("Maximum number of instances reached")

        self._mapping = {}
        Bridge.__init__(self, hypervisor, name)

        log.info("Ethernet hub {name} [id={id}] has been created".format(name=self._name,
                                                                         id=self._id))

    @classmethod
    def reset(cls):
        """
        Resets the instance count and the allocated instances list.
        """

        cls._instances.clear()

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
        self._instances.remove(self._id)

    def add_nio(self, nio, port):
        """
        Adds a NIO as new port on this hub.

        :param nio: NIO instance to add
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

    def start_capture(self, port, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param port: allocated port
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        if port not in self._mapping:
            raise DynamipsError("Port {} is not allocated".format(port))

        nio = self._mapping[port]

        data_link_type = data_link_type.lower()
        if data_link_type.startswith("dlt_"):
            data_link_type = data_link_type[4:]

        if nio.input_filter[0] is not None and nio.output_filter[0] is not None:
            raise DynamipsError("Port {} has already a filter applied".format(port))

        try:
            os.makedirs(os.path.dirname(output_file))
        except FileExistsError:
            pass
        except OSError as e:
            raise DynamipsError("Could not create captures directory {}".format(e))

        nio.bind_filter("both", "capture")
        nio.setup_filter("both", "{} {}".format(data_link_type, output_file))

        log.info("Ethernet hub {name} [id={id}]: starting packet capture on {port}".format(name=self._name,
                                                                                           id=self._id,
                                                                                           port=port))

    def stop_capture(self, port):
        """
        Stops a packet capture.

        :param port: allocated port
        """

        if port not in self._mapping:
            raise DynamipsError("Port {} is not allocated".format(port))

        nio = self._mapping[port]
        nio.unbind_filter("both")
        log.info("Ethernet hub {name} [id={id}]: stopping packet capture on {port}".format(name=self._name,
                                                                                           id=self._id,
                                                                                           port=port))
