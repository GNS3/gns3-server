#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
#

"""
Interface for kernel-datapath bridge NIOs.

A NIO of this type instructs the node to enslave its adapter's veth host end
into the named Linux kernel bridge instead of wiring a uBridge UDP relay.
Frames then flow entirely in the kernel (veth -> bridge -> veth). Filters,
markers and packet capture are not available on this datapath (they live in
the uBridge relay); the controller must only emit this NIO type for links
where those features are not in use.
"""

from .nio import NIO


class NIOBridge(NIO):

    """
    Kernel-bridge NIO.

    :param bridge: name of the per-link Linux kernel bridge
    """

    def __init__(self, bridge):

        super().__init__()
        self._bridge = bridge

    @property
    def bridge(self):
        """
        Returns the kernel bridge name.

        :returns: bridge name
        """

        return self._bridge

    def __str__(self):

        return "NIO bridge"

    def asdict(self):

        return {
            "type": "nio_bridge",
            "bridge": self._bridge,
            "suspend": self._suspended,
            "filters": self._filters,
            "markers": self._markers,
        }
