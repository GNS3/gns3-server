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
import posixpath

from .symbol_themes import BUILTIN_SYMBOL_THEMES
from .controller_error import ControllerNotFoundError
from ..utils.get_resource import get_resource
from ..utils.picture import get_size
from ..config import Config

import logging

log = logging.getLogger(__name__)


class Symbols:
    """
    Manage GNS3 symbols
    """

    def __init__(self):

        try:
            self.list()
        except OSError:  # The error will be raised and forwarded later
            pass

        # Keep a cache of symbols size
        self._symbol_size_cache = {}

        self._server_config = Config.instance().settings.Server
        self._current_theme = self._server_config.default_symbol_theme
        self._themes = BUILTIN_SYMBOL_THEMES

    @property
    def theme(self):

        return self._current_theme

    @theme.setter
    def theme(self, theme):

        if not self._themes.get(theme):
            raise ControllerNotFoundError(f"Could not find symbol theme '{theme}'")
        self._current_theme = theme

    def default_symbols(self):

        return BUILTIN_SYMBOL_THEMES

    def get_default_symbol(self, symbol, symbol_theme):

        theme = self._themes.get(symbol_theme, None)
        if not theme:
            log.warning(f"Could not find symbol theme '{symbol_theme}'")
            return None
        symbol_path = theme.get(symbol)
        if symbol_path not in self._symbols_path:
            log.debug(f"Default symbol {symbol} was not found")
            return None
        return symbol_path

    def list(self):

        self._symbols_path = {}
        symbols = []
        if get_resource("symbols"):
            for root, _, files in os.walk(get_resource("symbols")):
                for filename in files:
                    if filename.startswith("."):
                        continue
                    symbol_file = posixpath.normpath(
                        os.path.relpath(os.path.join(root, filename), get_resource("symbols"))
                    ).replace("\\", "/")
                    theme = posixpath.dirname(symbol_file).replace("/", "-").capitalize()
                    if not theme:
                        continue
                    symbol_id = ":/symbols/" + symbol_file
                    symbols.append({"symbol_id": symbol_id, "filename": filename, "theme": theme, "builtin": True})
                    self._symbols_path[symbol_id] = os.path.join(root, filename)

        directory = self.symbols_path()
        if directory:
            for root, _, files in os.walk(directory):
                for filename in files:
                    if filename.startswith("."):
                        continue
                    symbol_file = posixpath.normpath(os.path.relpath(os.path.join(root, filename), directory)).replace(
                        "\\", "/"
                    )
                    theme = posixpath.dirname(symbol_file).replace("/", "-").capitalize()
                    if not theme:
                        theme = "Custom symbols"
                    symbols.append({"symbol_id": symbol_file, "filename": filename, "builtin": False, "theme": theme})
                    self._symbols_path[symbol_file] = os.path.join(root, filename)
        symbols.sort(key=lambda x: x["theme"])
        return symbols

    def symbols_path(self):

        server_config = Config.instance().settings.Server
        directory = os.path.expanduser(server_config.symbols_path)
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                log.error(f"Could not create symbol directory '{directory}': {e}")
                return None
        return directory

    def has_symbol(self, symbol_id):

        return self._symbols_path.get(symbol_id)

    def resolve_symbol(self, symbol_name):

        if not symbol_name.startswith(":/"):
            symbol = self.get_default_symbol(symbol_name, self._current_theme)
            if symbol:
                return symbol
        return symbol_name

    def get_path(self, symbol_id):

        symbol_id = self.resolve_symbol(symbol_id)
        try:
            return self._symbols_path[symbol_id]
        except KeyError:
            try:
                self.list()
                return self._symbols_path[symbol_id]
            except (OSError, KeyError):
                # try to return a symbol with the same name from the classic theme
                symbol = self._symbols_path.get(f":/symbols/classic/{os.path.basename(symbol_id)}")
                if symbol:
                    return symbol
                else:
                    # return the default computer symbol
                    log.warning(f"Could not retrieve symbol '{symbol_id}', returning default symbol...")
                    symbol = self.get_default_symbol("computer", self._current_theme)
                    if symbol and symbol in self._symbols_path:
                        return self._symbols_path[symbol]
                    return self._symbols_path[":/symbols/classic/computer.svg"]

    def get_size(self, symbol_id):
        try:
            return self._symbol_size_cache[symbol_id]
        except KeyError:
            with open(self.get_path(symbol_id), "rb") as f:
                res = get_size(f.read())
            self._symbol_size_cache[symbol_id] = res
            return res
