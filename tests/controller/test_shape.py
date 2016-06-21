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

from unittest.mock import MagicMock
import pytest
import uuid

from tests.utils import AsyncioMagicMock


from gns3server.controller.shape import Shape
from gns3server.controller.project import Project


@pytest.fixture
def project(controller, async_run):
    return async_run(controller.add_project())


@pytest.fixture
def shape(project):
    return Shape(project, None, svg="<svg></svg>")


def test_init_without_uuid(project):
    shape = Shape(project, None, svg="<svg></svg>")
    assert shape.id is not None


def test_init_with_uuid(project):
    id = str(uuid.uuid4())
    shape = Shape(project, id, svg="<svg></svg>")
    assert shape.id == id


def test_json(project):
    i = Shape(project, None, svg="<svg></svg>")
    assert i.__json__() == {
        "shape_id": i.id,
        "project_id": project.id,
        "x": i.x,
        "y": i.y,
        "z": i.z,
        "svg": i.svg
    }
    assert i.__json__(topology_dump=True) == {
        "shape_id": i.id,
        "x": i.x,
        "y": i.y,
        "z": i.z,
        "svg": i.svg
    }


def test_update(shape, project, async_run, controller):
    controller._notification = AsyncioMagicMock()
    project.dump = MagicMock()

    async_run(shape.update(x=42))
    assert shape.x == 42
    controller._notification.emit.assert_called_with("shape.updated", shape.__json__())
    assert project.dump.called
