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


from gns3server.utils.picture import get_size


def test_get_size():
    with open("tests/resources/nvram_iou", "rb") as f:
        res = get_size(f.read(), default_width=100, default_height=50)
        assert res == (100, 50, None)
    with open("tests/resources/gns3_icon_128x64.gif", "rb") as f:
        res = get_size(f.read())
        assert res == (128, 64, "gif")
    with open("tests/resources/gns3_icon_128x64.jpg", "rb") as f:
        res = get_size(f.read())
        assert res == (128, 64, "jpg")
    with open("tests/resources/gns3_icon_128x64.png", "rb") as f:
        res = get_size(f.read())
        assert res == (128, 64, "png")
    with open("gns3server/symbols/dslam.svg", "rb") as f:
        res = get_size(f.read())
        assert res == (50, 53, "svg")
    # Symbol using size with cm
    with open("gns3server/symbols/cloud.svg", "rb") as f:
        res = get_size(f.read())
        assert res == (159, 71, "svg")
    # Size with px
    with open("tests/resources/firefox.svg", "rb") as f:
        res = get_size(f.read())
        assert res == (66, 70, "svg")
