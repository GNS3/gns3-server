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

import os
import pytest
import uuid
import unittest.mock

from pathlib import Path
from fastapi import FastAPI, status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.utils import asyncio_patch
from gns3server.db.repositories.images import ImagesRepository
from gns3server.db.repositories.templates import TemplatesRepository
from gns3server.controller import Controller
from gns3server.controller import Config
from gns3server.services.templates import BUILTIN_TEMPLATES

pytestmark = pytest.mark.asyncio


class TestTemplateRoutes:

    async def test_route_exist(self, app: FastAPI, client: AsyncClient) -> None:

        new_template = {"base_script_file": "vpcs_base_config.txt",
                        "category": "guest",
                        "console_auto_start": False,
                        "console_type": "telnet",
                        "default_name_format": "PC{0}",
                        "name": "VPCS_TEST",
                        "compute_id": "local",
                        "symbol": ":/symbols/vpcs_guest.svg",
                        "template_type": "vpcs"}

        response = await client.post(app.url_path_for("create_template"), json=new_template)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["template_id"] is not None

    async def test_template_list(self, app: FastAPI, client: AsyncClient) -> None:

        response = await client.get(app.url_path_for("get_templates"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) > 0

    async def test_template_get(self, app: FastAPI, client: AsyncClient) -> None:

        template_id = str(uuid.uuid4())
        params = {"template_id": template_id,
                  "name": "VPCS_TEST",
                  "version": "1.0",
                  "compute_id": "local",
                  "template_type": "vpcs"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.get(app.url_path_for("get_template", template_id=template_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["template_id"] == template_id

    async def test_template_create_same_name_and_version(
            self,
            app: FastAPI,
            client: AsyncClient,
            controller: Controller
    ) -> None:

        params = {"name": "VPCS_TEST",
                  "version": "1.0",
                  "compute_id": "local",
                  "template_type": "vpcs"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_template_create_wrong_type(self, app: FastAPI, client: AsyncClient, controller: Controller) -> None:

        params = {"name": "VPCS_TEST",
                  "version": "2.0",
                  "compute_id": "local",
                  "template_type": "invalid_template_type"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_template_update(self, app: FastAPI, client: AsyncClient) -> None:

        template_id = str(uuid.uuid4())
        params = {"template_id": template_id,
                  "name": "VPCS_TEST",
                  "version": "3.0",
                  "compute_id": "local",
                  "template_type": "vpcs"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.get(app.url_path_for("get_template", template_id=template_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["template_id"] == template_id

        params = {"name": "VPCS_TEST_RENAMED", "console_auto_start": True}
        response = await client.put(app.url_path_for("update_template", template_id=template_id), json=params)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "VPCS_TEST_RENAMED"

    async def test_template_delete(self, app: FastAPI, client: AsyncClient) -> None:

        template_id = str(uuid.uuid4())
        params = {"template_id": template_id,
                  "name": "VPCS_TEST",
                  "version": "4.0",
                  "compute_id": "local",
                  "template_type": "vpcs"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.delete(app.url_path_for("delete_template", template_id=template_id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_template_delete_with_prune_images(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            tmpdir: str,
    ) -> None:

        path = os.path.join(tmpdir, "test.qcow2")
        with open(path, "wb+") as f:
            f.write(b'\x42\x42\x42\x42')
        images_repo = ImagesRepository(db_session)
        await images_repo.add_image("test.qcow2", "qemu", 42, path, "e342eb86c1229b6c154367a5476969b5", "md5")

        template_id = str(uuid.uuid4())
        params = {"template_id": template_id,
                  "name": "QEMU_TEMPLATE",
                  "compute_id": "local",
                  "hda_disk_image": "test.qcow2",
                  "template_type": "qemu"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.delete(
            app.url_path_for("delete_template", template_id=template_id),
            params={"prune_images": True}
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        images_repo = ImagesRepository(db_session)
        images = await images_repo.get_images()
        assert len(images) == 0

    # async def test_create_node_from_template(self, controller_api, controller, project):
    #
    #     id = str(uuid.uuid4())
    #     controller.template_manager._templates = {id: Template(id, {
    #         "template_type": "qemu",
    #         "category": 0,
    #         "name": "test",
    #         "symbol": "guest.svg",
    #         "default_name_format": "{name}-{0}",
    #         "compute_id": "example.com"
    #     })}
    #     with asyncio_patch("gns3server.controller.project.Project.add_node_from_template", return_value={"name": "test", "node_type": "qemu", "compute_id": "example.com"}) as mock:
    #         response = await client.post("/projects/{}/templates/{}".format(project.id, id), {
    #             "x": 42,
    #             "y": 12
    #         })
    #     mock.assert_called_with(id, x=42, y=12, compute_id=None)
    #     assert response.status_code == status.HTTP_201_CREATED


class TestDuplicateTemplates:

    async def test_template_duplicate(self, app: FastAPI, client: AsyncClient, controller: Controller) -> None:

        template_id = str(uuid.uuid4())
        params = {"template_id": template_id,
                  "name": "VPCS_TEST",
                  "compute_id": "local",
                  "template_type": "vpcs"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post(app.url_path_for("duplicate_template", template_id=template_id))
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["template_id"] != template_id
        params.pop("template_id")
        for param, value in params.items():
            assert response.json()[param] == value

        response = await client.get(app.url_path_for("get_templates"))
        assert len(response.json()) == 9  # includes builtin templates

    async def test_template_duplicate_invalid_template_id(
            self,
            app: FastAPI,
            client: AsyncClient,
            controller: Controller
    ) -> None:

        template_id = str(uuid.uuid4())
        response = await client.post(app.url_path_for("duplicate_template", template_id=template_id))
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBuiltinTemplates:

    async def test_list_builtin_templates(self, app: FastAPI, client: AsyncClient, controller: Controller) -> None:

        response = await client.get(app.url_path_for("get_templates"))
        assert len(response.json()) == 7  # there currently are 7 built-in templates

    async def test_get_builtin_template(self, app: FastAPI, client: AsyncClient, controller: Controller) -> None:

        template_id = str(BUILTIN_TEMPLATES[0]["template_id"])  # take the first built-in template
        response = await client.get(app.url_path_for("get_template", template_id=template_id))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["template_id"] == template_id

    async def test_update_builtin_template(self, app: FastAPI, client: AsyncClient, controller: Controller) -> None:

        template_id = str(BUILTIN_TEMPLATES[0]["template_id"])  # take the first built-in template
        params = {"name": "RENAME_BUILTIN_TEMPLATE"}
        response = await client.put(app.url_path_for("update_template", template_id=template_id), json=params)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_duplicate_builtin_template(self, app: FastAPI, client: AsyncClient, controller: Controller) -> None:

        template_id = str(BUILTIN_TEMPLATES[0]["template_id"])  # take the first built-in template
        response = await client.post(app.url_path_for("duplicate_template", template_id=template_id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_delete_builtin_template(self, app: FastAPI, client: AsyncClient, controller: Controller) -> None:

        template_id = str(BUILTIN_TEMPLATES[0]["template_id"])  # take the first built-in template
        response = await client.delete(app.url_path_for("delete_template", template_id=template_id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_list_builtin_templates_not_enabled(
            self,
            app: FastAPI,
            client: AsyncClient,
            controller: Controller
    ) -> None:

        config = Config.instance()
        config.settings.Server.enable_builtin_templates = False
        response = await client.get(app.url_path_for("get_templates"))
        assert not response.json()


class TestDynamipsTemplate:

    async def test_c7200_dynamips_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c7200 template",
                  "platform": "c7200",
                  "compute_id": "local",
                  "image": "c7200-adventerprisek9-mz.124-24.T5.image",
                  "template_type": "dynamips"}

        with asyncio_patch("gns3server.services.templates.TemplatesService._find_images", return_value=[]) as mock:
            response = await client.post(app.url_path_for("create_template"), json=params)
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["template_id"] is not None

            expected_response = {"template_type": "dynamips",
                                 "auto_delete_disks": False,
                                 "builtin": False,
                                 "category": "router",
                                 "compute_id": "local",
                                 "console_auto_start": False,
                                 "console_type": "telnet",
                                 "default_name_format": "R{0}",
                                 "disk0": 0,
                                 "disk1": 0,
                                 "exec_area": 64,
                                 "idlemax": 500,
                                 "idlepc": "",
                                 "idlesleep": 30,
                                 "image": "c7200-adventerprisek9-mz.124-24.T5.image",
                                 "mac_addr": "",
                                 "midplane": "vxr",
                                 "mmap": True,
                                 "name": "Cisco c7200 template",
                                 "npe": "npe-400",
                                 "nvram": 512,
                                 "platform": "c7200",
                                 "private_config": "",
                                 "ram": 512,
                                 "sparsemem": True,
                                 "startup_config": "ios_base_startup-config.txt",
                                 "symbol": unittest.mock.ANY,
                                 "system_id": "FTX0945W0MY"}

            for item, value in expected_response.items():
                assert response.json().get(item) == value

    async def test_c3745_dynamips_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c3745 template",
                  "platform": "c3745",
                  "compute_id": "local",
                  "image": "c3745-adventerprisek9-mz.124-25d.image",
                  "template_type": "dynamips"}

        with asyncio_patch("gns3server.services.templates.TemplatesService._find_images", return_value=[]) as mock:
            response = await client.post(app.url_path_for("create_template"), json=params)
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["template_id"] is not None

            expected_response = {"template_type": "dynamips",
                                 "auto_delete_disks": False,
                                 "builtin": False,
                                 "category": "router",
                                 "compute_id": "local",
                                 "console_auto_start": False,
                                 "console_type": "telnet",
                                 "default_name_format": "R{0}",
                                 "disk0": 0,
                                 "disk1": 0,
                                 "exec_area": 64,
                                 "idlemax": 500,
                                 "idlepc": "",
                                 "idlesleep": 30,
                                 "image": "c3745-adventerprisek9-mz.124-25d.image",
                                 "mac_addr": "",
                                 "mmap": True,
                                 "name": "Cisco c3745 template",
                                 "iomem": 5,
                                 "nvram": 256,
                                 "platform": "c3745",
                                 "private_config": "",
                                 "ram": 256,
                                 "sparsemem": True,
                                 "startup_config": "ios_base_startup-config.txt",
                                 "symbol": unittest.mock.ANY,
                                 "system_id": "FTX0945W0MY"}

            for item, value in expected_response.items():
                assert response.json().get(item) == value

    async def test_c3725_dynamips_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c3725 template",
                  "platform": "c3725",
                  "compute_id": "local",
                  "image": "c3725-adventerprisek9-mz.124-25d.image",
                  "template_type": "dynamips"}

        with asyncio_patch("gns3server.services.templates.TemplatesService._find_images", return_value=[]) as mock:
            response = await client.post(app.url_path_for("create_template"), json=params)
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["template_id"] is not None

            expected_response = {"template_type": "dynamips",
                                 "auto_delete_disks": False,
                                 "builtin": False,
                                 "category": "router",
                                 "compute_id": "local",
                                 "console_auto_start": False,
                                 "console_type": "telnet",
                                 "default_name_format": "R{0}",
                                 "disk0": 0,
                                 "disk1": 0,
                                 "exec_area": 64,
                                 "idlemax": 500,
                                 "idlepc": "",
                                 "idlesleep": 30,
                                 "image": "c3725-adventerprisek9-mz.124-25d.image",
                                 "mac_addr": "",
                                 "mmap": True,
                                 "name": "Cisco c3725 template",
                                 "iomem": 5,
                                 "nvram": 256,
                                 "platform": "c3725",
                                 "private_config": "",
                                 "ram": 128,
                                 "sparsemem": True,
                                 "startup_config": "ios_base_startup-config.txt",
                                 "symbol": unittest.mock.ANY,
                                 "system_id": "FTX0945W0MY"}

            for item, value in expected_response.items():
                assert response.json().get(item) == value

    async def test_c3600_dynamips_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c3600 template",
                  "platform": "c3600",
                  "chassis": "3660",
                  "compute_id": "local",
                  "image": "c3660-a3jk9s-mz.124-25d.image",
                  "template_type": "dynamips"}

        with asyncio_patch("gns3server.services.templates.TemplatesService._find_images", return_value=[]) as mock:
            response = await client.post(app.url_path_for("create_template"), json=params)
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["template_id"] is not None

            expected_response = {"template_type": "dynamips",
                                 "auto_delete_disks": False,
                                 "builtin": False,
                                 "category": "router",
                                 "compute_id": "local",
                                 "console_auto_start": False,
                                 "console_type": "telnet",
                                 "default_name_format": "R{0}",
                                 "disk0": 0,
                                 "disk1": 0,
                                 "exec_area": 64,
                                 "idlemax": 500,
                                 "idlepc": "",
                                 "idlesleep": 30,
                                 "image": "c3660-a3jk9s-mz.124-25d.image",
                                 "mac_addr": "",
                                 "mmap": True,
                                 "name": "Cisco c3600 template",
                                 "iomem": 5,
                                 "nvram": 128,
                                 "platform": "c3600",
                                 "chassis": "3660",
                                 "private_config": "",
                                 "ram": 192,
                                 "sparsemem": True,
                                 "startup_config": "ios_base_startup-config.txt",
                                 "symbol": unittest.mock.ANY,
                                 "system_id": "FTX0945W0MY"}

            for item, value in expected_response.items():
                assert response.json().get(item) == value

    async def test_c3600_dynamips_template_create_wrong_chassis(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c3600 template with wrong chassis",
                  "platform": "c3600",
                  "chassis": "3650",
                  "compute_id": "local",
                  "image": "c3660-a3jk9s-mz.124-25d.image",
                  "template_type": "dynamips"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_c2691_dynamips_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c2691 template",
                  "platform": "c2691",
                  "compute_id": "local",
                  "image": "c2691-adventerprisek9-mz.124-25d.image",
                  "template_type": "dynamips"}

        with asyncio_patch("gns3server.services.templates.TemplatesService._find_images", return_value=[]) as mock:
            response = await client.post(app.url_path_for("create_template"), json=params)
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["template_id"] is not None

            expected_response = {"template_type": "dynamips",
                                 "auto_delete_disks": False,
                                 "builtin": False,
                                 "category": "router",
                                 "compute_id": "local",
                                 "console_auto_start": False,
                                 "console_type": "telnet",
                                 "default_name_format": "R{0}",
                                 "disk0": 0,
                                 "disk1": 0,
                                 "exec_area": 64,
                                 "idlemax": 500,
                                 "idlepc": "",
                                 "idlesleep": 30,
                                 "image": "c2691-adventerprisek9-mz.124-25d.image",
                                 "mac_addr": "",
                                 "mmap": True,
                                 "name": "Cisco c2691 template",
                                 "iomem": 5,
                                 "nvram": 256,
                                 "platform": "c2691",
                                 "private_config": "",
                                 "ram": 192,
                                 "sparsemem": True,
                                 "startup_config": "ios_base_startup-config.txt",
                                 "symbol": unittest.mock.ANY,
                                 "system_id": "FTX0945W0MY"}

            for item, value in expected_response.items():
                assert response.json().get(item) == value

    async def test_c2600_dynamips_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c2600 template",
                  "platform": "c2600",
                  "chassis": "2651XM",
                  "compute_id": "local",
                  "image": "c2600-adventerprisek9-mz.124-25d.image",
                  "template_type": "dynamips"}

        with asyncio_patch("gns3server.services.templates.TemplatesService._find_images", return_value=[]) as mock:
            response = await client.post(app.url_path_for("create_template"), json=params)
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["template_id"] is not None

            expected_response = {"template_type": "dynamips",
                                 "auto_delete_disks": False,
                                 "builtin": False,
                                 "category": "router",
                                 "compute_id": "local",
                                 "console_auto_start": False,
                                 "console_type": "telnet",
                                 "default_name_format": "R{0}",
                                 "disk0": 0,
                                 "disk1": 0,
                                 "exec_area": 64,
                                 "idlemax": 500,
                                 "idlepc": "",
                                 "idlesleep": 30,
                                 "image": "c2600-adventerprisek9-mz.124-25d.image",
                                 "mac_addr": "",
                                 "mmap": True,
                                 "name": "Cisco c2600 template",
                                 "iomem": 15,
                                 "nvram": 128,
                                 "platform": "c2600",
                                 "chassis": "2651XM",
                                 "private_config": "",
                                 "ram": 160,
                                 "sparsemem": True,
                                 "startup_config": "ios_base_startup-config.txt",
                                 "symbol": unittest.mock.ANY,
                                 "system_id": "FTX0945W0MY"}

            for item, value in expected_response.items():
                assert response.json().get(item) == value

    async def test_c2600_dynamips_template_create_wrong_chassis(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c2600 template with wrong chassis",
                  "platform": "c2600",
                  "chassis": "2660XM",
                  "compute_id": "local",
                  "image": "c2600-adventerprisek9-mz.124-25d.image",
                  "template_type": "dynamips"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_c1700_dynamips_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c1700 template",
                  "platform": "c1700",
                  "chassis": "1760",
                  "compute_id": "local",
                  "image": "c1700-adventerprisek9-mz.124-25d.image",
                  "template_type": "dynamips"}

        with asyncio_patch("gns3server.services.templates.TemplatesService._find_images", return_value=[]) as mock:
            response = await client.post(app.url_path_for("create_template"), json=params)
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["template_id"] is not None

            expected_response = {"template_type": "dynamips",
                                 "auto_delete_disks": False,
                                 "builtin": False,
                                 "category": "router",
                                 "compute_id": "local",
                                 "console_auto_start": False,
                                 "console_type": "telnet",
                                 "default_name_format": "R{0}",
                                 "disk0": 0,
                                 "disk1": 0,
                                 "exec_area": 64,
                                 "idlemax": 500,
                                 "idlepc": "",
                                 "idlesleep": 30,
                                 "image": "c1700-adventerprisek9-mz.124-25d.image",
                                 "mac_addr": "",
                                 "mmap": True,
                                 "name": "Cisco c1700 template",
                                 "iomem": 15,
                                 "nvram": 128,
                                 "platform": "c1700",
                                 "chassis": "1760",
                                 "private_config": "",
                                 "ram": 160,
                                 "sparsemem": False,
                                 "startup_config": "ios_base_startup-config.txt",
                                 "symbol": unittest.mock.ANY,
                                 "system_id": "FTX0945W0MY"}

            for item, value in expected_response.items():
                assert response.json().get(item) == value

    async def test_c1700_dynamips_template_create_wrong_chassis(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c1700 template with wrong chassis",
                  "platform": "c1700",
                  "chassis": "1770",
                  "compute_id": "local",
                  "image": "c1700-adventerprisek9-mz.124-25d.image",
                  "template_type": "dynamips"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    async def test_dynamips_template_create_wrong_platform(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cisco c3900 template",
                  "platform": "c3900",
                  "compute_id": "local",
                  "image": "c3900-test.124-25d.image",
                  "template_type": "dynamips"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestIOUTemplate:

    async def test_iou_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        image_path = str(Path("/path/to/i86bi_linux-ipbase-ms-12.4.bin"))
        params = {"name": "IOU template",
                  "compute_id": "local",
                  "path": image_path,
                  "template_type": "iou"}

        with asyncio_patch("gns3server.services.templates.TemplatesService._find_images", return_value=[]) as mock:
            response = await client.post(app.url_path_for("create_template"), json=params)
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["template_id"] is not None

            expected_response = {"template_type": "iou",
                                 "builtin": False,
                                 "category": "router",
                                 "compute_id": "local",
                                 "console_auto_start": False,
                                 "console_type": "telnet",
                                 "default_name_format": "IOU{0}",
                                 "ethernet_adapters": 2,
                                 "name": "IOU template",
                                 "nvram": 128,
                                 "path": image_path,
                                 "private_config": "",
                                 "ram": 256,
                                 "serial_adapters": 2,
                                 "startup_config": "iou_l3_base_startup-config.txt",
                                 "symbol": unittest.mock.ANY,
                                 "use_default_iou_values": True,
                                 "l1_keepalives": False}

            for item, value in expected_response.items():
                assert response.json().get(item) == value


class TestDockerTemplate:

    async def test_docker_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Docker template",
                  "compute_id": "local",
                  "image": "gns3/endhost:latest",
                  "template_type": "docker"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["template_id"] is not None

        expected_response = {"adapters": 1,
                             "template_type": "docker",
                             "builtin": False,
                             "category": "guest",
                             "compute_id": "local",
                             "console_auto_start": False,
                             "console_http_path": "/",
                             "console_http_port": 80,
                             "console_resolution": "1024x768",
                             "console_type": "telnet",
                             "default_name_format": "{name}-{0}",
                             "environment": "",
                             "extra_hosts": "",
                             "image": "gns3/endhost:latest",
                             "name": "Docker template",
                             "start_command": "",
                             "symbol": unittest.mock.ANY,
                             "custom_adapters": []}

        for item, value in expected_response.items():
            assert response.json().get(item) == value


class TestQemuTemplate:

    async def test_qemu_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Qemu template",
                  "compute_id": "local",
                  "platform": "i386",
                  "hda_disk_image": "IOSvL2-15.2.4.0.55E.qcow2",
                  "ram": 512,
                  "template_type": "qemu"}

        with asyncio_patch("gns3server.services.templates.TemplatesService._find_images", return_value=[]) as mock:
            response = await client.post(app.url_path_for("create_template"), json=params)
            assert mock.called
            assert response.status_code == status.HTTP_201_CREATED
            assert response.json()["template_id"] is not None

            expected_response = {"adapter_type": "e1000",
                                 "adapters": 1,
                                 "template_type": "qemu",
                                 "bios_image": "",
                                 "boot_priority": "c",
                                 "builtin": False,
                                 "category": "guest",
                                 "cdrom_image": "",
                                 "compute_id": "local",
                                 "console_auto_start": False,
                                 "console_type": "telnet",
                                 "cpu_throttling": 0,
                                 "cpus": 1,
                                 "default_name_format": "{name}-{0}",
                                 "first_port_name": "",
                                 "hda_disk_image": "IOSvL2-15.2.4.0.55E.qcow2",
                                 "hda_disk_interface": "none",
                                 "hdb_disk_image": "",
                                 "hdb_disk_interface": "none",
                                 "hdc_disk_image": "",
                                 "hdc_disk_interface": "none",
                                 "hdd_disk_image": "",
                                 "hdd_disk_interface": "none",
                                 "initrd": "",
                                 "kernel_command_line": "",
                                 "kernel_image": "",
                                 "linked_clone": True,
                                 "mac_address": "",
                                 "name": "Qemu template",
                                 "on_close": "power_off",
                                 "options": "",
                                 "platform": "i386",
                                 "port_name_format": "Ethernet{0}",
                                 "port_segment_size": 0,
                                 "process_priority": "normal",
                                 "qemu_path": "",
                                 "ram": 512,
                                 "symbol": unittest.mock.ANY,
                                 "usage": "",
                                 "custom_adapters": []}

            for item, value in expected_response.items():
                assert response.json().get(item) == value


class TestVMwareTemplate:

    async def test_vmware_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        vmx_path = str(Path("/path/to/vm.vmx"))
        params = {"name": "VMware template",
                  "compute_id": "local",
                  "template_type": "vmware",
                  "vmx_path": vmx_path}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["template_id"] is not None

        expected_response = {"adapter_type": "e1000",
                             "adapters": 1,
                             "template_type": "vmware",
                             "builtin": False,
                             "category": "guest",
                             "compute_id": "local",
                             "console_auto_start": False,
                             "console_type": "none",
                             "default_name_format": "{name}-{0}",
                             "first_port_name": "",
                             "headless": False,
                             "linked_clone": False,
                             "name": "VMware template",
                             "on_close": "power_off",
                             "port_name_format": "Ethernet{0}",
                             "port_segment_size": 0,
                             "symbol": unittest.mock.ANY,
                             "use_any_adapter": False,
                             "vmx_path": vmx_path,
                             "custom_adapters": []}

        for item, value in expected_response.items():
            assert response.json().get(item) == value


class TestVirtualBoxTemplate:

    async def test_virtualbox_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "VirtualBox template",
                  "compute_id": "local",
                  "template_type": "virtualbox",
                  "vmname": "My VirtualBox VM"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["template_id"] is not None

        expected_response = {"adapter_type": "Intel PRO/1000 MT Desktop (82540EM)",
                             "adapters": 1,
                             "template_type": "virtualbox",
                             "builtin": False,
                             "category": "guest",
                             "compute_id": "local",
                             "console_auto_start": False,
                             "console_type": "none",
                             "default_name_format": "{name}-{0}",
                             "first_port_name": "",
                             "headless": False,
                             "linked_clone": False,
                             "name": "VirtualBox template",
                             "on_close": "power_off",
                             "port_name_format": "Ethernet{0}",
                             "port_segment_size": 0,
                             "ram": 256,
                             "symbol": unittest.mock.ANY,
                             "use_any_adapter": False,
                             "vmname": "My VirtualBox VM",
                             "custom_adapters": []}

        for item, value in expected_response.items():
            assert response.json().get(item) == value


class TestVPCSTemplate:

    async def test_vpcs_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "VPCS template",
                  "compute_id": "local",
                  "template_type": "vpcs"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["template_id"] is not None

        expected_response = {"template_type": "vpcs",
                             "base_script_file": "vpcs_base_config.txt",
                             "builtin": False,
                             "category": "guest",
                             "compute_id": "local",
                             "console_auto_start": False,
                             "console_type": "telnet",
                             "default_name_format": "PC{0}",
                             "name": "VPCS template",
                             "symbol": unittest.mock.ANY}

        for item, value in expected_response.items():
            assert response.json().get(item) == value


class TestEthernetSwitchTemplate:

    async def test_ethernet_switch_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Ethernet switch template",
                  "compute_id": "local",
                  "template_type": "ethernet_switch"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["template_id"] is not None

        expected_response = {"template_type": "ethernet_switch",
                             "builtin": False,
                             "category": "switch",
                             "compute_id": "local",
                             "console_type": "none",
                             "default_name_format": "Switch{0}",
                             "name": "Ethernet switch template",
                             "ports_mapping": [{"ethertype": "0x8100",
                                                "name": "Ethernet0",
                                                "port_number": 0,
                                                "type": "access",
                                                "vlan": 1
                                                },
                                               {"ethertype": "0x8100",
                                                "name": "Ethernet1",
                                                "port_number": 1,
                                                "type": "access",
                                                "vlan": 1
                                                },
                                               {"ethertype": "0x8100",
                                                "name": "Ethernet2",
                                                "port_number": 2,
                                                "type": "access",
                                                "vlan": 1
                                                },
                                               {"ethertype": "0x8100",
                                                "name": "Ethernet3",
                                                "port_number": 3,
                                                "type": "access",
                                                "vlan": 1
                                                },
                                               {"ethertype": "0x8100",
                                                "name": "Ethernet4",
                                                "port_number": 4,
                                                "type": "access",
                                                "vlan": 1
                                                },
                                               {"ethertype": "0x8100",
                                                "name": "Ethernet5",
                                                "port_number": 5,
                                                "type": "access",
                                                "vlan": 1
                                                },
                                               {"ethertype": "0x8100",
                                                "name": "Ethernet6",
                                                "port_number": 6,
                                                "type": "access",
                                                "vlan": 1
                                                },
                                               {"ethertype": "0x8100",
                                                "name": "Ethernet7",
                                                "port_number": 7,
                                                "type": "access",
                                                "vlan": 1
                                                }],
                             "symbol": unittest.mock.ANY}

        for item, value in expected_response.items():
            assert response.json().get(item) == value


class TestHubTemplate:

    async def test_ethernet_hub_template_create(self, app: FastAPI, client: AsyncClient) -> None:
        params = {"name": "Ethernet hub template",
                  "compute_id": "local",
                  "template_type": "ethernet_hub"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["template_id"] is not None

        expected_response = {"ports_mapping": [{"port_number": 0,
                                                "name": "Ethernet0"
                                                },
                                               {"port_number": 1,
                                                "name": "Ethernet1"
                                                },
                                               {"port_number": 2,
                                                "name": "Ethernet2"
                                                },
                                               {"port_number": 3,
                                                "name": "Ethernet3"
                                                },
                                               {"port_number": 4,
                                                "name": "Ethernet4"
                                                },
                                               {"port_number": 5,
                                                "name": "Ethernet5"
                                                },
                                               {"port_number": 6,
                                                "name": "Ethernet6"
                                                },
                                               {"port_number": 7,
                                                "name": "Ethernet7"
                                                }],
                             "compute_id": "local",
                             "name": "Ethernet hub template",
                             "symbol": unittest.mock.ANY,
                             "default_name_format": "Hub{0}",
                             "template_type": "ethernet_hub",
                             "category": "switch",
                             "builtin": False}

        for item, value in expected_response.items():
            assert response.json().get(item) == value


class TestCloudTemplate:

    async def test_cloud_template_create(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Cloud template",
                  "compute_id": "local",
                  "template_type": "cloud"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["template_id"] is not None

        expected_response = {"template_type": "cloud",
                             "builtin": False,
                             "category": "guest",
                             "compute_id": "local",
                             "default_name_format": "Cloud{0}",
                             "name": "Cloud template",
                             "ports_mapping": [],
                             "symbol": unittest.mock.ANY,
                             "remote_console_host": "127.0.0.1",
                             "remote_console_port": 23,
                             "remote_console_type": "none",
                             "remote_console_http_path": "/"}

        for item, value in expected_response.items():
            assert response.json().get(item) == value


class TestImageAssociationWithTemplate:

    @pytest.mark.parametrize(
        "image_name, image_type, params",
        (
                (
                        "c7200-adventerprisek9-mz.124-24.T5.image",
                        "ios",
                        {
                            "template_id": "6d85c8db-640f-4547-8955-bc132f7d7196",
                            "name": "Cisco c7200 template",
                            "platform": "c7200",
                            "compute_id": "local",
                            "image": "<replace_image>",
                            "template_type": "dynamips"
                        }
                ),
                (
                        "i86bi_linux-ipbase-ms-12.4.bin",
                        "iou",
                        {
                            "template_id": "0014185e-bdfe-454b-86cd-9009c23900c5",
                            "name": "IOU template",
                            "compute_id": "local",
                            "path": "<replace_image>",
                            "template_type": "iou"
                        }
                ),
                (
                        "image.qcow2",
                        "qemu",
                        {
                            "template_id": "97ef56a5-7ae4-4795-ad4c-e7dcdd745cff",
                            "name": "Qemu template",
                            "compute_id": "local",
                            "platform": "i386",
                            "hda_disk_image": "<replace_image>",
                            "hdb_disk_image": "<replace_image>",
                            "hdc_disk_image": "<replace_image>",
                            "hdd_disk_image": "<replace_image>",
                            "cdrom_image": "<replace_image>",
                            "kernel_image": "<replace_image>",
                            "bios_image": "<replace_image>",
                            "ram": 512,
                            "template_type": "qemu"
                        }
                ),
        ),
    )
    async def test_template_create_with_images(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            tmpdir: str,
            image_name: str,
            image_type: str,
            params: dict
    ) -> None:

        path = os.path.join(tmpdir, image_name)
        with open(path, "wb+") as f:
            f.write(b'\x42\x42\x42\x42')
        images_repo = ImagesRepository(db_session)
        await images_repo.add_image(image_name, image_type, 42, path, "e342eb86c1229b6c154367a5476969b5", "md5")
        for key, value in params.items():
            if value == "<replace_image>":
                params[key] = image_name
        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED

        templates_repo = TemplatesRepository(db_session)
        db_template = await templates_repo.get_template(uuid.UUID(params["template_id"]))
        assert len(db_template.images) == 1
        assert db_template.images[0].filename == image_name

    @pytest.mark.parametrize(
        "image_name, image_type, template_id, params",
        (
                (
                        "c7200-adventerprisek9-mz.155-2.XB.image",
                        "ios",
                        "6d85c8db-640f-4547-8955-bc132f7d7196",
                        {
                            "image": "<replace_image>",
                        }
                ),
                (
                        "i86bi-linux-l2-adventerprisek9-15.2d.bin",
                        "iou",
                        "0014185e-bdfe-454b-86cd-9009c23900c5",
                        {
                            "path": "<replace_image>",
                        }
                ),
                (
                        "new_image.qcow2",
                        "qemu",
                        "97ef56a5-7ae4-4795-ad4c-e7dcdd745cff",
                        {
                            "hda_disk_image": "<replace_image>",
                            "hdb_disk_image": "<replace_image>",
                            "hdc_disk_image": "<replace_image>",
                            "hdd_disk_image": "<replace_image>",
                            "cdrom_image": "<replace_image>",
                            "kernel_image": "<replace_image>",
                            "bios_image": "<replace_image>",
                        }
                ),
        ),
    )
    async def test_template_update_with_images(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            tmpdir: str,
            image_name: str,
            image_type: str,
            template_id: str,
            params: dict
    ) -> None:

        path = os.path.join(tmpdir, image_name)
        with open(path, "wb+") as f:
            f.write(b'\x42\x42\x42\x42')
        images_repo = ImagesRepository(db_session)
        await images_repo.add_image(image_name, image_type, 42, path, "e342eb86c1229b6c154367a5476969b5", "md5")

        for key, value in params.items():
            if value == "<replace_image>":
                params[key] = image_name
        response = await client.put(app.url_path_for("update_template", template_id=template_id), json=params)
        assert response.status_code == status.HTTP_200_OK

        templates_repo = TemplatesRepository(db_session)
        db_template = await templates_repo.get_template(uuid.UUID(template_id))
        assert len(db_template.images) == 1
        assert db_template.images[0].filename == image_name

    @pytest.mark.parametrize(
        "template_id, params",
        (
                (
                        "6d85c8db-640f-4547-8955-bc132f7d7196",
                        {
                            "image": "<remove_image>",
                        }
                ),
                (
                        "0014185e-bdfe-454b-86cd-9009c23900c5",
                        {
                            "path": "<remove_image>",
                        }
                ),
                (
                        "97ef56a5-7ae4-4795-ad4c-e7dcdd745cff",
                        {
                            "hda_disk_image": "<remove_image>",
                            "hdb_disk_image": "<remove_image>",
                            "hdc_disk_image": "<remove_image>",
                            "hdd_disk_image": "<remove_image>",
                            "cdrom_image": "<remove_image>",
                            "kernel_image": "<remove_image>",
                            "bios_image": "<remove_image>",
                        }
                ),
        ),
    )
    async def test_remove_images_from_template(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            template_id: str,
            params: dict
    ) -> None:

        for key, value in params.items():
            if value == "<remove_image>":
                params[key] = ""
        response = await client.put(app.url_path_for("update_template", template_id=template_id), json=params)
        assert response.status_code == status.HTTP_200_OK

        templates_repo = TemplatesRepository(db_session)
        db_template = await templates_repo.get_template(uuid.UUID(template_id))
        assert len(db_template.images) == 0

    async def test_template_create_with_image_in_subdir(
            self,
            app: FastAPI,
            client: AsyncClient,
            db_session: AsyncSession,
            tmpdir: str,
    ) -> None:

        params = {"name": "Qemu template",
                  "version": "1.0",
                  "compute_id": "local",
                  "platform": "i386",
                  "hda_disk_image": "subdir/image.qcow2",
                  "ram": 512,
                  "template_type": "qemu"}

        path = os.path.join(tmpdir, "subdir", "image.qcow2")
        os.makedirs(os.path.dirname(path))
        with open(path, "wb+") as f:
            f.write(b'\x42\x42\x42\x42')
        images_repo = ImagesRepository(db_session)
        await images_repo.add_image("image.qcow2", "qemu", 42, path, "e342eb86c1229b6c154367a5476969b5", "md5")

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_201_CREATED
        template_id = response.json()["template_id"]

        templates_repo = TemplatesRepository(db_session)
        db_template = await templates_repo.get_template(template_id)
        assert len(db_template.images) == 1
        assert db_template.images[0].path.endswith("subdir/image.qcow2")

    async def test_template_create_with_non_existing_image(self, app: FastAPI, client: AsyncClient) -> None:

        params = {"name": "Qemu template with non existing image",
                  "compute_id": "local",
                  "platform": "i386",
                  "hda_disk_image": "unkown_image.qcow2",
                  "ram": 512,
                  "template_type": "qemu"}

        response = await client.post(app.url_path_for("create_template"), json=params)
        assert response.status_code == status.HTTP_404_NOT_FOUND
