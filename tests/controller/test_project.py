#!/usr/bin/env python
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

import pytest
import aiohttp
from unittest.mock import MagicMock


from gns3server.controller.project import Project


def test_affect_uuid():
    p = Project()
    assert len(p.id) == 36

    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert p.id == '00010203-0405-0607-0809-0a0b0c0d0e0f'


def test_json(tmpdir):
    p = Project()
    assert p.__json__() == {"name": p.name, "project_id": p.id, "temporary": False, "path": None}


def test_addVM(async_run):
    hypervisor = MagicMock()
    project = Project()
    vm = async_run(project.addVM(hypervisor, None, name="test", vm_type="vpcs", properties={"startup_config": "test.cfg"}))
    hypervisor.post.assert_called_with('/projects/{}/vpcs/vms'.format(project.id),
                                       data={'console': None,
                                             'vm_id': vm.id,
                                             'console_type': 'telnet',
                                             'startup_config': 'test.cfg',
                                             'name': 'test'})


def test_getVM(async_run):
    hypervisor = MagicMock()
    project = Project()
    vm = async_run(project.addVM(hypervisor, None, name="test", vm_type="vpcs", properties={"startup_config": "test.cfg"}))
    assert project.getVM(vm.id) == vm

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.getVM("test")


def test_addLink(async_run):
    hypervisor = MagicMock()
    project = Project()
    vm1 = async_run(project.addVM(hypervisor, None, name="test1", vm_type="vpcs", properties={"startup_config": "test.cfg"}))
    vm2 = async_run(project.addVM(hypervisor, None, name="test2", vm_type="vpcs", properties={"startup_config": "test.cfg"}))
    link = async_run(project.addLink())
    async_run(link.addVM(vm1, 3, 1))
    async_run(link.addVM(vm2, 4, 2))
    assert len(link._vms) == 2


def test_getLink(async_run):
    hypervisor = MagicMock()
    project = Project()
    link = async_run(project.addLink())
    assert project.getLink(link.id) == link

    with pytest.raises(aiohttp.web_exceptions.HTTPNotFound):
        project.getLink("test")
