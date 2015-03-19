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

import os

from gns3server.web.documentation import Documentation
from gns3server.handlers import *
from gns3server.web.route import Route


def test_documentation_write(tmpdir):
    os.makedirs(str(tmpdir / "api/examples"))
    with open(str(tmpdir / "api/examples/post_projectsprojectidvirtualboxvms.txt"), "w+") as f:
        f.write("curl test")

    Documentation(Route, str(tmpdir)).write()

    assert os.path.exists(str(tmpdir / "api"))
    assert os.path.exists(str(tmpdir / "api" / "v1"))
    assert os.path.exists(str(tmpdir / "api" / "v1" / "virtualbox.rst"))
    assert os.path.exists(str(tmpdir / "api" / "v1" / "virtualbox"))
    assert os.path.exists(str(tmpdir / "api" / "v1" / "virtualbox" / "virtualboxvms.rst"))
    with open(str(tmpdir / "api" / "v1" / "virtualbox" / "projectsprojectidvirtualboxvms.rst")) as f:
        content = f.read()
        assert "Sample session" in content
        assert "literalinclude:: ../../examples/post_projectsprojectidvirtualboxvms.txt" in content
