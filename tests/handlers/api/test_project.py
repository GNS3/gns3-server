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
import os
from unittest.mock import patch
from tests.utils import asyncio_patch


def test_create_project_with_path(server, tmpdir):
    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        response = server.post("/projects", {"name": "test", "path": str(tmpdir)})
        assert response.status == 201
        assert response.json["path"] == str(tmpdir)
        assert response.json["name"] == "test"


def test_create_project_without_dir(server):
    query = {"name": "test"}
    response = server.post("/projects", query, example=True)
    assert response.status == 201
    assert response.json["project_id"] is not None
    assert response.json["temporary"] is False
    assert response.json["name"] == "test"


def test_create_temporary_project(server):
    query = {"name": "test", "temporary": True}
    response = server.post("/projects", query)
    assert response.status == 201
    assert response.json["project_id"] is not None
    assert response.json["temporary"] is True
    assert response.json["name"] == "test"


def test_create_project_with_uuid(server):
    query = {"name": "test", "project_id": "00010203-0405-0607-0809-0a0b0c0d0e0f"}
    response = server.post("/projects", query)
    assert response.status == 201
    assert response.json["project_id"] == "00010203-0405-0607-0809-0a0b0c0d0e0f"
    assert response.json["name"] == "test"


def test_show_project(server):
    query = {"name": "test", "project_id": "00010203-0405-0607-0809-0a0b0c0d0e02", "temporary": False}
    response = server.post("/projects", query)
    assert response.status == 201
    response = server.get("/projects/00010203-0405-0607-0809-0a0b0c0d0e02", example=True)
    assert len(response.json.keys()) == 5
    assert len(response.json["location"]) > 0
    assert response.json["project_id"] == "00010203-0405-0607-0809-0a0b0c0d0e02"
    assert response.json["temporary"] is False
    assert response.json["name"] == "test"


def test_show_project_invalid_uuid(server):
    response = server.get("/projects/00010203-0405-0607-0809-0a0b0c0d0e42")
    assert response.status == 404


def test_update_temporary_project(server):
    query = {"name": "test", "temporary": True}
    response = server.post("/projects", query)
    assert response.status == 201
    query = {"name": "test", "temporary": False}
    response = server.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
    assert response.status == 200
    assert response.json["temporary"] is False


def test_update_path_project_temporary(server, tmpdir):

    os.makedirs(str(tmpdir / "a"))
    os.makedirs(str(tmpdir / "b"))

    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        response = server.post("/projects", {"name": "first_name", "path": str(tmpdir / "a"), "temporary": True})
        assert response.status == 201
        assert response.json["name"] == "first_name"
        query = {"name": "second_name", "path": str(tmpdir / "b")}
        response = server.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
        assert response.status == 200
        assert response.json["path"] == str(tmpdir / "b")
        assert response.json["name"] == "second_name"

        assert not os.path.exists(str(tmpdir / "a"))
        assert os.path.exists(str(tmpdir / "b"))


def test_update_path_project_non_temporary(server, tmpdir):

    os.makedirs(str(tmpdir / "a"))
    os.makedirs(str(tmpdir / "b"))

    with patch("gns3server.modules.project.Project.is_local", return_value=True):
        response = server.post("/projects", {"name": "first_name", "path": str(tmpdir / "a")})
        assert response.status == 201
        assert response.json["name"] == "first_name"
        query = {"name": "second_name", "path": str(tmpdir / "b")}
        response = server.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
        assert response.status == 200
        assert response.json["path"] == str(tmpdir / "b")
        assert response.json["name"] == "second_name"

        assert os.path.exists(str(tmpdir / "a"))
        assert os.path.exists(str(tmpdir / "b"))


def test_update_path_project_non_local(server, tmpdir):

    with patch("gns3server.modules.project.Project.is_local", return_value=False):
        response = server.post("/projects", {"name": "first_name"})
        assert response.status == 201
        query = {"name": "second_name", "path": str(tmpdir)}
        response = server.put("/projects/{project_id}".format(project_id=response.json["project_id"]), query, example=True)
        assert response.status == 403


def test_commit_project(server, project):
    with asyncio_patch("gns3server.modules.project.Project.commit", return_value=True) as mock:
        response = server.post("/projects/{project_id}/commit".format(project_id=project.id), example=True)
    assert response.status == 204
    assert mock.called


def test_commit_project_invalid_uuid(server):
    response = server.post("/projects/{project_id}/commit".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_delete_project(server, project):
    with asyncio_patch("gns3server.modules.project.Project.delete", return_value=True) as mock:
        response = server.delete("/projects/{project_id}".format(project_id=project.id), example=True)
        assert response.status == 204
        assert mock.called


def test_delete_project_invalid_uuid(server):
    response = server.delete("/projects/{project_id}".format(project_id=uuid.uuid4()))
    assert response.status == 404


def test_close_project(server, project):
    with asyncio_patch("gns3server.modules.project.Project.close", return_value=True) as mock:
        response = server.post("/projects/{project_id}/close".format(project_id=project.id), example=True)
        assert response.status == 204
        assert mock.called


def test_close_project_invalid_uuid(server):
    response = server.post("/projects/{project_id}/close".format(project_id=uuid.uuid4()))
    assert response.status == 404
