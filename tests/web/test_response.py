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

from tests.utils import AsyncioMagicMock
from aiohttp.web import HTTPNotFound

from gns3server.web.response import Response


@pytest.fixture()
def response():
    request = AsyncioMagicMock()
    return Response(request=request)


# async def test_response_file(tmpdir, response):
#
#     filename = str(tmpdir / 'hello')
#     with open(filename, 'w+') as f:
#         f.write('world')
#
#     await response.stream_file(filename)
#     assert response.status == 200


async def test_response_file_not_found(tmpdir, response):

    filename = str(tmpdir / 'hello-not-found')
    with pytest.raises(HTTPNotFound):
        await response.stream_file(filename)
