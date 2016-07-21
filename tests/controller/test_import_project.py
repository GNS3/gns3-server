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

import os
import uuid
import json
import zipfile


from gns3server.controller.project import Project
from gns3server.controller.import_project import import_project


def test_import_project(async_run, tmpdir, controller):
    project_id = str(uuid.uuid4())

    topology = {
        "project_id": str(uuid.uuid4()),
        "name": "test",
        "topology": {
        },
        "version": "2.0.0"
    }

    with open(str(tmpdir / "project.gns3"), 'w+') as f:
        json.dump(topology, f)
    with open(str(tmpdir / "b.png"), 'w+') as f:
        f.write("B")

    zip_path = str(tmpdir / "project.zip")
    with zipfile.ZipFile(zip_path, 'w') as myzip:
        myzip.write(str(tmpdir / "project.gns3"), "project.gns3")
        myzip.write(str(tmpdir / "b.png"), "b.png")
        myzip.write(str(tmpdir / "b.png"), "project-files/dynamips/test")
        myzip.write(str(tmpdir / "b.png"), "project-files/qemu/test")

    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, project_id, f))

    assert project.name == "test"
    assert project.id == project_id # The project should changed

    assert os.path.exists(os.path.join(project.path, "b.png"))
    assert not os.path.exists(os.path.join(project.path, "project.gns3"))
    assert os.path.exists(os.path.join(project.path, "test.gns3"))
    assert os.path.exists(os.path.join(project.path, "project-files/dynamips/test"))
    assert os.path.exists(os.path.join(project.path, "project-files/qemu/test"))

    # A new project name is generated when you import twice the same name
    with open(zip_path, "rb") as f:
        project = async_run(import_project(controller, str(uuid.uuid4()), f))
    assert project.name != "test"



