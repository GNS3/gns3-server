#!/usr/bin/env python
#
# Copyright (C) 2024 GNS3 Technologies Inc.
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
#
# Traffic-insight marker subsystem (compute side).
#
# ubridge's ``marker`` module is a passive tap: on a BPF match it emits a UDP
# ``MARK`` signal to a configured sink and/or appends the packet to a pcap.
# This package owns the compute-side UDP sink: one listener per compute process
# serves every ubridge on that host, disambiguated by ``node=<id>``.
