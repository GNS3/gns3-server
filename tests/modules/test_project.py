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

import os
import asyncio
import pytest
import aiohttp
from unittest.mock import patch

from gns3server.modules.project import Project
from gns3server.modules.vpcs import VPCS, VPCSVM


@pytest.fixture(scope="module")
def manager(port_manager):
    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager):
    return VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)


def test_affect_uuid():
    p = Project()
    assert len(p.uuid) == 36

    p = Project(uuid='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert p.uuid == '00010203-0405-0607-0809-0a0b0c0d0e0f'


def test_path(tmpdir):
    with patch("gns3server.config.Config.get_section_config", return_value={"local": True}):
        p = Project(location=str(tmpdir))
        assert p.path == os.path.join(str(tmpdir), p.uuid)
        assert os.path.exists(os.path.join(str(tmpdir), p.uuid))
        assert os.path.exists(os.path.join(str(tmpdir), p.uuid, 'vms'))


def test_temporary_path():
    p = Project()
    assert os.path.exists(p.path)


def test_changing_location_not_allowed(tmpdir):
    with patch("gns3server.config.Config.get_section_config", return_value={"local": False}):
        with pytest.raises(aiohttp.web.HTTPForbidden):
            p = Project(location=str(tmpdir))


def test_json(tmpdir):
    p = Project()
    assert p.__json__() == {"location": p.location, "uuid": p.uuid, "temporary": False}


def test_vm_working_directory(tmpdir, vm):
    with patch("gns3server.config.Config.get_section_config", return_value={"local": True}):
        p = Project(location=str(tmpdir))
        assert os.path.exists(p.vm_working_directory(vm))
        assert os.path.exists(os.path.join(str(tmpdir), p.uuid, vm.module_name, vm.uuid))


def test_mark_vm_for_destruction(vm):
    project = Project()
    project.add_vm(vm)
    project.mark_vm_for_destruction(vm)
    assert len(project._vms_to_destroy) == 1
    assert len(project.vms) == 0


def test_commit(manager, loop):
    project = Project()
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    project.add_vm(vm)
    directory = project.vm_working_directory(vm)
    project.mark_vm_for_destruction(vm)
    assert len(project._vms_to_destroy) == 1
    assert os.path.exists(directory)
    loop.run_until_complete(asyncio.async(project.commit()))
    assert len(project._vms_to_destroy) == 0
    assert os.path.exists(directory) is False
    assert len(project.vms) == 0


def test_project_delete(loop):
    project = Project()
    directory = project.path
    assert os.path.exists(directory)
    loop.run_until_complete(asyncio.async(project.delete()))
    assert os.path.exists(directory) is False


def test_project_add_vm(manager):
    project = Project()
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    project.add_vm(vm)
    assert len(project.vms) == 1


def test_project_close(loop, manager):
    project = Project()
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    project.add_vm(vm)
    with patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM.close") as mock:
        loop.run_until_complete(asyncio.async(project.close()))
        assert mock.called


def test_project_close_temporary_project(loop, manager):
    """A temporary project is deleted when closed"""

    project = Project(temporary=True)
    directory = project.path
    assert os.path.exists(directory)
    loop.run_until_complete(asyncio.async(project.close()))
    assert os.path.exists(directory) is False


def test_get_default_project_directory():

    project = Project()
    path = os.path.normpath(os.path.expanduser("~/GNS3/projects"))
    assert project._get_default_project_directory() == path
    assert os.path.exists(path)
