#!/usr/bin/env python
#
# Copyright (C) 2020 GNS3 Technologies Inc.
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


def test_list(symbols_dir):

    with open(os.path.join(symbols_dir, "linux.svg"), "w+") as f:
        pass

    symbols = Symbols()
    assert {
        'symbol_id': ':/symbols/classic/firewall.svg',
        'filename': 'firewall.svg',
        'builtin': True,
        'theme': 'Classic'
    } in symbols.list()
    assert {
        'symbol_id': 'linux.svg',
        'filename': 'linux.svg',
        'builtin': False,
        'theme': 'Custom symbols'
    } in symbols.list()


def test_get_path():

    symbols = Symbols()
    symbols.theme = "Classic"
    assert symbols.get_path(':/symbols/classic/firewall.svg') == get_resource("symbols/classic/firewall.svg")


def test_get_size():

    symbols = Symbols()
    symbols.theme = "Classic"
    assert symbols.get_size(':/symbols/classic/firewall.svg') == (66, 45, 'svg')
