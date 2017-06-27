# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 GNS3 Technologies Inc.
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
from gns3server.compute.iou.utils.application_id import get_next_application_id, IOUError


def test_get_next_application_id():
    # test first node
    assert get_next_application_id([]) == 1

    # test second node
    nodes = [
        MagicMock(node_type='different'),
        MagicMock(node_type='iou', properties=dict(application_id=1))
    ]
    assert get_next_application_id(nodes) == 2

    # test reach out the limit
    nodes = [MagicMock(node_type='iou', properties=dict(application_id=i)) for i in range(1, 512)]

    with pytest.raises(IOUError):
        get_next_application_id(nodes)
