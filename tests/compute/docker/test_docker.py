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
import pytest_asyncio

from gns3server.compute.docker import (
    DOCKER_MINIMUM_API_VERSION,
    DOCKER_PREFERRED_API_VERSION,
    PULL_IDLE_TIMEOUT,
    Docker,
)
from gns3server.compute.docker.docker_error import DockerError, DockerHttp404Error, DockerHttp409Error
from gns3server.compute.project_manager import ProjectManager
from tests.utils import AsyncioMagicMock, asyncio_patch


@pytest_asyncio.fixture
async def vm():

    vm = Docker()
    vm._connected = True
    vm._session = MagicMock()
    vm._session.closed = False
    return vm


@pytest.mark.asyncio
async def test_query_success(vm):

    response = MagicMock()
    response.status = 200
    response.headers = {"CONTENT-TYPE": "application/json"}

    async def read():
        return b'{"c": false}'

    response.read.side_effect = read
    vm._session.request = AsyncioMagicMock(return_value=response)
    data = await vm.query("POST", "test", data={"a": True}, params={"b": 1})
    vm._session.request.assert_called_with(
        "POST",
        f"http://docker/v{DOCKER_MINIMUM_API_VERSION}/test",
        data='{"a": true}',
        headers={"content-type": "application/json"},
        params={"b": 1},
        timeout=300,
    )

    assert data == {"c": False}


@pytest.mark.asyncio
async def test_query_error(vm):

    response = MagicMock()
    response.status = 404

    async def read():
        return b"NOT FOUND"

    response.read.side_effect = read
    vm._session.request = AsyncioMagicMock(return_value=response)
    with pytest.raises(DockerError):
        await vm.query("POST", "test", data={"a": True}, params={"b": 1})
    vm._session.request.assert_called_with(
        "POST",
        f"http://docker/v{DOCKER_MINIMUM_API_VERSION}/test",
        data='{"a": true}',
        headers={"content-type": "application/json"},
        params={"b": 1},
        timeout=300,
    )


@pytest.mark.asyncio
async def test_query_error_json(vm):

    response = MagicMock()
    response.status = 404

    async def read():
        return b'{"message": "Error"}'

    response.read.side_effect = read
    vm._session.request = AsyncioMagicMock(return_value=response)
    with pytest.raises(DockerError):
        await vm.query("POST", "test", data={"a": True}, params={"b": 1})
    vm._session.request.assert_called_with(
        "POST",
        f"http://docker/v{DOCKER_MINIMUM_API_VERSION}/test",
        data='{"a": true}',
        headers={"content-type": "application/json"},
        params={"b": 1},
        timeout=300,
    )


@pytest.mark.asyncio
async def test_list_images():

    response = [
        {
            "RepoTags": ["ubuntu:12.04", "ubuntu:precise", "ubuntu:latest"],
            "Id": "8dbd9e392a964056420e5d58ca5cc376ef18e2de93b5cc90e868a1bbc8318c1c",
            "Created": 1365714795,
            "Size": 131506275,
            "VirtualSize": 131506275,
        },
        {
            "RepoTags": ["ubuntu:12.10", "ubuntu:quantal", "<none>:<none>"],
            "ParentId": "27cf784147099545",
            "Id": "b750fe79269d2ec9a3c593ef05b4332b1d1a02a62b4accb2c21d589ff2f5f2dc",
            "Created": 1364102658,
            "Size": 24653,
            "VirtualSize": 180116135,
        },
    ]

    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response) as mock:
        images = await Docker.instance().list_images()
        mock.assert_called_with("GET", "images/json", params={"all": 0})
    assert len(images) == 5
    by_tag = {image["image"]: image for image in images}
    assert by_tag["ubuntu:12.04"]["id"] == "8dbd9e392a964056420e5d58ca5cc376ef18e2de93b5cc90e868a1bbc8318c1c"
    assert by_tag["ubuntu:12.04"]["size"] == 131506275
    assert by_tag["ubuntu:12.04"]["created"] == 1365714795
    # tags of the same image share its id
    assert by_tag["ubuntu:precise"]["id"] == by_tag["ubuntu:12.04"]["id"]
    assert "<none>:<none>" not in by_tag
    assert {"ubuntu:precise", "ubuntu:latest", "ubuntu:12.10", "ubuntu:quantal"} <= set(by_tag)


@pytest.mark.asyncio
async def test_list_images_created_fallback_to_oci_label():
    """
    Images built without a created timestamp (e.g. reproducible Ubuntu images)
    report 0 from the daemon: the build time comes from the OCI created label.
    """

    response = [
        {
            # zero timestamp, the label is used (Z suffix, nanosecond precision)
            "RepoTags": ["ubuntu:latest"],
            "Id": "febc1a2eec1f",
            "Created": 0,
            "Size": 78101592,
            "Labels": {"org.opencontainers.image.created": "2026-10-25T10:26:07.538865123Z"},
        },
        {
            # zero timestamp without a label stays at zero
            "RepoTags": ["no-label:latest"],
            "Id": "aaaaaa",
            "Created": 0,
            "Size": 1,
        },
        {
            # the daemon timestamp wins over the label when it is set
            "RepoTags": ["normal:latest"],
            "Id": "bbbbbb",
            "Created": 1365714795,
            "Size": 1,
            "Labels": {"org.opencontainers.image.created": "2000-01-01T00:00:00Z"},
        },
        {
            # a broken label is ignored, the timestamp stays at zero
            "RepoTags": ["broken-label:latest"],
            "Id": "cccccc",
            "Created": 0,
            "Size": 1,
            "Labels": {"org.opencontainers.image.created": "not a date"},
        },
    ]

    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response):
        images = await Docker.instance().list_images()
    by_tag = {image["image"]: image for image in images}
    assert by_tag["ubuntu:latest"]["created"] == 1792923967
    assert by_tag["no-label:latest"]["created"] == 0
    assert by_tag["normal:latest"]["created"] == 1365714795
    assert by_tag["broken-label:latest"]["created"] == 0


@pytest.mark.asyncio
async def test_pull_image():

    class Response:
        """
        Simulate a response split in multiple packets
        """

        def __init__(self):
            self._read = -1

        async def read(self, size):
            self._read += 1
            if self._read == 0:
                return b'{"progress": "0/100",'
            elif self._read == 1:
                return '"id": 42}'
            else:
                None

    mock_query = MagicMock()
    mock_query.content.return_value = Response()

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerHttp404Error("404")):
        with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=mock_query) as mock:
            await Docker.instance().pull_image("ubuntu")
            args, kwargs = mock.call_args
            assert args == ("POST", "images/create")
            assert kwargs["params"] == {"fromImage": "ubuntu", "tag": "latest"}
            # no total timeout (a pull can take as long as it needs) but an
            # idle socket read timeout, so an unreachable registry fails
            assert kwargs["timeout"].total is None
            assert kwargs["timeout"].sock_read == PULL_IDLE_TIMEOUT


@pytest.mark.asyncio
async def test_pull_image_reports_aggregated_progress():

    class Content:
        def __init__(self):
            self._chunks = [
                b'{"status": "Pulling fs layer", "id": "sha256:a"}\n'
                b'{"status": "Pulling fs layer", "id": "sha256:b"}\n'
                b'{"status": "Downloading", "id": "sha256:a", "progress": "[==>   ] 40/100"}\n'
                b'{"status": "Pull complete", "id": "sha256:a"}\n',
                b'{"status": "Pull complete", "id": "sha256:b"}\n',
                b"",
            ]

        async def read(self, size):
            return self._chunks.pop(0)

    response = MagicMock()
    response.content = Content()

    progress = []
    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerHttp404Error("404")):
        with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response):
            await Docker.instance().pull_image("ubuntu", progress_callback=progress.append)
    # the callback sees the running totals of layers, not raw daemon lines
    assert progress[0] == {
        "layers_total": 0,
        "layers_done": 0,
        "message": "Pulling 'ubuntu' from Docker repository",
        "state": "started",
    }
    assert progress[1] == {"layers_total": 1, "layers_done": 0, "message": "Pulling fs layer"}
    assert progress[2] == {"layers_total": 2, "layers_done": 0, "message": "Pulling fs layer"}
    assert {"layers_total": 2, "layers_done": 0, "message": "[==>   ] 40/100"} in progress
    assert progress[-1] == {"layers_total": 2, "layers_done": 2, "message": "Pull complete"}


@pytest.mark.asyncio
async def test_pull_image_skips_image_available_locally():

    with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": "existing"}) as query_mock:
        with asyncio_patch("gns3server.compute.docker.Docker.http_query") as pull_mock:
            await Docker.instance().pull_image("ubuntu")
            query_mock.assert_called_once_with("GET", "images/ubuntu/json")
            pull_mock.assert_not_called()


@pytest.mark.asyncio
async def test_force_pull_image():

    response = MagicMock()
    response.content.read = AsyncioMagicMock(return_value=b"")

    with asyncio_patch("gns3server.compute.docker.Docker.query") as query_mock:
        with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response) as pull_mock:
            await Docker.instance().pull_image("ubuntu", force=True)
            query_mock.assert_not_called()
            args, kwargs = pull_mock.call_args
            assert args == ("POST", "images/create")
            assert kwargs["params"] == {"fromImage": "ubuntu", "tag": "latest"}
            assert kwargs["timeout"].sock_read == PULL_IDLE_TIMEOUT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "image, expected_params",
    [
        # without a tag or digest the daemon would pull every tag of the
        # repository: default to latest so the pull targets a single tag
        ("ubuntu", {"fromImage": "ubuntu", "tag": "latest"}),
        ("gns3/ubuntu", {"fromImage": "gns3/ubuntu", "tag": "latest"}),
        # the ':' before the last '/' is a registry port, not a tag
        ("registry:5000/ubuntu", {"fromImage": "registry:5000/ubuntu", "tag": "latest"}),
        ("registry:5000/gns3/ubuntu", {"fromImage": "registry:5000/gns3/ubuntu", "tag": "latest"}),
        # an explicit tag or digest is left alone
        ("ubuntu:24.04", {"fromImage": "ubuntu:24.04"}),
        ("registry:5000/ubuntu:24.04", {"fromImage": "registry:5000/ubuntu:24.04"}),
        ("ubuntu@sha256:8b2f", {"fromImage": "ubuntu@sha256:8b2f"}),
    ],
)
async def test_pull_image_targets_a_single_tag(image, expected_params):

    response = MagicMock()
    response.content.read = AsyncioMagicMock(return_value=b"")

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerHttp404Error("404")):
        with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response) as pull_mock:
            await Docker.instance().pull_image(image)
            args, kwargs = pull_mock.call_args
            assert args == ("POST", "images/create")
            assert kwargs["params"] == expected_params


@pytest.mark.asyncio
async def test_pull_image_error():

    class Content:
        def __init__(self):
            self._chunks = [b'{"error": "image not found"}', b""]

        async def read(self, size):
            return self._chunks.pop(0)

    response = MagicMock()
    response.content = Content()

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerHttp404Error("404")):
        with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response):
            with pytest.raises(DockerError, match="image not found"):
                await Docker.instance().pull_image("missing")
            response.close.assert_called_once()


@pytest.mark.asyncio
async def test_pull_image_not_found_is_not_reported_as_a_network_error():
    """
    A 404 from the registry means the image name is wrong or the registry needs
    authentication: telling the user to check the Internet connection sends
    them in the wrong direction.
    """

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerHttp404Error("404")):
        with asyncio_patch(
            "gns3server.compute.docker.Docker.http_query",
            side_effect=DockerHttp404Error("Docker has returned an error: 404 pull access denied for debian13"),
        ):
            with pytest.raises(DockerError, match="not found in the registry") as error:
                await Docker.instance().pull_image("debian13")
    assert "Internet connection" not in str(error.value)


@pytest.mark.asyncio
async def test_pull_image_rejects_incomplete_response():

    class Content:
        def __init__(self):
            self._read = False

        async def read(self, size):
            if self._read:
                return b""
            self._read = True
            return b'{"status": "Pulling"'

    response = MagicMock()
    response.content = Content()

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerHttp404Error("404")):
        with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response):
            with pytest.raises(DockerError, match="Invalid response"):
                await Docker.instance().pull_image("ubuntu")
            response.close.assert_called_once()


@pytest.mark.asyncio
async def test_pull_image_propagates_timeout():

    class Content:
        async def read(self, size):
            raise TimeoutError

    response = MagicMock()
    response.content = Content()

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerHttp404Error("404")):
        with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response):
            with pytest.raises(DockerError, match="Timeout while pulling"):
                await Docker.instance().pull_image("ubuntu")
            response.close.assert_called_once()


@pytest.mark.asyncio
async def test_load_image():

    class Content:
        def __init__(self):
            self._chunks = [b'{"stream": "Loaded image ID: sha256:e90e34656806"}', b""]

        async def read(self, size):
            return self._chunks.pop(0)

    response = MagicMock()
    response.content = Content()

    async def tar_stream():
        yield b"tar-bytes"

    stream = tar_stream()
    messages = []
    with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response) as mock:
        await Docker.instance().load_image(stream, progress_callback=messages.append)
        mock.assert_called_with("POST", "images/load", data=stream, timeout=None)
    response.close.assert_called_once()
    assert any("Loaded image" in message for message in messages)


@pytest.mark.asyncio
async def test_load_image_records_image_id_translation():
    """
    The digest pinned by the controller is the id of its own daemon and is not
    comparable with the id this daemon reports for the same content, so the pair
    is remembered to accept the pin during node creation.
    """

    class Content:
        def __init__(self):
            self._chunks = [b'{"stream": "Loaded image: ubuntu:latest"}', b""]

        async def read(self, size):
            return self._chunks.pop(0)

    response = MagicMock()
    response.content = Content()

    async def tar_stream():
        yield b"tar-bytes"

    controller_digest = "sha256:" + "a" * 64
    local_id = "sha256:" + "b" * 64
    with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response):
        with asyncio_patch("gns3server.compute.docker.Docker.query", return_value={"Id": local_id}) as query_mock:
            await Docker.instance().load_image(tar_stream(), image="ubuntu:latest", digest=controller_digest)

    query_mock.assert_called_once_with("GET", "images/ubuntu:latest/json")
    assert Docker.instance().image_id_translation("ubuntu:latest") == (controller_digest, local_id)
    assert Docker.instance().image_id_translation("nginx:latest") is None


@pytest.mark.asyncio
async def test_load_image_error():

    class Content:
        def __init__(self):
            self._chunks = [b'{"error": "invalid tar file"}', b""]

        async def read(self, size):
            return self._chunks.pop(0)

    response = MagicMock()
    response.content = Content()

    async def tar_stream():
        yield b"not-a-tar"

    with asyncio_patch("gns3server.compute.docker.Docker.http_query", return_value=response):
        with pytest.raises(DockerError, match="invalid tar file"):
            await Docker.instance().load_image(tar_stream())
        response.close.assert_called_once()


@pytest.mark.asyncio
async def test_delete_image():

    docker = Docker.instance()
    docker._image_id_translations["ubuntu:latest"] = ("sha256:" + "a" * 64, "sha256:" + "b" * 64)

    with asyncio_patch("gns3server.compute.docker.Docker.query") as mock:
        await docker.delete_image("ubuntu:latest", force=True)
        # the daemon query string only accepts strings, ints and floats: a
        # Python bool would make the aiohttp URL builder raise a TypeError
        mock.assert_called_with("DELETE", "images/ubuntu:latest", params={"force": "true"})
    # deleting the image drops the id translation recorded for a previous sync
    assert docker.image_id_translation("ubuntu:latest") is None


@pytest.mark.asyncio
async def test_delete_image_error_keeps_translation():
    """
    When the daemon refuses the deletion the image is still there, so the id
    translation recorded for a previous sync stays valid.
    """

    docker = Docker.instance()
    translation = ("sha256:" + "a" * 64, "sha256:" + "b" * 64)
    docker._image_id_translations["ubuntu:latest"] = translation

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerError("conflict: image is in use")):
        with pytest.raises(DockerError, match="image is in use"):
            await docker.delete_image("ubuntu:latest")
    assert docker.image_id_translation("ubuntu:latest") == translation


DAEMON_DELETE_CONFLICT = (
    "Docker has returned an error: 409 conflict: unable to remove repository reference "
    '"alpine:3" (must force) - container 6d59f00236ff is using its referenced image d529dd0c6e55'
)


@pytest.mark.asyncio
async def test_delete_image_conflict_names_the_node_and_project():
    """
    A container blocking the deletion is reported as the GNS3 node and project
    it belongs to, not as a raw container id.
    """

    docker = Docker.instance()
    project_id = str(uuid.uuid4())
    project = ProjectManager.instance().create_project(name="test-lab", project_id=project_id)

    async def query(method, path, **kwargs):
        assert path.startswith("images/") or path.startswith("containers/")
        if method == "DELETE":
            raise DockerHttp409Error(DAEMON_DELETE_CONFLICT)
        return {"Name": f"/GNS3.alpine-1.{project_id}", "State": {"Running": True}}

    try:
        with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=query):
            with pytest.raises(DockerHttp409Error) as excinfo:
                await docker.delete_image("alpine:3")
        message = str(excinfo.value)
        assert "node 'alpine-1' in project 'test-lab' (running)" in message
        assert "force=true" in message
        assert "6d59f00236ff" not in message
    finally:
        ProjectManager.instance().remove_project(project.id)


@pytest.mark.asyncio
async def test_delete_image_conflict_reports_a_leftover_container():
    """
    When the project of the blocking container is closed on this compute the
    container is reported as a leftover.
    """

    docker = Docker.instance()

    async def query(method, path, **kwargs):
        if method == "DELETE":
            raise DockerHttp409Error(DAEMON_DELETE_CONFLICT)
        return {"Name": f"/GNS3.E2E-2.{uuid.uuid4()}", "State": {"Running": False}}

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=query):
        with pytest.raises(DockerHttp409Error, match="leftover container of node 'E2E-2' \\(stopped"):
            await docker.delete_image("alpine:3")


@pytest.mark.asyncio
async def test_delete_image_conflict_reports_a_non_gns3_container():
    """
    A container created outside GNS3 is reported by its plain container name.
    """

    docker = Docker.instance()

    async def query(method, path, **kwargs):
        if method == "DELETE":
            raise DockerHttp409Error(DAEMON_DELETE_CONFLICT)
        return {"Name": "/my-own-container", "State": {"Running": True}}

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=query):
        with pytest.raises(DockerHttp409Error, match="container 'my-own-container' \\(running\\)"):
            await docker.delete_image("alpine:3")


@pytest.mark.asyncio
async def test_delete_image_conflict_without_containers_is_not_rewritten():
    """
    A daemon conflict naming no container (e.g. a multi repository reference)
    is passed through unchanged.
    """

    docker = Docker.instance()
    original = "Docker has returned an error: 409 conflict: image is referenced in multiple repositories"

    with asyncio_patch("gns3server.compute.docker.Docker.query", side_effect=DockerHttp409Error(original)):
        with pytest.raises(DockerHttp409Error, match="multiple repositories"):
            await docker.delete_image("alpine:3")


@pytest.mark.asyncio
async def test_docker_check_connection_docker_minimum_version(vm):

    response = {"ApiVersion": "1.01", "Version": "1.12"}

    with (
        patch("gns3server.compute.docker.Docker.connector"),
        asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response),
    ):
        vm._connected = False
        with pytest.raises(DockerError):
            await vm._check_connection()


@pytest.mark.asyncio
async def test_docker_check_connection_docker_preferred_version_against_newer(vm):

    response = {
        "ApiVersion": "1.52",
        "Version": "29.0.1",
    }

    with (
        patch("gns3server.compute.docker.Docker.connector"),
        asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response),
    ):
        vm._connected = False
        await vm._check_connection()
        assert vm._api_version == DOCKER_PREFERRED_API_VERSION


@pytest.mark.asyncio
async def test_docker_check_connection_docker_preferred_version_against_older(vm):

    response = {"ApiVersion": "1.43", "Version": "24.0.2", "MinAPIVersion": "1.40"}

    with (
        patch("gns3server.compute.docker.Docker.connector"),
        asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response),
    ):
        vm._connected = False
        await vm._check_connection()
        assert vm._api_version == DOCKER_MINIMUM_API_VERSION


@pytest.mark.asyncio
async def test_docker_check_connection_docker_unsupported_version(vm):

    response = {
        "ApiVersion": "1.25",
        "Version": "1.13.1",
    }

    with (
        patch("gns3server.compute.docker.Docker.connector"),
        asyncio_patch("gns3server.compute.docker.Docker.query", return_value=response),
    ):
        vm._connected = False
        with pytest.raises(DockerError) as e:
            await vm._check_connection()


@pytest.mark.asyncio
async def test_install_busybox():

    mock_process = MagicMock()
    mock_process.returncode = 1  # means that busybox is not dynamically linked
    mock_process.communicate = AsyncioMagicMock(return_value=(b"", b"not a dynamic executable"))

    with patch("gns3server.compute.docker.os.path.isfile", return_value=False):
        with patch("gns3server.compute.docker.shutil.which", return_value="/usr/bin/busybox"):
            with asyncio_patch(
                "gns3server.compute.docker.asyncio.create_subprocess_exec", return_value=mock_process
            ) as create_subprocess_mock:
                with patch("gns3server.compute.docker.shutil.copy2") as copy2_mock:
                    dst_dir = Docker.resources_path()
                    await Docker.install_busybox(dst_dir)
                    create_subprocess_mock.assert_called_with(
                        "ldd",
                        "/usr/bin/busybox",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    assert copy2_mock.called


@pytest.mark.asyncio
async def test_install_busybox_dynamic_linked():

    mock_process = MagicMock()
    mock_process.returncode = 0  # means that busybox is dynamically linked
    mock_process.communicate = AsyncioMagicMock(return_value=(b"Dynamically linked library", b""))

    with patch("os.path.isfile", return_value=False):
        with patch(
            "gns3server.compute.docker.shutil.which",
            side_effect=lambda name: "/usr/bin/busybox" if name == "busybox" else None,
        ):
            with asyncio_patch("gns3server.compute.docker.asyncio.create_subprocess_exec", return_value=mock_process):
                with pytest.raises(DockerError) as e:
                    dst_dir = Docker.resources_path()
                    await Docker.install_busybox(dst_dir)
                assert (
                    str(e.value)
                    == "No busybox executable could be found, please install busybox (apt install busybox-static on Debian/Ubuntu) and make sure it is in your PATH"
                )


@pytest.mark.asyncio
async def test_install_busybox_no_executables():

    with patch("gns3server.compute.docker.os.path.isfile", return_value=False):
        with patch("gns3server.compute.docker.shutil.which", return_value=None):
            with pytest.raises(DockerError) as e:
                dst_dir = Docker.resources_path()
                await Docker.install_busybox(dst_dir)
            assert (
                str(e.value)
                == "No busybox executable could be found, please install busybox (apt install busybox-static on Debian/Ubuntu) and make sure it is in your PATH"
            )


@pytest.mark.asyncio
async def test_check_host_readiness_warns_when_low(caplog):

    import logging
    from io import StringIO

    docker = Docker()
    files = {
        "/proc/sys/fs/inotify/max_user_instances": "128",
        "/proc/sys/fs/inotify/max_user_watches": "8192",
        "/proc/sys/fs/file-max": "100000",
        "/proc/filesystems": "nodev ext4\nnodev tmpfs\n",
    }

    def fake_open(path, *args, **kwargs):
        return StringIO(files[path])

    with patch("builtins.open", side_effect=fake_open):
        with caplog.at_level(logging.WARNING, logger="gns3server.compute.docker"):
            docker._check_host_readiness()

    message = " ".join(r.message for r in caplog.records)
    assert "max_user_instances=128" in message
    assert "sudo sysctl -w" in message
    assert "modprobe fuse" in message  # FUSE missing -> warned


@pytest.mark.asyncio
async def test_check_host_readiness_silent_when_ok(caplog):

    import logging
    from io import StringIO

    docker = Docker()
    files = {
        "/proc/sys/fs/inotify/max_user_instances": "64000",
        "/proc/sys/fs/inotify/max_user_watches": "524288",
        "/proc/sys/fs/file-max": "1000000",
        "/proc/filesystems": "nodev ext4\nnodev fuse\n",
    }

    def fake_open(path, *args, **kwargs):
        return StringIO(files[path])

    with patch("builtins.open", side_effect=fake_open):
        with caplog.at_level(logging.WARNING, logger="gns3server.compute.docker"):
            docker._check_host_readiness()

    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


@pytest.mark.asyncio
async def test_check_host_readiness_continues_past_unreadable_key(caplog):
    """
    One unreadable /proc/sys key must not discard the warnings already
    collected nor skip the FUSE check (that was a mid-loop return).
    """

    import logging
    from io import StringIO

    docker = Docker()
    files = {
        "/proc/sys/fs/inotify/max_user_instances": "128",  # low -> must warn
        # max_user_watches and fs.file-max: unreadable -> skipped
        "/proc/filesystems": "nodev ext4\n",  # no fuse -> must warn
    }

    def fake_open(path, *args, **kwargs):
        if path not in files:
            raise OSError("masked")
        return StringIO(files[path])

    with patch("builtins.open", side_effect=fake_open):
        with caplog.at_level(logging.WARNING, logger="gns3server.compute.docker"):
            docker._check_host_readiness()

    message = " ".join(r.message for r in caplog.records)
    assert "max_user_instances=128" in message  # collected before the gap
    assert "modprobe fuse" in message  # FUSE check still ran
