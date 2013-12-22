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

#import networkx as nx


class Topology(object):

    def __init__(self):

        pass
        #self._topology = nx.Graph()

    def add_node(self, node):

        self._topology.add_node(node)

    def remove_node(self, node):

        self._topology.remove_node(node)

    def clear(self):

        self._topology.clear()

    def __str__(self):

        return "GNS3 network topology"

    @staticmethod
    def instance():

        if not hasattr(Topology, "_instance"):
            Topology._instance = Topology()
        return Topology._instance
