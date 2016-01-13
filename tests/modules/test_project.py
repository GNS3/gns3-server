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
from uuid import uuid4
from unittest.mock import patch

from tests.utils import asyncio_patch
from gns3server.modules.project import Project
from gns3server.modules.vpcs import VPCS, VPCSVM


@pytest.fixture(scope="module")
def manager(port_manager):
    m = VPCS.instance()
    m.port_manager = port_manager
    return m


@pytest.fixture(scope="function")
def vm(project, manager, loop):
    vm = manager.create_vm("test", project.id, "00010203-0405-0607-0809-0a0b0c0d0e0f")
    return loop.run_until_complete(asyncio.async(vm))


def test_affect_uuid():
    p = Project()
    assert len(p.id) == 36

    p = Project(project_id='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert p.id == '00010203-0405-0607-0809-0a0b0c0d0e0f'


def test_path(tmpdir):
    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        p = Project(location=str(tmpdir))
        assert p.path == os.path.join(str(tmpdir), p.id)
        assert os.path.exists(os.path.join(str(tmpdir), p.id))
        assert not os.path.exists(os.path.join(p.path, ".gns3_temporary"))


def test_init_path(tmpdir):

    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        p = Project(path=str(tmpdir))
        assert p.path == str(tmpdir)


def test_changing_path_temporary_flag(tmpdir):

    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        p = Project(temporary=True)
        assert os.path.exists(p.path)
        original_path = p.path
        assert os.path.exists(os.path.join(p.path, ".gns3_temporary"))

        p.path = str(tmpdir)


def test_temporary_path():
    p = Project(temporary=True)
    assert os.path.exists(p.path)
    assert os.path.exists(os.path.join(p.path, ".gns3_temporary"))


def test_remove_temporary_flag():
    p = Project(temporary=True)
    assert os.path.exists(p.path)
    assert os.path.exists(os.path.join(p.path, ".gns3_temporary"))
    p.temporary = False
    assert not os.path.exists(os.path.join(p.path, ".gns3_temporary"))


def test_changing_location_not_allowed(tmpdir):
    with patch("gns3server.modules.project.Project.is_local", return_value=False):
        with pytest.raises(aiohttp.web.HTTPForbidden):
            p = Project(location=str(tmpdir))


def test_changing_path_not_allowed(tmpdir):
    with patch("gns3server.modules.project.Project.is_local", return_value=False):
        with pytest.raises(aiohttp.web.HTTPForbidden):
            p = Project()
            p.path = str(tmpdir)


def test_json(tmpdir):
    p = Project()
    assert p.__json__() == {"name": p.name, "location": p.location, "path": p.path, "project_id": p.id, "temporary": False}


def test_vm_working_directory(tmpdir, vm):
    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        p = Project(location=str(tmpdir))
        assert p.vm_working_directory(vm) == os.path.join(str(tmpdir), p.id, 'project-files', vm.module_name, vm.id)
        assert os.path.exists(p.vm_working_directory(vm))


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


def test_commit_permission_issue(manager, loop):
    project = Project()
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    project.add_vm(vm)
    directory = project.vm_working_directory(vm)
    project.mark_vm_for_destruction(vm)
    assert len(project._vms_to_destroy) == 1
    assert os.path.exists(directory)
    os.chmod(directory, 0)
    with pytest.raises(aiohttp.web.HTTPInternalServerError):
        loop.run_until_complete(asyncio.async(project.commit()))
    os.chmod(directory, 700)


def test_project_delete(loop):
    project = Project()
    directory = project.path
    assert os.path.exists(directory)
    loop.run_until_complete(asyncio.async(project.delete()))
    assert os.path.exists(directory) is False


def test_project_delete_permission_issue(loop):
    project = Project()
    directory = project.path
    assert os.path.exists(directory)
    os.chmod(directory, 0)
    with pytest.raises(aiohttp.web.HTTPInternalServerError):
        loop.run_until_complete(asyncio.async(project.delete()))
    os.chmod(directory, 700)


def test_project_add_vm(manager):
    project = Project()
    vm = VPCSVM("test", "00010203-0405-0607-0809-0a0b0c0d0e0f", project, manager)
    project.add_vm(vm)
    assert len(project.vms) == 1


def test_project_close(loop, vm, project):

    with asyncio_patch("gns3server.modules.vpcs.vpcs_vm.VPCSVM.close") as mock:
        loop.run_until_complete(asyncio.async(project.close()))
        assert mock.called
    assert vm.id not in vm.manager._vms


def test_project_close_temporary_project(loop, manager):
    """A temporary project is deleted when closed"""

    project = Project(temporary=True)
    directory = project.path
    assert os.path.exists(directory)
    loop.run_until_complete(asyncio.async(project.close()))
    assert os.path.exists(directory) is False


def test_get_default_project_directory(monkeypatch):

    monkeypatch.undo()
    project = Project()
    path = os.path.normpath(os.path.expanduser("~/GNS3/projects"))
    assert project._get_default_project_directory() == path
    assert os.path.exists(path)


def test_clean_project_directory(tmpdir):

    # A non anonymous project with uuid.
    project1 = tmpdir / uuid4()
    project1.mkdir()

    # A non anonymous project.
    oldproject = tmpdir / uuid4()
    oldproject.mkdir()

    # an anonymous project
    project2 = tmpdir / uuid4()
    project2.mkdir()
    tmp = (project2 / ".gns3_temporary")
    with open(str(tmp), 'w+') as f:
        f.write("1")

    with patch("gns3server.config.Config.get_section_config", return_value={"project_directory": str(tmpdir)}):
        Project.clean_project_directory()

    assert os.path.exists(str(project1))
    assert os.path.exists(str(oldproject))
    assert not os.path.exists(str(project2))


def test_list_files(tmpdir, loop):

    with patch("gns3server.config.Config.get_section_config", return_value={"project_directory": str(tmpdir)}):
        project = Project()
        path = project.path
        os.makedirs(os.path.join(path, "vm-1", "dynamips"))
        with open(os.path.join(path, "vm-1", "dynamips", "test.bin"), "w+") as f:
            f.write("test")
        open(os.path.join(path, "vm-1", "dynamips", "test.ghost"), "w+").close()
        with open(os.path.join(path, "test.txt"), "w+") as f:
            f.write("test2")

        files = loop.run_until_complete(asyncio.async(project.list_files()))

        assert files == [
            {
                "path": "test.txt",
                "md5sum": "ad0234829205b9033196ba818f7a872b"
            },
            {
                "path": os.path.join("vm-1", "dynamips", "test.bin"),
                "md5sum": "098f6bcd4621d373cade4e832627b4f6"
            }
        ]
