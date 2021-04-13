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
Base interface for NIOs.
"""


class NIO:

    """
    IOU NIO.
    """

    def __init__(self):

        self._capturing = False
        self._suspended = False
        self._filters = {}
        self._pcap_output_file = ""
        self._pcap_data_link_type = ""

    def start_packet_capture(self, pcap_output_file, pcap_data_link_type="DLT_EN10MB"):
        """
        :param pcap_output_file: PCAP destination file for the capture
        :param pcap_data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        self._capturing = True
        self._pcap_output_file = pcap_output_file
        self._pcap_data_link_type = pcap_data_link_type

    def stop_packet_capture(self):

        self._capturing = False
        self._pcap_output_file = ""
        self._pcap_data_link_type = ""

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
