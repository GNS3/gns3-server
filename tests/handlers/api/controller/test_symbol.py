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

from gns3server.config import Config


def test_symbols(http_controller):
    response = http_controller.get('/symbols', example=True)
    assert response.status == 200
    assert {
        'symbol_id': ':/symbols/firewall.svg',
        'url': '/static/builtin_symbols/firewall.svg',
        'filename': 'firewall.svg',
        'builtin': True
    } in response.json
