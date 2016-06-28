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

import os


from gns3server.controller.symbols import Symbols
from gns3server.utils.get_resource import get_resource


def test_list():
    symbols = Symbols()
    assert {
        'symbol_id': ':/symbols/firewall.svg',
        'filename': 'firewall.svg',
        'builtin': True
    } in symbols.list()
    assert symbols


def test_get_path():
    symbols = Symbols()
    assert symbols.get_path(':/symbols/firewall.svg') == get_resource("symbols/firewall.svg")
