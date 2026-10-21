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
Frames then flow entirely in the kernel (veth -> bridge -> veth). Impairment
filters ride the NIO and run on the veth host end — one tc netem qdisc
(delay/loss/corrupt and the netem extensions), cls_bpf match-drop (bpf) and
the eBPF stateful classifier (frequency_drop, quota, window_drop); markers
and packet capture are served by uBridge's AF_PACKET modules on the
veth host end (marker add_kernel / capture start_kernel).

``bridge`` may be ``None``: the anchor is then bridged elsewhere — an
Ethernet switch absorbed it into the switch's own kernel bridge — and this
node applies only the link state the anchor carries (carrier, markers,
impairments), never bridge membership.

A NIO may additionally carry ``vxlan`` (a BridgeVxlan spec): the link
crosses computes through a VXLAN device this end creates (uBridge's
``vxlan`` module) and enslaves into the same per-link bridge next to the
anchor. The kernel encapsulates/decapsulates the frames; everything else —
filters, markers, capture, carrier, suspend — still runs on the anchor, so
the datapath behaves exactly like a same-host kernel link.
"""

from .nio import NIO


class NIOBridge(NIO):
    """
    Kernel-bridge NIO.

    :param bridge: name of the per-link Linux kernel bridge, or None when
        the anchor is bridged by an Ethernet switch (see module docstring)
    :param vxlan: cross-compute tunnel spec (dict: name/vni/remote/dstport)
        this end creates and enslaves into the bridge, or None for a
        same-host kernel link
    """

    def __init__(self, bridge, vxlan=None):

        super().__init__()
        self._bridge = bridge
        self._vxlan = vxlan

    @property
    def bridge(self):
        """
        Returns the kernel bridge name, or None for an externally bridged
        anchor.

        :returns: bridge name
        """

        return self._bridge

    @property
    def vxlan(self):
        """
        Returns the cross-compute VXLAN tunnel spec, or None when the link
        is wired on this host alone.

        :returns: dict (name/vni/remote/dstport) or None
        """

        return self._vxlan

    def __str__(self):

        return "NIO bridge"

    def asdict(self):

        return {
            "type": "nio_bridge",
            "bridge": self._bridge,
            "vxlan": self._vxlan,
            "suspend": self._suspended,
            "filters": self._filters,
            "markers": self._markers,
        }
