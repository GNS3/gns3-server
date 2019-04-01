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
Base interface for Dynamips Network Input/Output (NIO) module ("nio").
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L451
"""

import asyncio
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class NIO:

    """
    Base NIO class

    :param hypervisor: Dynamips hypervisor instance
    """

    def __init__(self, name, hypervisor):

        self._hypervisor = hypervisor
        self._name = name
        self._filters = {}
        self._suspended = False
        self._capturing = False
        self._pcap_output_file = ""
        self._pcap_data_link_type = ""
        self._bandwidth = None  # no bandwidth constraint by default
        self._input_filter = None  # no input filter applied by default
        self._output_filter = None  # no output filter applied by default
        self._input_filter_options = None  # no input filter options by default
        self._output_filter_options = None  # no output filter options by default
        self._dynamips_direction = {"in": 0, "out": 1, "both": 2}

    async def list(self):
        """
        Returns all NIOs.

        :returns: NIO list
        """

        nio_list = await self._hypervisor.send("nio list")
        return nio_list

    async def delete(self):
        """
        Deletes this NIO.
        """

        if self._input_filter or self._output_filter:
            await self.unbind_filter("both")
            self._capturing = False
        await self._hypervisor.send("nio delete {}".format(self._name))
        log.info("NIO {name} has been deleted".format(name=self._name))

    async def rename(self, new_name):
        """
        Renames this NIO

        :param new_name: new NIO name
        """

        await self._hypervisor.send("nio rename {name} {new_name}".format(name=self._name, new_name=new_name))

        log.info("NIO {name} renamed to {new_name}".format(name=self._name, new_name=new_name))
        self._name = new_name

    async def debug(self, debug):
        """
        Enables/Disables debugging for this NIO.

        :param debug: debug value (0 = disable, enable = 1)
        """

        await self._hypervisor.send("nio set_debug {name} {debug}".format(name=self._name, debug=debug))

    async def start_packet_capture(self, pcap_output_file, pcap_data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param pcap_output_file: PCAP destination file for the capture
        :param pcap_data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        await self.bind_filter("both", "capture")
        await self.setup_filter("both", '{} "{}"'.format(pcap_data_link_type, pcap_output_file))
        self._capturing = True
        self._pcap_output_file = pcap_output_file
        self._pcap_data_link_type = pcap_data_link_type

    async def stop_packet_capture(self):
        """
        Stops a packet capture.
        """

        await self.unbind_filter("both")
        self._capturing = False
        self._pcap_output_file = ""
        self._pcap_data_link_type = ""

    async def bind_filter(self, direction, filter_name):
        """
        Adds a packet filter to this NIO.
        Filter "freq_drop" drops packets.
        Filter "capture" captures packets.

        :param direction: "in", "out" or "both"
        :param filter_name: name of the filter to apply
        """

        if direction not in self._dynamips_direction:
            raise DynamipsError("Unknown direction {} to bind filter {}:".format(direction, filter_name))
        dynamips_direction = self._dynamips_direction[direction]

        await self._hypervisor.send("nio bind_filter {name} {direction} {filter}".format(name=self._name,
                                                                                              direction=dynamips_direction,
                                                                                              filter=filter_name))

        if direction == "in":
            self._input_filter = filter_name
        elif direction == "out":
            self._output_filter = filter_name
        elif direction == "both":
            self._input_filter = filter_name
            self._output_filter = filter_name

    async def unbind_filter(self, direction):
        """
        Removes packet filter for this NIO.

        :param direction: "in", "out" or "both"
        """

        if direction not in self._dynamips_direction:
            raise DynamipsError("Unknown direction {} to unbind filter:".format(direction))
        dynamips_direction = self._dynamips_direction[direction]

        await self._hypervisor.send("nio unbind_filter {name} {direction}".format(name=self._name,
                                                                                       direction=dynamips_direction))

        if direction == "in":
            self._input_filter = None
        elif direction == "out":
            self._output_filter = None
        elif direction == "both":
            self._input_filter = None
            self._output_filter = None
        self._capturing = False

    async def setup_filter(self, direction, options):
        """
        Setups a packet filter bound with this NIO.

        Filter "freq_drop" has 1 argument "<frequency>". It will drop
        everything with a -1 frequency, drop every Nth packet with a
        positive frequency, or drop nothing.

        Filter "capture" has 2 arguments "<link_type_name> <output_file>".
        It will capture packets to the target output file. The link type
        name is a case-insensitive DLT_ name from the PCAP library
        constants with the DLT_ part removed.See http://www.tcpdump.org/linktypes.html
        for a list of all available DLT values.

        :param direction: "in", "out" or "both"
        :param options: options for the packet filter (string)
        """

        if direction not in self._dynamips_direction:
            raise DynamipsError("Unknown direction {} to setup filter:".format(direction))
        dynamips_direction = self._dynamips_direction[direction]

        await self._hypervisor.send("nio setup_filter {name} {direction} {options}".format(name=self._name,
                                                                                                direction=dynamips_direction,
                                                                                                options=options))

        if direction == "in":
            self._input_filter_options = options
        elif direction == "out":
            self._output_filter_options = options
        elif direction == "both":
            self._input_filter_options = options
            self._output_filter_options = options

    @property
    def input_filter(self):
        """
        Returns the input packet filter for this NIO.

        :returns: tuple (filter name, filter options)
        """

        return self._input_filter, self._input_filter_options

    @property
    def output_filter(self):
        """
        Returns the output packet filter for this NIO.

        :returns: tuple (filter name, filter options)
        """

        return self._output_filter, self._output_filter_options

    async def get_stats(self):
        """
        Gets statistics for this NIO.

        :returns: NIO statistics (string with packets in, packets out, bytes in, bytes out)
        """

        stats = await self._hypervisor.send("nio get_stats {}".format(self._name))
        return stats[0]

    async def reset_stats(self):
        """
        Resets statistics for this NIO.
        """

        await self._hypervisor.send("nio reset_stats {}".format(self._name))

    @property
    def bandwidth(self):
        """
        Returns the bandwidth constraint for this NIO.

        :returns: bandwidth integer value (in Kb/s)
        """

        return self._bandwidth

    async def set_bandwidth(self, bandwidth):
        """
        Sets bandwidth constraint.

        :param bandwidth: bandwidth integer value (in Kb/s)
        """

        await self._hypervisor.send("nio set_bandwidth {name} {bandwidth}".format(name=self._name, bandwidth=bandwidth))
        self._bandwidth = bandwidth

    @property
    def suspend(self):
        """
        Returns if this link is suspended or not.

        :returns: boolean
        """

        return self._suspended

    @suspend.setter
    def suspend(self, suspended):
        """
        Suspend this link.

        :param suspended: boolean
        """

        self._suspended = suspended

    @property
    def filters(self):
        """
        Returns the list of packet filters for this NIO.

        :returns: packet filters (dictionary)
        """

        return self._filters

    @filters.setter
    def filters(self, new_filters):
        """
        Set a list of packet filters for this NIO.

        :param new_filters: packet filters (dictionary)
        """

        assert isinstance(new_filters, dict)
        self._filters = new_filters

    @property
    def capturing(self):
        """
        Returns either a capture is configured on this NIO.
        :returns: boolean
        """

        return self._capturing

    @property
    def pcap_output_file(self):
        """
        Returns the path to the PCAP output file.

        :returns: path to the PCAP output file
        """

        return self._pcap_output_file

    @property
    def pcap_data_link_type(self):
        """
        Returns the PCAP data link type

        :returns: PCAP data link type (DLT_* value)
        """

        return self._pcap_data_link_type

    def __str__(self):
        """
        NIO string representation.

        :returns: NIO name
        """

        return self._name

    @property
    def name(self):
        """
        Returns the NIO name.

        :returns: NIO name
        """

        return self._name
