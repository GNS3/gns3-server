#!/usr/bin/env python
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

import asyncio
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.controller import Controller
from gns3server.schemas.controller.computes import Compute

pytestmark = pytest.mark.asyncio

from tests.utils import AsyncioMagicMock, asyncio_patch


class TestComputeRoutes:
    async def test_compute_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 84, "user": "julien", "password": "secure"}

        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["compute_id"] is not None

        del params["password"]
        for param, value in params.items():
            assert response.json()[param] == value

    async def test_compute_create_with_id(self, app: FastAPI, client: AsyncClient) -> None:

        compute_id = str(uuid.uuid4())
        params = {
            "compute_id": compute_id,
            "protocol": "http",
            "host": "127.0.0.1",
            "port": 84,
            "user": "julien",
            "password": "secure",
        }

        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["compute_id"] == compute_id

        del params["password"]
        for param, value in params.items():
            assert response.json()[param] == value

    async def test_compute_list(self, app: FastAPI, client: AsyncClient, test_compute: Compute) -> None:

        response = await client.get(app.url_path_for("get_computes"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) > 0

    async def test_compute_list_filter_by_name(self, app: FastAPI, client: AsyncClient) -> None:

        for name, port in (("compute-a", 85), ("compute-b", 86)):
            params = {
                "name": name,
                "protocol": "http",
                "host": "localhost",
                "port": port,
                "user": "julien",
                "password": "secure",
            }
            response = await client.post(app.url_path_for("create_compute"), json=params)
            assert response.status_code == status.HTTP_201_CREATED

        response = await client.get(app.url_path_for("get_computes"), params={"name": "compute-a"})
        assert response.status_code == status.HTTP_200_OK
        assert [c["name"] for c in response.json()] == ["compute-a"]

        response = await client.get(app.url_path_for("get_computes"), params={"name": "COMPUTE-A"})
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        response = await client.get(app.url_path_for("get_computes"))
        assert len(response.json()) >= 2

    async def test_compute_get(self, app: FastAPI, client: AsyncClient, test_compute: Compute) -> None:

        response = await client.get(app.url_path_for("get_compute", compute_id=test_compute.compute_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["compute_id"] == str(test_compute.compute_id)

    async def test_compute_get_reports_every_capability(self, app: FastAPI, client: AsyncClient, controller) -> None:
        """
        The capabilities payload the compute reports must survive the
        response model intact. The local compute is the interesting one: it
        is the controller object serialized straight through, and a second,
        private Capabilities definition in the response schema silently
        stripped the kernel-datapath fields (ubridge_tap, ubridge_iol_tap)
        there — links were then built on a datapath clients could not see.
        """

        await controller.add_compute(
            compute_id="local", name="local", host="127.0.0.1", port=3080, force=True, connect=False
        )
        controller.get_compute("local")._capabilities.update(
            {
                "version": "3.1.0",
                "node_types": ["docker"],
                "platform": "linux",
                "cpus": 4,
                "memory": 1024,
                "disk_size": 2048,
                "ubridge_tc": {"netem": ["delay"], "ebpf": True, "ebpf_modes": ["nth"], "cbpf": True},
                "ubridge_tap": True,
                "ubridge_iol_tap": False,
            }
        )

        response = await client.get(app.url_path_for("get_compute", compute_id="local"))
        assert response.status_code == status.HTTP_200_OK
        capabilities = response.json()["capabilities"]
        assert capabilities["ubridge_tap"] is True
        assert capabilities["ubridge_iol_tap"] is False
        assert capabilities["ubridge_tc"]["netem"] == ["delay"]

    async def test_compute_get_local(self, app: FastAPI, client: AsyncClient, controller) -> None:

        await controller.add_compute(
            compute_id="local", name="local", host="127.0.0.1", port=3080, force=True, connect=False
        )

        response = await client.get(app.url_path_for("get_compute", compute_id="local"))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["compute_id"] == "local"
        assert response.json()["name"] == "local"

    async def test_compute_update(self, app: FastAPI, client: AsyncClient, test_compute: Compute) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 42, "user": "julien", "password": "secure"}

        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        params["protocol"] = "https"
        response = await client.put(app.url_path_for("update_compute", compute_id=compute_id), json=params)
        assert response.status_code == status.HTTP_200_OK

        del params["password"]
        for param, value in params.items():
            assert response.json()[param] == value

    async def test_compute_delete(self, app: FastAPI, client: AsyncClient, test_compute: Compute) -> None:

        response = await client.delete(app.url_path_for("delete_compute", compute_id=test_compute.compute_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestComputeFeatures:
    async def test_compute_list_docker_images(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 84, "user": "julien", "password": "secure"}

        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        with asyncio_patch(
            "gns3server.controller.compute.Compute.forward", return_value=[{"image": "docker1"}, {"image": "docker2"}]
        ) as mock:
            response = await client.get(app.url_path_for("docker_get_images", compute_id=compute_id))
            mock.assert_called_with("GET", "docker", "images")
            assert response.json() == [{"image": "docker1"}, {"image": "docker2"}]

    async def test_compute_pull_docker_image(self, app: FastAPI, client: AsyncClient, test_compute: Compute) -> None:

        compute = MagicMock()
        compute.forward = AsyncioMagicMock(return_value={})
        with patch("gns3server.api.routes.controller.computes.Controller.instance") as controller:
            controller.return_value.get_compute.return_value = compute
            response = await client.post(
                app.url_path_for("docker_pull_image", compute_id=test_compute.compute_id),
                json={"image": "nginx:latest"},
            )
            compute.forward.assert_called_with("POST", "docker", "images/pull", data={"image": "nginx:latest"})
            assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_compute_list_virtualbox_vms(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 4242, "user": "julien", "password": "secure"}
        response = await client.post(app.url_path_for("get_computes"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
            response = await client.get(app.url_path_for("virtualbox_vms", compute_id=compute_id))
            mock.assert_called_with("GET", "virtualbox", "vms")
            assert response.json() == []

    async def test_compute_list_vmware_vms(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 4243, "user": "julien", "password": "secure"}
        response = await client.post(app.url_path_for("get_computes"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
            response = await client.get(app.url_path_for("vmware_vms", compute_id=compute_id))
            mock.assert_called_with("GET", "vmware", "vms")
            assert response.json() == []

    # async def test_compute_create_img(self, app: FastAPI, client: AsyncClient) -> None:
    #
    #     params = {
    #         "protocol": "http",
    #         "host": "localhost",
    #         "port": 4284,
    #         "user": "julien",
    #         "password": "secure"
    #     }
    #
    #     response = await client.post(app.url_path_for("get_computes"), json=params)
    #     assert response.status_code == status.HTTP_201_CREATED
    #     compute_id = response.json()["compute_id"]
    #
    #     params = {"path": "/test"}
    #     with asyncio_patch("gns3server.controller.compute.Compute.forward", return_value=[]) as mock:
    #         response = await client.post(app.url_path_for("get_compute", compute_id=compute_id) + "/qemu/img", json=params)
    #         assert response.json() == []
    #         mock.assert_called_with("POST", "qemu", "img", data=unittest.mock.ANY)

    # async def test_compute_autoidlepc(self, app: FastAPI, client: AsyncClient) -> None:
    #
    #     params = {
    #         "protocol": "http",
    #         "host": "localhost",
    #         "port": 84,
    #         "user": "julien",
    #         "password": "secure"
    #     }
    #
    #     response = await client.post(app.url_path_for("get_computes"), json=params)
    #     assert response.status_code == status.HTTP_201_CREATED
    #     compute_id = response.json()["compute_id"]
    #
    #     params = {
    #         "platform": "c7200",
    #         "image": "test.bin",
    #         "ram": 512
    #     }
    #
    #     with asyncio_patch("gns3server.controller.Controller.autoidlepc", return_value={"idlepc": "0x606de20c"}) as mock:
    #         response = await client.post(app.url_path_for("autoidlepc", compute_id=compute_id) + "/auto_idlepc", json=params)
    #         assert mock.called
    #         assert response.status_code == status.HTTP_200_OK


class TestComputeAutoConnect:
    async def test_compute_create_with_auto_connect(self, app: FastAPI, client: AsyncClient) -> None:

        params = {
            "protocol": "http",
            "host": "localhost",
            "port": 84,
            "user": "julien",
            "password": "secure",
            "auto_connect": True,
        }

        with patch("gns3server.controller.compute.Compute.connect", new_callable=AsyncioMagicMock) as connect_mock:
            response = await client.post(app.url_path_for("create_compute"), json=params)
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["auto_connect"] is True
            # the create request returns immediately, the connection happens
            # in the background
            await asyncio.sleep(0)
            assert connect_mock.call_count == 1

        # persisted, not just echoed back
        compute_id = response.json()["compute_id"]
        response = await client.get(app.url_path_for("get_compute", compute_id=compute_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["auto_connect"] is True

    async def test_compute_create_auto_connect_defaults_to_false(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 85, "user": "julien", "password": "secure"}

        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["auto_connect"] is False

    async def test_compute_update_enable_auto_connect_connects(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 86, "name": "auto-connect-target"}
        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        with patch("gns3server.controller.compute.Compute.connect", new_callable=AsyncioMagicMock) as connect_mock:
            response = await client.put(
                app.url_path_for("update_compute", compute_id=compute_id), json={"auto_connect": True}
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["auto_connect"] is True
            await asyncio.sleep(0)  # give the background connection task a tick
            assert connect_mock.call_count == 1

            # saving the same value again must not reconnect: a manual
            # disconnect has to survive an unrelated edit of the compute
            response = await client.put(
                app.url_path_for("update_compute", compute_id=compute_id), json={"auto_connect": True}
            )
            assert response.status_code == status.HTTP_200_OK
            await asyncio.sleep(0)
            assert connect_mock.call_count == 1

    async def test_compute_update_preserves_auto_connect(self, app: FastAPI, client: AsyncClient) -> None:

        params = {
            "protocol": "http",
            "host": "localhost",
            "port": 87,
            "user": "julien",
            "password": "secure",
            "auto_connect": True,
        }
        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        response = await client.put(app.url_path_for("update_compute", compute_id=compute_id), json={"name": "renamed"})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "renamed"

        response = await client.get(app.url_path_for("get_compute", compute_id=compute_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["auto_connect"] is True


class TestComputeDisconnect:
    async def test_compute_disconnect(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 88, "user": "julien", "password": "secure"}
        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        compute = Controller.instance().get_compute(compute_id)
        compute._connected = True

        response = await client.post(app.url_path_for("disconnect_compute", compute_id=compute_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert compute._manual_disconnect is True
        assert compute.connected is False

    async def test_compute_disconnect_in_use_rejected(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 89, "user": "julien", "password": "secure"}
        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        compute = Controller.instance().get_compute(compute_id)
        compute._connected = True

        open_project = MagicMock()
        open_project.name = "project-using-the-compute"
        with patch("gns3server.controller.Controller.get_compute_open_projects", return_value=[open_project]):
            response = await client.post(app.url_path_for("disconnect_compute", compute_id=compute_id))
        assert response.status_code == status.HTTP_409_CONFLICT
        # the offending project names are reported to the client
        assert "project-using-the-compute" in response.json()["message"]
        # the compute is left untouched
        assert compute._manual_disconnect is False
        assert compute.connected is True

    async def test_compute_disconnect_in_use_forced(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"protocol": "http", "host": "localhost", "port": 90, "user": "julien", "password": "secure"}
        response = await client.post(app.url_path_for("create_compute"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        compute_id = response.json()["compute_id"]

        compute = Controller.instance().get_compute(compute_id)
        compute._connected = True

        with patch("gns3server.controller.Controller.get_compute_open_projects", return_value=[MagicMock()]):
            response = await client.post(
                app.url_path_for("disconnect_compute", compute_id=compute_id), params={"force": True}
            )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert compute._manual_disconnect is True
        assert compute.connected is False

    async def test_compute_disconnect_local_rejected(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.post(app.url_path_for("disconnect_compute", compute_id="local"))
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_compute_disconnect_unknown(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.post(app.url_path_for("disconnect_compute", compute_id=str(uuid.uuid4())))
        assert response.status_code == status.HTTP_404_NOT_FOUND
