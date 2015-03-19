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

from unittest.mock import MagicMock, patch
from gns3server.config import Config


def test_reload_accepted(server):

    gns_config = MagicMock()
    config = Config.instance()
    config.set("Server", "local", "true")
    gns_config.get_section_config.return_value = config.get_section_config("Server")

    with patch("gns3server.config.Config.instance", return_value=gns_config):
        response = server.post('/config/reload', example=True)

    assert response.status == 201
    assert gns_config.reload.called


def test_reload_forbidden(server):

    config = Config.instance()
    config.set("Server", "local", "false")

    response = server.post('/config/reload')

    assert response.status == 403
