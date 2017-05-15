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
from ..utils.picture import get_size
from ..config import Config


class Symbols:
    """
    Manage GNS3 symbols
    """

    def __init__(self):
        try:
            self.list()
        except OSError:  # The error will be raised and forward later
            pass
        # Keep a cache of symbols size
        self._symbol_size_cache = {}

    def list(self):
        self._symbols_path = {}
        symbols = []
        if get_resource("symbols"):
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
        directory = self.symbols_path()
        if directory:
            for file in os.listdir(directory):
                if file.startswith('.'):
                    continue
                if not os.path.isfile(os.path.join(directory, file)):
                    continue
                symbol_id = file
                symbols.append({
                    'symbol_id': symbol_id,
                    'filename': file,
                    'builtin': False,
                })
                self._symbols_path[symbol_id] = os.path.join(directory, file)

        symbols.sort(key=lambda x: x["filename"])

        return symbols

    def symbols_path(self):
        directory = os.path.expanduser(Config.instance().get_section_config("Server").get("symbols_path", "~/GNS3/symbols"))
        if directory:
            os.makedirs(directory, exist_ok=True)
        return directory

    def get_path(self, symbol_id):
        try:
            return self._symbols_path[symbol_id]
        # Symbol not found refresh cache
        except KeyError:
            self.list()
            try:
                return self._symbols_path[symbol_id]
            except KeyError:
                return self._symbols_path[":/symbols/computer.svg"]

    def get_size(self, symbol_id):
        try:
            return self._symbol_size_cache[symbol_id]
        except KeyError:
            with open(self.get_path(symbol_id), "rb") as f:
                res = get_size(f.read())
            self._symbol_size_cache[symbol_id] = res
            return res
