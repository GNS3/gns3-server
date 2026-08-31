# -*- coding: utf-8 -*-
#
# Copyright (C) 2026 GNS3 Technologies Inc.
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
import configparser

import pytest

from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.config import Config
from gns3server.schemas.controller.settings import SECRET_MASK
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY

pytestmark = pytest.mark.asyncio


@pytest.fixture
def stable_jwt_secret(config):
    """
    A settings update reloads the configuration, which re-reads the JWT
    secret from <secrets dir>/gns3_jwt_secret_key. Pin it to the default
    key so the class-scoped bearer token stays valid across PUT tests.
    """

    path = os.path.join(os.path.dirname(config._main_config_file), "gns3_jwt_secret_key")
    with open(path, "w") as f:
        f.write(DEFAULT_JWT_SECRET_KEY)
    return path


class TestSettingsRoutes:

    async def test_get_settings(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_server_settings"))
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert sorted(body.keys()) == [
            "Controller", "Dynamips", "IOU", "Qemu", "Server", "VPCS", "WebWireshark"
        ]
        # deprecated sections are not exposed
        assert "VirtualBox" not in body
        assert "VMware" not in body
        # secret managed outside of the configuration file
        assert "jwt_secret_key" not in body["Controller"]
        # secrets are masked (an empty secret serializes as "", it is
        # only generated when the server actually starts)
        assert body["Server"]["compute_password"] in ("", SECRET_MASK)
        assert body["Controller"]["default_admin_password"] in ("", SECRET_MASK)

    async def test_get_settings_unauthorized(self, app: FastAPI, client: AsyncClient) -> None:

        # send an explicit invalid token: the class-scoped clients share the same
        # underlying httpx client and its default headers depend on the fixture
        # instantiation order
        response = await client.get(
            app.url_path_for("get_server_settings"), headers={"Authorization": "Bearer invalid_token"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_settings_forbidden(self, app: FastAPI, client: AsyncClient, test_user) -> None:

        # the "User" role has no Server.Audit privilege
        token = auth_service.create_access_token(test_user.username, secret_key=DEFAULT_JWT_SECRET_KEY)
        response = await client.get(
            app.url_path_for("get_server_settings"), headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_put_settings(self, app: FastAPI, client: AsyncClient, config: Config,
                                stable_jwt_secret: str) -> None:

        response = await client.put(app.url_path_for("update_server_settings"), json={
            "Server": {
                "port": 3081,
                "allowed_interfaces": ["eth0"],
                "default_symbol_theme": "Classic",
                "report_errors": False,
            },
            "Qemu": {
                "enable_monitor": False,
            },
        })
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["Server"]["port"] == 3081
        assert body["Server"]["allowed_interfaces"] == ["eth0"]
        assert body["Server"]["default_symbol_theme"] == "Classic"
        assert body["Server"]["report_errors"] is False
        assert body["Qemu"]["enable_monitor"] is False
        assert "Server.port" in body["restart_required"]
        assert "Server.report_errors" not in body["restart_required"]

        # the configuration file holds the serialized INI values
        parsed = configparser.ConfigParser()
        parsed.read(config._main_config_file)
        assert parsed["Server"]["port"] == "3081"
        assert parsed["Server"]["allowed_interfaces"] == "eth0"
        assert parsed["Server"]["default_symbol_theme"] == "Classic"
        assert parsed["Server"]["report_errors"] == "False"
        assert parsed["Qemu"]["enable_monitor"] == "False"

    async def test_put_settings_preserves_unknown_options(
            self, app: FastAPI, client: AsyncClient, config: Config, stable_jwt_secret: str) -> None:

        with open(config._main_config_file, "w") as f:
            f.write("[Server]\nhost = 127.0.0.1\nfrobnicate = 42\n")

        response = await client.put(app.url_path_for("update_server_settings"), json={"Server": {"port": 3082}})
        assert response.status_code == status.HTTP_200_OK

        parsed = configparser.ConfigParser()
        parsed.read(config._main_config_file)
        assert parsed["Server"]["frobnicate"] == "42"
        assert parsed["Server"]["host"] == "127.0.0.1"

    async def test_put_settings_secrets(
            self, app: FastAPI, client: AsyncClient, config: Config, stable_jwt_secret: str) -> None:

        # masked secret means "unchanged": nothing is written
        response = await client.put(
            app.url_path_for("update_server_settings"), json={"Server": {"compute_password": SECRET_MASK}})
        assert response.status_code == status.HTTP_200_OK
        parsed = configparser.ConfigParser()
        parsed.read(config._main_config_file)
        assert not parsed.has_option("Server", "compute_password")

        # empty string means "unchanged" too
        response = await client.put(
            app.url_path_for("update_server_settings"), json={"Server": {"compute_password": ""}})
        assert response.status_code == status.HTTP_200_OK
        parsed = configparser.ConfigParser()
        parsed.read(config._main_config_file)
        assert not parsed.has_option("Server", "compute_password")

        # an explicit new value is written in clear text (like a hand-edited file)
        response = await client.put(
            app.url_path_for("update_server_settings"), json={"Server": {"compute_password": "secret123"}})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["Server"]["compute_password"] == SECRET_MASK  # masked in the response
        parsed = configparser.ConfigParser()
        parsed.read(config._main_config_file)
        assert parsed["Server"]["compute_password"] == "secret123"

    async def test_put_settings_null_removes_option(
            self, app: FastAPI, client: AsyncClient, config: Config, stable_jwt_secret: str) -> None:

        with open(config._main_config_file, "w") as f:
            f.write("[Server]\nhost = 127.0.0.1\n")

        response = await client.put(app.url_path_for("update_server_settings"), json={"Server": {"host": None}})
        assert response.status_code == status.HTTP_200_OK

        parsed = configparser.ConfigParser()
        parsed.read(config._main_config_file)
        assert not parsed.has_option("Server", "host")
        assert response.json()["Server"]["host"] == "0.0.0.0"  # default restored

    async def test_put_settings_validation_failure(
            self, app: FastAPI, client: AsyncClient, config: Config, stable_jwt_secret: str) -> None:

        with open(config._main_config_file, "w") as f:
            f.write("[Server]\nhost = 127.0.0.1\n")
        with open(config._main_config_file) as f:
            content_before = f.read()

        # cross-field violation: console_end_port_range must be > console_start_port_range
        response = await client.put(app.url_path_for("update_server_settings"), json={
            "Server": {"console_start_port_range": 10000, "console_end_port_range": 5000}})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        with open(config._main_config_file) as f:
            assert f.read() == content_before

    async def test_put_settings_unknown_option_rejected(
            self, app: FastAPI, client: AsyncClient, stable_jwt_secret: str) -> None:

        response = await client.put(
            app.url_path_for("update_server_settings"), json={"Server": {"prot": "http"}})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_put_settings_deprecated_sections_rejected(
            self, app: FastAPI, client: AsyncClient, stable_jwt_secret: str) -> None:

        response = await client.put(app.url_path_for("update_server_settings"), json={"VirtualBox": {}})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        response = await client.put(app.url_path_for("update_server_settings"), json={"VMware": {}})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_put_settings_jwt_secret_key_rejected(
            self, app: FastAPI, client: AsyncClient, stable_jwt_secret: str) -> None:

        response = await client.put(
            app.url_path_for("update_server_settings"), json={"Controller": {"jwt_secret_key": "nope"}})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_put_settings_conflict(
            self, app: FastAPI, client: AsyncClient, config: Config, stable_jwt_secret: str, tmpdir) -> None:

        override_path = str(tmpdir / "override.conf")
        with open(override_path, "w") as f:
            f.write("[Server]\nhost = 10.0.0.1\n")
        # a later configuration file takes precedence over the main one
        Config.instance()._files.append(override_path)

        response = await client.put(app.url_path_for("update_server_settings"), json={"Server": {"host": "192.168.1.1"}})
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_put_settings_empty_body(self, app: FastAPI, client: AsyncClient, config: Config) -> None:

        response = await client.put(app.url_path_for("update_server_settings"), json={})
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["restart_required"] == []
        assert body["Server"]["host"]  # current values are returned
