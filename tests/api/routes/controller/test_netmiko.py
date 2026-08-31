#
# Copyright (C) 2020 GNS3 Technologies Inc.
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

from fastapi import FastAPI, status
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestNetmikoRoutes:

    async def test_device_types(self, app: FastAPI, client: AsyncClient) -> None:
        """
        Test listing the device types supported by the installed Netmiko library.
        """

        pytest.importorskip("netmiko", reason="netmiko is not installed")
        import netmiko

        response = await client.get(app.url_path_for("get_netmiko_device_types"))
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["netmiko_version"] == netmiko.__version__

        device_types = data["device_types"]
        assert len(device_types) > 0

        names = [entry["name"] for entry in device_types]
        assert names == sorted(names)

        by_name = {entry["name"]: entry for entry in device_types}
        assert by_name["cisco_ios"]["telnet"] is False
        assert by_name["cisco_ios"]["custom"] is False
        assert by_name["cisco_ios_telnet"]["telnet"] is True

        # '_ssh' aliases and the 'autodetect' pseudo device type are filtered out
        assert not [name for name in names if name.endswith("_ssh")]
        assert "autodetect" not in names

        # GNS3-copilot custom drivers are flagged as custom
        assert by_name["gns3_vpcs_telnet"]["custom"] is True
        assert by_name["gns3_vpcs_telnet"]["telnet"] is True

    async def test_device_types_unavailable(self, app: FastAPI, client: AsyncClient, monkeypatch) -> None:
        """
        Test that a 501 is returned when Netmiko is not installed.
        """

        from gns3server.api.routes.controller import netmiko as netmiko_route

        def _raise_import_error():
            raise ImportError("No module named 'netmiko'")

        monkeypatch.setattr(netmiko_route, "_load_netmiko_device_types", _raise_import_error)
        monkeypatch.setattr(netmiko_route, "_device_types_cache", None)

        response = await client.get(app.url_path_for("get_netmiko_device_types"))
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
        # the HTTP exception handler formats errors with a "message" key
        assert "ai-features" in response.json()["message"]
