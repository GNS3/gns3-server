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


from ..utils.get_resource import get_resource


class Symbols:
    """
    Manage GNS3 symbols
    """

    def __init__(self):
        self.list()

    def list(self):
        self._symbols_path = {}
        symbols = []
        for file in os.listdir(get_resource("symbols")):
            if file.startswith('.'):
                continue
            symbol_id = ':/symbols/' + file
            symbols.append({
                'symbol_id': symbol_id,
                'filename': file,
                'builtin': True,
            })
            self._symbols_path[symbol_id] = os.path.join(get_resource("symbols"), file)
        symbols.sort(key=lambda x: x["filename"])

        #TODO: support ~/GNS3/symbols directory
        return symbols

    def get_path(self, symbol_id):
        return self._symbols_path[symbol_id]
