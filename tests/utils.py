# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

import asyncio
from unittest.mock import patch


def asyncio_patch(function, *args, **kwargs):
    @asyncio.coroutine
    def fake_anwser(*a, **kw):
        return kwargs["return_value"]

    def register(func):
        @patch(function, return_value=fake_anwser)
        @asyncio.coroutine
        def inner(*a, **kw):
            return func(*a, **kw)
        return inner
    return register
