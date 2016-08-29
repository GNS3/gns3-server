#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import socket
from .cloud import Cloud
from ...error import NodeError


class Nat(Cloud):
    """
    A portable and preconfigured node allowing topology to get a
    nat access to the outside
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if socket.gethostname() != "gns3vm":
            raise NodeError("NAT node is supported only on GNS3 VM")

        self.ports = [
            {
                "name": "nat0",
                "type": "ethernet",
                "interface": "eth1",
                "port_number": 1
            }
        ]

    @classmethod
    def is_supported(self):
        return socket.gethostname() == "gns3vm"

    def __json__(self):
        return {
            "name": self.name,
            "node_id": self.id,
            "project_id": self.project.id,
            "status": "started",
            "ports": self.ports
        }
