# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 GNS3 Technologies Inc.
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

import pytest

from unittest.mock import MagicMock
from aiohttp.web import HTTPNotFound

from gns3server.web.response import Response


@pytest.fixture()
def response():
    request = MagicMock()
    return Response(request=request)


def test_response_file(async_run, tmpdir, response):
    filename = str(tmpdir / 'hello')
    with open(filename, 'w+') as f:
        f.write('world')

    async_run(response.stream_file(filename))
    assert response.status == 200


def test_response_file_not_found(async_run, tmpdir, response):
    filename = str(tmpdir / 'hello-not-found')

    pytest.raises(HTTPNotFound, lambda: async_run(response.stream_file(filename)))
