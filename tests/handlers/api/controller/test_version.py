# -*- coding: utf-8 -*-
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


from gns3server.version import __version__


async def test_version_output(controller_api, config):

    config.set("Server", "local", "true")
    response = await controller_api.get('/version')
    assert response.status == 200
    assert response.json == {'local': True, 'version': __version__}


async def test_version_input(controller_api):

    params = {'version': __version__}
    response = await controller_api.post('/version', params)
    assert response.status == 200
    assert response.json == {'version': __version__}


async def test_version_invalid_input(controller_api):

    params = {'version': "0.4.2"}
    response = await controller_api.post('/version', params)
    assert response.status == 409
    assert response.json == {'message': 'Client version 0.4.2 is not the same as server version {}'.format(__version__),
                             'status': 409}


async def test_version_invalid_input_schema(controller_api):

    params = {'version': "0.4.2", "bla": "blu"}
    response = await controller_api.post('/version', params)
    assert response.status == 400


async def test_version_invalid_json(controller_api):

    params = "BOUM"
    response = await controller_api.post('/version', params, raw=True)
    assert response.status == 400
