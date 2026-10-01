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
Interface for anchor-absorbing NIOs (the Ethernet switch's kernel datapath).

A NIO of this type instructs the node to join a *foreign* host interface —
another node's kernel-datapath anchor — into a bridge the node itself owns,
with the node's port settings applied to it. The Ethernet switch is the
consumer: its per-node kernel bridge absorbs the peer's anchor directly, so
frames cross peer anchor -> switch bridge -> switch ports entirely in the
kernel instead of riding the switch's per-port uBridge relay.

This is the mirror of NIOBridge: NIOBridge says "enslave *my* anchor into
the bridge named here", NIOAnchor says "enslave *this* interface into my
own bridge". Impairment filters, markers and capture ride the NIO and
attach to the named anchor (tc on it, marker add_kernel / capture
start_kernel on it) — exactly one link end owns them.
"""

from .nio import NIO


class NIOAnchor(NIO):
    """
    Anchor-absorbing NIO.

    :param anchor: host interface to join to the node's own bridge
    """

    def __init__(self, anchor):

        super().__init__()
        self._anchor = anchor

    @property
    def anchor(self):
        """
        Returns the interface name to absorb.

        :returns: interface name
        """

        return self._anchor

    @property
    def bridge(self):
        """
        Always None: this NIO owns no per-link bridge — the absorbed anchor
        joins the node's *own* bridge. The None makes the shared
        KernelDatapathMixin attach/remove flows skip the per-link bridge
        membership work (their external-bridge case), which is exactly what
        the switch needs on top of its own addif.
        """

        return None

    def __str__(self):

        return "NIO anchor"

    def asdict(self):

        return {
            "type": "nio_anchor",
            "anchor": self._anchor,
            "suspend": self._suspended,
            "filters": self._filters,
            "markers": self._markers,
        }
