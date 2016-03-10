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

import pytest
import uuid
import aiohttp
from unittest.mock import MagicMock


from gns3server.controller import Controller
from gns3server.controller.hypervisor import Hypervisor
from gns3server.controller.project import Project
from gns3server.config import Config


def test_isEnabled(controller):
    Config.instance().set("Server", "controller", False)
    assert not controller.isEnabled()
    Config.instance().set("Server", "controller", True)
    assert controller.isEnabled()


def test_addHypervisor(controller, async_run):
    async_run(controller.addHypervisor("test1"))
    assert len(controller.hypervisors) == 1
    async_run(controller.addHypervisor("test1"))
    assert len(controller.hypervisors) == 1
    async_run(controller.addHypervisor("test2"))
    assert len(controller.hypervisors) == 2


def test_getHypervisor(controller, async_run):

    hypervisor = async_run(controller.addHypervisor("test1"))

    assert controller.getHypervisor("test1") == hypervisor
    with pytest.raises(aiohttp.web.HTTPNotFound):
        assert controller.getHypervisor("dsdssd")


def test_addProject(controller, async_run):
    uuid1 = str(uuid.uuid4())
    uuid2 = str(uuid.uuid4())

    async_run(controller.addProject(project_id=uuid1))
    assert len(controller.projects) == 1
    async_run(controller.addProject(project_id=uuid1))
    assert len(controller.projects) == 1
    async_run(controller.addProject(project_id=uuid2))
    assert len(controller.projects) == 2


def test_removeProject(controller, async_run):
    uuid1 = str(uuid.uuid4())

    project1 = async_run(controller.addProject(project_id=uuid1))
    assert len(controller.projects) == 1

    controller.removeProject(project1)
    assert len(controller.projects) == 0


def test_addProject_with_hypervisor(controller, async_run):
    uuid1 = str(uuid.uuid4())

    hypervisor = Hypervisor("test1")
    hypervisor.post = MagicMock()
    controller._hypervisors = {"test1": hypervisor }

    project1 = async_run(controller.addProject(project_id=uuid1))
    hypervisor.post.assert_called_with("/projects", project1)


def test_getProject(controller, async_run):
    uuid1 = str(uuid.uuid4())

    project = async_run(controller.addProject(project_id=uuid1))
    assert controller.getProject(uuid1) == project
    with pytest.raises(aiohttp.web.HTTPNotFound):
        assert controller.getProject("dsdssd")
