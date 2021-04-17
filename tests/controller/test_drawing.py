#!/usr/bin/env python
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

from unittest.mock import MagicMock
import pytest
import uuid
import os

from tests.utils import AsyncioMagicMock

from gns3server.controller.drawing import Drawing


@pytest.fixture
def drawing(project):

    return Drawing(project, None, svg="<svg></svg>")


def test_init_without_uuid(project):

    drawing = Drawing(project, None, svg="<svg></svg>")
    assert drawing.id is not None


def test_init_with_uuid(project):

    id = str(uuid.uuid4())
    drawing = Drawing(project, id, svg="<svg></svg>")
    assert drawing.id == id


def test_json(project):

    i = Drawing(project, None, svg="<svg></svg>")
    assert i.asdict() == {
        "drawing_id": i.id,
        "project_id": project.id,
        "x": i.x,
        "y": i.y,
        "z": i.z,
        "locked": i.locked,
        "svg": i.svg,
        "rotation": i.rotation
    }
    assert i.asdict(topology_dump=True) == {
        "drawing_id": i.id,
        "x": i.x,
        "y": i.y,
        "z": i.z,
        "rotation": i.rotation,
        "locked": i.locked,
        "svg": i.svg
    }


@pytest.mark.asyncio
async def test_update(drawing, project, controller):

    controller._notification = AsyncioMagicMock()
    project.dump = MagicMock()

    await drawing.update(x=42, svg="<svg><rect></rect></svg>")
    assert drawing.x == 42
    args, kwargs = controller._notification.project_emit.call_args
    assert args[0] == "drawing.updated"
    # JSON
    assert args[1]["x"] == 42
    assert args[1]["svg"] == "<svg><rect></rect></svg>"

    await drawing.update(x=12, svg="<svg><rect></rect></svg>")
    assert drawing.x == 12
    args, kwargs = controller._notification.project_emit.call_args
    assert args[0] == "drawing.updated"
    # JSON
    assert args[1]["x"] == 12
    # To avoid spamming client with large data we don't send the svg if the SVG didn't change
    assert "svg" not in args[1]

    assert project.dump.called


def test_image_base64(project):
    """
    If image are embed as base 64 we need to dump them on disk
    """

    svg = "<svg xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" height=\"128\" width=\"128\">\n<image height=\"128\" width=\"128\" xlink:href=\"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAYAAADDPmHLAAAACXBIWXMAAAN2AAADdgF91YLMAAAAGXRFWHRTb2Z0d2FyZQB3d3cuaW5rc2NhcGUub3Jnm+48GgAAHm5JREFUeJztnXl8FGXSx7/VIYAKKCoe4IEIq6ALuQnI4YXXKihulCSACIIsu4qKNyqXByqK67EeiMtyJGrwXnfABSu/L3I31aclPub3oBIQ/YD2zdUBZ+T37l7Dt0OAKoIYcUf07mBhpkieonJe+FcAUOgeX8dL/4ysTCSmTiwwsx1FPLJfuas89mXsByu/N/BR43E09+xMafDrYFI6wmzINu7QreFo1kD4EQIW/m8ICm1iAdBXWp0wuusiJp+Q7ilok3VE02RR+MoWPTYMXTYNlarAx6c6iQU7X/RbQ4DZA2m1F44CnrdYjDPG8ZcLBe/1kzz2Z9ybfUZQALAS\" />\n</svg>"

    drawing = Drawing(project, None, svg=svg)
    assert drawing._svg == "8418154b760b4e8023650e04c4992e24.png"
    assert os.path.exists(os.path.join(project.pictures_directory, "8418154b760b4e8023650e04c4992e24.png"))

    assert drawing.svg == svg


def test_image_svg(project):
    """
    Large SVG are dump on disk
    """

    svg = "<svg xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" height=\"128\" width=\"128\">\n"

    for i in range(0, 1000):
        svg += "<rect width=\"100\"></rect>"
    svg += "</svg>"

    drawing = Drawing(project, None, svg=svg)
    assert drawing._svg == "fdf4d3035774a72ba165f7199b9431b2.svg"
    assert os.path.exists(os.path.join(project.pictures_directory, "fdf4d3035774a72ba165f7199b9431b2.svg"))

    assert drawing.svg.replace("\r", "") == svg.replace("\r", "")
