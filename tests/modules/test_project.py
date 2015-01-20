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
from gns3server.modules.project import Project


def test_affect_uuid():
    p = Project()
    assert len(p.uuid) == 36

    p = Project(uuid='00010203-0405-0607-0809-0a0b0c0d0e0f')
    assert p.uuid == '00010203-0405-0607-0809-0a0b0c0d0e0f'


def test_path(tmpdir):
    p = Project(location=str(tmpdir))
    assert p.path == os.path.join(str(tmpdir), p.uuid)
    assert os.path.exists(os.path.join(str(tmpdir), p.uuid))
    assert os.path.exists(os.path.join(str(tmpdir), p.uuid, 'files'))


def test_temporary_path():
    p = Project()
    assert os.path.exists(p.path)


def test_json(tmpdir):
    p = Project()
    assert p.__json__() == {"location": p.location, "uuid": p.uuid}
