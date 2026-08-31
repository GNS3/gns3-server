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

import pytest

from fastapi import FastAPI, status
from httpx import AsyncClient
from tests.utils import asyncio_patch

pytestmark = pytest.mark.asyncio


class TestImagesRoutes:

    async def test_pull_docker_image(self, app: FastAPI, compute_client: AsyncClient) -> None:

        with asyncio_patch("gns3server.compute.docker.Docker.pull_image") as mock:
            response = await compute_client.post(
                app.url_path_for("compute:pull_docker_image"),
                json={"image": "nginx:latest"}
            )
            mock.assert_called_once_with("nginx:latest", force=True)
            assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.parametrize("image", ["", "   ", "nginx latest"])
    async def test_pull_docker_image_rejects_invalid_name(
            self, app: FastAPI, compute_client: AsyncClient, image: str
    ) -> None:

        with asyncio_patch("gns3server.compute.docker.Docker.pull_image") as mock:
            response = await compute_client.post(
                app.url_path_for("compute:pull_docker_image"),
                json={"image": image}
            )
            mock.assert_not_called()
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
