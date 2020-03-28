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

import hashlib
import base64
import uuid
import re
import os
import xml.etree.ElementTree as ET


from gns3server.utils.picture import get_size


import logging
log = logging.getLogger(__name__)


class Drawing:
    """
    Drawing are visual element not used by the network emulation. Like
    text, images, rectangle... They are pure SVG elements.
    """

    def __init__(self, project, drawing_id=None, svg="<svg></svg>", x=0, y=0, z=2, locked=False, rotation=0):
        self._project = project
        if drawing_id is None:
            self._id = str(uuid.uuid4())
        else:
            self._id = drawing_id
        self._svg = "<svg></svg>"
        self.svg = svg
        self._x = x
        self._y = y
        self._z = z
        self._rotation = rotation
        self._locked = locked

    @property
    def id(self):
        return self._id

    @property
    def resource_filename(self):
        """
        If the svg content has been dump to an external file return is name otherwise None
        """
        if "<svg" not in self._svg:
            return self._svg
        return None

    @property
    def svg(self):
        if "<svg" not in self._svg:
            try:
                filename = os.path.basename(self._svg)
                with open(os.path.join(self._project.pictures_directory, filename), "rb") as f:
                    data = f.read()
                    try:
                        return data.decode()
                    except UnicodeError:
                        width, height, filetype = get_size(data)
                        return "<svg xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" height=\"{height}\" width=\"{width}\">\n<image height=\"{height}\" width=\"{width}\" xlink:href=\"data:image/{filetype};base64,{b64}\" />\n</svg>".format(b64=base64.b64encode(data).decode(), filetype=filetype, width=width, height=height)
            except OSError:
                log.warning("Image file %s missing", filename)
                return "<svg></svg>"
        return self._svg

    @svg.setter
    def svg(self, value):
        """
        Set SVG field value.

        If the svg has embed base64 element we will extract them
        to disk in order to avoid duplication of content
        """

        if len(value) < 500:
            self._svg = value
            return

        try:
            root = ET.fromstring(value)
        except ET.ParseError as e:
            log.error("Can't parse SVG: {}".format(e))
            return
        # SVG is the default namespace no need to prefix it
        ET.register_namespace('xmlns', "http://www.w3.org/2000/svg")
        ET.register_namespace('xmlns:xlink', "http://www.w3.org/1999/xlink")

        if len(root.findall("{http://www.w3.org/2000/svg}image")) == 1:
            href = "{http://www.w3.org/1999/xlink}href"
            elem = root.find("{http://www.w3.org/2000/svg}image")
            if elem.get(href, "").startswith("data:image/"):
                changed = True
                data = elem.get(href, "")
                extension = re.sub(r"[^a-z0-9]", "", data.split(";")[0].split("/")[1].lower())

                data = base64.decodebytes(data.split(",", 1)[1].encode())

                # We compute an hash of the image file to avoid duplication
                filename = hashlib.md5(data).hexdigest() + "." + extension
                elem.set(href, filename)

                file_path = os.path.join(self._project.pictures_directory, filename)
                if not os.path.exists(file_path):
                    with open(file_path, "wb") as f:
                        f.write(data)
                value = filename

        # We dump also large svg on disk to keep .gns3 small
        if len(value) > 1000:
            filename = hashlib.md5(value.encode()).hexdigest() + ".svg"
            file_path = os.path.join(self._project.pictures_directory, filename)
            if not os.path.exists(file_path):
                with open(file_path, "w+", encoding="utf-8") as f:
                    f.write(value)
            self._svg = filename
        else:
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

    @property
    def locked(self):
        return self._locked

    @locked.setter
    def locked(self, val):
        self._locked = val

    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, val):
        self._rotation = val

    async def update(self, **kwargs):
        """
        Update the drawing

        :param kwargs: Drawing properties
        """

        # Update node properties with additional elements
        svg_changed = False
        for prop in kwargs:
            if prop == "drawing_id":
                pass  # No good reason to change a drawing_id
            elif getattr(self, prop) != kwargs[prop]:
                if prop == "svg":
                    # To avoid spamming client with large data we don't send the svg if the SVG didn't change
                    svg_changed = True
                setattr(self, prop, kwargs[prop])
        data = self.__json__()
        if not svg_changed:
            del data["svg"]
        self._project.emit_notification("drawing.updated", data)
        self._project.dump()

    def __json__(self, topology_dump=False):
        """
        :param topology_dump: Filter to keep only properties require for saving on disk
        """
        if topology_dump:
            return {
                "drawing_id": self._id,
                "x": self._x,
                "y": self._y,
                "z": self._z,
                "locked": self._locked,
                "rotation": self._rotation,
                "svg": self._svg
            }
        return {
            "project_id": self._project.id,
            "drawing_id": self._id,
            "x": self._x,
            "y": self._y,
            "z": self._z,
            "locked": self._locked,
            "rotation": self._rotation,
            "svg": self.svg
        }

    def __repr__(self):
        return "<gns3server.controller.Drawing {}>".format(self._id)
