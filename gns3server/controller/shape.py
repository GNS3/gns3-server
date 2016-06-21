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

import asyncio
import uuid


class Shape:
    """
    Shape are visual element not used by the network emulation. Like
    text, images, rectangle... They are pure SVG elements.
    """
    def __init__(self, project, shape_id=None, svg="<svg></svg>", x=0, y=0, z=0):
        self.svg = svg
        self._project = project
        if shape_id is None:
            self._id = str(uuid.uuid4())
        else:
            self._id = shape_id
        self._x = x
        self._y = y
        self._z = z

    @property
    def id(self):
        return self._id

    @property
    def svg(self):
        return self._svg

    @svg.setter
    def svg(self, value):
        self._svg = value

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, val):
        self._x = val

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, val):
        self._y = val

    @property
    def z(self):
        return self._z

    @z.setter
    def z(self, val):
        self._z = val

    @asyncio.coroutine
    def update(self, **kwargs):
        """
        Update the shape

        :param kwargs: Shape properties
        """

        # Update node properties with additional elements
        for prop in kwargs:
            if getattr(self, prop) != kwargs[prop]:
                setattr(self, prop, kwargs[prop])
        self._project.controller.notification.emit("shape.updated", self.__json__())
        self._project.dump()

    def __json__(self, topology_dump=False):
        """
        :param topology_dump: Filter to keep only properties require for saving on disk
        """
        if topology_dump:
            return {
                "shape_id": self._id,
                "x": self._x,
                "y": self._y,
                "z": self._z,
                "svg": self._svg
            }
        return {
            "project_id": self._project.id,
            "shape_id": self._id,
            "x": self._x,
            "y": self._y,
            "z": self._z,
            "svg": self._svg
        }

    def __repr__(self):
        return "<gns3server.controller.Shape {}>".format(self._id)


