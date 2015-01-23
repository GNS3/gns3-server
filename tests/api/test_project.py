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

"""
This test suite check /project endpoint
"""

import uuid
from tests.utils import asyncio_patch


def test_create_project_with_dir(server, tmpdir):
    response = server.post("/project", {"location": str(tmpdir)})
    assert response.status == 200
    assert response.json["location"] == str(tmpdir)


def test_create_project_without_dir(server):
    query = {}
    response = server.post("/project", query)
    assert response.status == 200
    assert response.json["uuid"] is not None
    assert response.json["temporary"] is False


def test_create_temporary_project(server):
    query = {"temporary": True}
    response = server.post("/project", query)
    assert response.status == 200
    assert response.json["uuid"] is not None
    assert response.json["temporary"] is True


def test_create_project_with_uuid(server):
    query = {"uuid": "00010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = server.post("/project", query)
    assert response.status == 200
    assert response.json["uuid"] == "00010203-0405-0607-0809-0a0b0c0d0e0f"


def test_create_project_with_uuid(server):
    query = {"uuid": "00010203-0405-0607-0809-0a0b0c0d0e0f", "location": "/tmp"}
    response = server.post("/project", query, example=True)
    assert response.status == 200
    assert response.json["uuid"] == "00010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["location"] == "/tmp"


def test_show_project(server):
    query = {"uuid": "00010203-0405-0607-0809-0a0b0c0d0e0f", "location": "/tmp", "temporary": False}
    response = server.post("/project", query)
    assert response.status == 200
    response = server.get("/project/00010203-0405-0607-0809-0a0b0c0d0e0f")
    assert response.json == query


def test_show_project_invalid_uuid(server):
    response = server.get("/project/00010203-0405-0607-0809-0a0b0c0d0e42")
    assert response.status == 404


def test_update_temporary_project(server):
    query = {"temporary": True}
    response = server.post("/project", query)
    assert response.status == 200
    query = {"temporary": False}
    response = server.put("/project/{uuid}".format(uuid=response.json["uuid"]), query)
    assert response.status == 200
    assert response.json["temporary"] is False


def test_commit_project(server, project):
    with asyncio_patch("gns3server.modules.project.Project.commit", return_value=True) as mock:
        response = server.post("/project/{uuid}/commit".format(uuid=project.uuid), example=True)
    assert response.status == 204
    assert mock.called


def test_commit_project_invalid_project_uuid(server, project):
    response = server.post("/project/{uuid}/commit".format(uuid=uuid.uuid4()))
    assert response.status == 404


def test_delete_project(server, project):
    with asyncio_patch("gns3server.modules.project.Project.delete", return_value=True) as mock:
        response = server.delete("/project/{uuid}".format(uuid=project.uuid), example=True)
        assert response.status == 204
        assert mock.called


def test_delete_project_invalid_uuid(server, project):
    response = server.delete("/project/{uuid}".format(uuid=uuid.uuid4()))
    assert response.status == 404


def test_close_project(server, project):
    with asyncio_patch("gns3server.modules.project.Project.close", return_value=True) as mock:
        response = server.post("/project/{uuid}/close".format(uuid=project.uuid), example=True)
        assert response.status == 204
        assert mock.called


def test_close_project_invalid_uuid(server, project):
    response = server.post("/project/{uuid}/close".format(uuid=uuid.uuid4()))
    assert response.status == 404
