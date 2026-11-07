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

from gns3server.compute.docker.docker_error import DockerError
from tests.utils import asyncio_patch

pytestmark = pytest.mark.asyncio


class TestImagesRoutes:
    async def test_pull_docker_image(self, app: FastAPI, compute_client: AsyncClient) -> None:

        async def fake_pull(image, progress_callback=None, force=False):
            progress_callback(
                {"layers_total": 0, "layers_done": 0, "message": "Pulling 'nginx:latest'", "state": "started"}
            )

        with asyncio_patch("gns3server.compute.docker.Docker.pull_image", side_effect=fake_pull) as mock:
            with asyncio_patch("gns3server.compute.notification_manager.NotificationManager.emit") as emit_mock:
                response = await compute_client.post(
                    app.url_path_for("compute:pull_docker_image"), json={"image": "nginx:latest"}
                )
                assert mock.call_args[0] == ("nginx:latest",)
                assert mock.call_args[1]["force"] is True
                assert callable(mock.call_args[1]["progress_callback"])
                # started and completed events are emitted to the notification stream
                assert [(c.args[0], c.args[1]["state"]) for c in emit_mock.call_args_list] == [
                    ("docker.image.pull", "started"),
                    ("docker.image.pull", "completed"),
                ]
                assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_pull_docker_image_progress_id(self, app: FastAPI, compute_client: AsyncClient) -> None:

        async def fake_pull(image, progress_callback=None, force=False):
            progress_callback({"layers_total": 1, "layers_done": 0, "message": "Pulling", "state": "started"})
            progress_callback({"layers_total": 1, "layers_done": 0, "message": "[==>   ] 10/100"})

        with asyncio_patch("gns3server.compute.docker.Docker.pull_image", side_effect=fake_pull):
            with asyncio_patch("gns3server.compute.notification_manager.NotificationManager.emit") as emit_mock:
                response = await compute_client.post(
                    app.url_path_for("compute:pull_docker_image"),
                    json={"image": "nginx:latest"},
                    params={"progress_id": "abc123"},
                )
                assert response.status_code == status.HTTP_204_NO_CONTENT
                assert all(c.args[1]["progress_id"] == "abc123" for c in emit_mock.call_args_list)

    async def test_pull_docker_image_reports_downloading(self, app: FastAPI, compute_client: AsyncClient) -> None:

        async def fake_pull(image, progress_callback=None, force=False):
            progress_callback({"layers_total": 2, "layers_done": 0, "message": "Pulling", "state": "started"})
            progress_callback({"layers_total": 2, "layers_done": 1, "message": "[==>   ] 40/100"})

        with asyncio_patch("gns3server.compute.docker.Docker.pull_image", side_effect=fake_pull):
            with asyncio_patch("gns3server.compute.notification_manager.NotificationManager.emit") as emit_mock:
                response = await compute_client.post(
                    app.url_path_for("compute:pull_docker_image"), json={"image": "nginx:latest"}
                )
                assert response.status_code == status.HTTP_204_NO_CONTENT
                states = [c.args[1]["state"] for c in emit_mock.call_args_list]
                assert states == ["started", "downloading", "completed"]
                downloading = emit_mock.call_args_list[1].args[1]
                assert downloading["layers_total"] == 2
                assert downloading["layers_done"] == 1
                assert downloading["message"] == "[==>   ] 40/100"

    async def test_pull_docker_image_emits_failed(self, app: FastAPI, compute_client: AsyncClient) -> None:

        async def fake_pull(image, progress_callback=None, force=False):
            raise DockerError("no data received for 60 seconds")

        with asyncio_patch("gns3server.compute.docker.Docker.pull_image", side_effect=fake_pull):
            with asyncio_patch("gns3server.compute.notification_manager.NotificationManager.emit") as emit_mock:
                response = await compute_client.post(
                    app.url_path_for("compute:pull_docker_image"), json={"image": "nginx:latest"}
                )
                assert response.status_code == status.HTTP_409_CONFLICT
                failed = emit_mock.call_args_list[-1].args[1]
                assert failed["state"] == "failed"
                assert "no data received" in failed["message"]

    @pytest.mark.parametrize("image", ["", "   ", "nginx latest"])
    async def test_pull_docker_image_rejects_invalid_name(
        self, app: FastAPI, compute_client: AsyncClient, image: str
    ) -> None:

        with asyncio_patch("gns3server.compute.docker.Docker.pull_image") as mock:
            response = await compute_client.post(app.url_path_for("compute:pull_docker_image"), json={"image": image})
            mock.assert_not_called()
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_load_docker_image(self, app: FastAPI, compute_client: AsyncClient) -> None:

        with asyncio_patch("gns3server.compute.docker.Docker.load_image") as mock:
            response = await compute_client.post(
                app.url_path_for("compute:load_docker_image"), content=b"docker-save-tar-bytes"
            )
            mock.assert_called_once()
            # the tar is streamed to the Docker daemon as an async iterable
            stream = mock.call_args[0][0]
            assert hasattr(stream, "__aiter__")
            assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_delete_docker_image(self, app: FastAPI, compute_client: AsyncClient) -> None:

        with asyncio_patch("gns3server.compute.docker.Docker.delete_image") as mock:
            response = await compute_client.delete(
                app.url_path_for("compute:delete_docker_image", image="ios-xr/xrd-control-plane:24.4.1")
            )
            mock.assert_called_once_with("ios-xr/xrd-control-plane:24.4.1", force=False)
            assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_delete_docker_image_rejects_path_traversal(self, app: FastAPI, compute_client: AsyncClient) -> None:
        # percent encoded so the client does not normalize the ".." segments
        # away before the request reaches the server
        with asyncio_patch("gns3server.compute.docker.Docker.delete_image") as mock:
            response = await compute_client.delete("/v3/compute/docker/images/a%2F..%2F..%2Fversion")
            mock.assert_not_called()
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_delete_docker_image_force(self, app: FastAPI, compute_client: AsyncClient) -> None:

        with asyncio_patch("gns3server.compute.docker.Docker.delete_image") as mock:
            response = await compute_client.delete(
                app.url_path_for("compute:delete_docker_image", image="ubuntu:latest"),
                params={"force": "true"},
            )
            mock.assert_called_once_with("ubuntu:latest", force=True)
            assert response.status_code == status.HTTP_204_NO_CONTENT

    async def test_load_docker_image_with_image_and_digest(self, app: FastAPI, compute_client: AsyncClient) -> None:

        digest = "sha256:" + "a" * 64
        with asyncio_patch("gns3server.compute.docker.Docker.load_image") as mock:
            response = await compute_client.post(
                app.url_path_for("compute:load_docker_image"),
                params={"image": "gns3/frr:latest", "digest": digest},
                content=b"docker-save-tar-bytes",
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT
            # the tag and the digest pinned by the controller reach the manager
            assert mock.call_args[1] == {"image": "gns3/frr:latest", "digest": digest}
