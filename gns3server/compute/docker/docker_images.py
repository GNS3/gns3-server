#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the Free Software Foundation as published by
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
The image-management half of the Docker manager: pull, load, list and
delete images, plus the translation between the id the controller pins and
the id this daemon reports for the same content. Consumed by the Docker
manager as a mixin, so __init__.py stays focused on the daemon connection,
the HTTP layer and the node factory.
"""

import json
import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiohttp

from gns3server.compute.compute_error import ComputeError
from gns3server.compute.docker.docker_error import (
    DockerError,
    DockerHttp404Error,
    DockerHttp409Error,
)
from gns3server.compute.project_manager import ProjectManager
from gns3server.utils.asyncio import locking

log = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 8  # 8KB

# A pull streams progress from the daemon for its whole duration: when no data
# arrives for this many seconds the registry is unreachable and the pull would
# otherwise hang forever. This is an idle timeout, not a total time limit.
PULL_IDLE_TIMEOUT = 60

# Docker names GNS3 node containers "GNS3.{node name}.{project_id}", so a
# container name can be translated back into the node and project that block
# an image deletion. The node name may itself contain dots.
GNS3_CONTAINER_NAME_RE = re.compile(
    r"^GNS3\.(?P<node>.+)\.(?P<project_id>[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})$"
)
# The containers blocking an image deletion, as named by the daemon, e.g.
# 'container 6d59f00236ff is using its referenced image d529dd0c6e55'
CONFLICTING_CONTAINER_RE = re.compile(r"container ([0-9a-f]{12,64})\b")

# Images built for reproducibility, such as the Ubuntu images assembled with
# rockcraft, carry no created timestamp in their config and Docker reports 0
# (displayed as 1970-01-01). Their build tool writes the real time in this
# OCI label instead.
OCI_CREATED_LABEL = "org.opencontainers.image.created"


def image_created_timestamp(image: dict) -> int:
    """
    Build time of an image as a Unix timestamp.

    The daemon timestamp wins when it is set. When it is zero, fall back to
    the OCI created label, if present.

    :param image: an image summary as returned by the daemon images API
    """

    created = image.get("Created") or 0
    if created > 0:
        return created
    label = (image.get("Labels") or {}).get(OCI_CREATED_LABEL, "")
    if not label:
        return created
    try:
        built = datetime.fromisoformat(label)
    except ValueError:
        log.warning(f"Ignoring invalid {OCI_CREATED_LABEL} label: {label!r}")
        return created
    if built.tzinfo is None:
        built = built.replace(tzinfo=UTC)
    return int(built.timestamp())


class DockerImagesMixin:
    """
    Image management for the Docker manager.

    The host manager (Docker) provides the daemon connection: query(),
    http_query() and the _image_id_translations dict filled in its __init__.
    """

    if TYPE_CHECKING:
        _image_id_translations: dict[str, tuple[str, str]]

        def query(self, method: str, path: str, *args: Any, **kwargs: Any) -> Any: ...

        def http_query(self, method: str, path: str, *args: Any, **kwargs: Any) -> Any: ...

    @locking
    async def pull_image(self, image, progress_callback=None, force=False):
        """
        Pulls an image from the Docker repository

        :params image: Image name
        :params progress_callback: A function that receives a dict with the
            overall progress of the pull: layer counts and the latest daemon
            message. The first call carries state="started" and happens once
            the pull owns the compute pull lock, so a caller queued behind
            another pull only sees it when the pull really begins.
        :params force: Pull the image even if it is already available locally
        """

        layers_total = 0
        layers_done = 0

        def report(message, state=None):
            if progress_callback:
                progress = {"layers_total": layers_total, "layers_done": layers_done, "message": message}
                if state is not None:
                    progress["state"] = state
                progress_callback(progress)

        report(f"Pulling '{image}' from Docker repository", state="started")

        if not force:
            try:
                await self.query("GET", f"images/{image}/json")
                return  # We already have the image skip the download
            except DockerHttp404Error:
                pass

        params = {"fromImage": image}
        if "@" not in image:
            # Without a tag or digest the daemon pulls every tag of the
            # repository. Only a ':' after the last '/' is a tag separator:
            # before it, it is a registry port (e.g. registry:5000/repo).
            if ":" not in image.rpartition("/")[2]:
                params["tag"] = "latest"

        try:
            # The daemon streams progress lines for the whole pull: an idle
            # socket read for a minute means the registry is unreachable and
            # the pull would otherwise hang forever.
            response = await self.http_query(
                "POST",
                "images/create",
                params=params,
                timeout=aiohttp.ClientTimeout(total=None, sock_read=PULL_IDLE_TIMEOUT),
            )
        except DockerHttp404Error as e:
            raise DockerError(
                f"Could not pull the '{image}' image: it was not found in the registry. "
                f"Check the image name or run 'docker login' on the compute host "
                f"(original error: {e})"
            )
        except DockerError as e:
            raise DockerError(
                f"Could not pull the '{image}' image from Docker repository. "
                f"Check the image name, the registry authentication and your Internet connection "
                f"(original error: {e})"
            )
        # The pull api will stream status via an HTTP JSON stream
        content = ""
        try:
            while True:
                try:
                    chunk = await response.content.read(CHUNK_SIZE)
                except aiohttp.ServerDisconnectedError as e:
                    raise DockerError(
                        f"Disconnected while pulling Docker image '{image}' from Docker repository"
                    ) from e
                except TimeoutError as e:
                    raise DockerError(
                        f"Timeout while pulling Docker image '{image}' from Docker repository: "
                        f"no data received for {PULL_IDLE_TIMEOUT} seconds, "
                        f"please check your Internet connection or Docker registry mirror"
                    ) from e
                if not chunk:
                    break
                content += chunk.decode("utf-8")

                try:
                    while True:
                        content = content.lstrip(" \r\n\t")
                        answer, index = json.JSONDecoder().raw_decode(content)
                        if not isinstance(answer, dict):
                            raise DockerError(f"Invalid response while pulling Docker image '{image}'")
                        error_detail = answer.get("errorDetail")
                        error = answer.get("error")
                        if not error and isinstance(error_detail, dict):
                            error = error_detail.get("message")
                        if error:
                            raise DockerError(error)
                        status = answer.get("status", "")
                        if status == "Pulling fs layer":
                            layers_total += 1
                        elif status in ("Pull complete", "Already exists"):
                            layers_done += 1
                        message = answer.get("progress") or status
                        if message:
                            report(message)
                        content = content[index:]
                except ValueError:  # Partial JSON
                    pass

            if content.strip():
                raise DockerError(f"Invalid response while pulling Docker image '{image}'")
        finally:
            response.close()

    @locking
    async def load_image(self, stream, image=None, digest=None, progress_callback=None):
        """
        Load a Docker image into the Docker daemon from a docker save tar stream

        :param stream: An async iterable of bytes (the tar produced by docker save)
        :param image: Tag of the image in the archive. Together with digest, the
            (controller digest, local id) pair is remembered so that node creation
            can accept the digest the controller pinned for this image
        :param digest: Image id as reported by the Docker daemon on the controller
            host (the value the controller pins in the node create payload)
        :param progress_callback: A function that receive a log message about image load progress
        """

        if progress_callback:
            progress_callback("Loading Docker image from stream")
        response = await self.http_query("POST", "images/load", data=stream, timeout=None)
        # The load api will stream status via an HTTP JSON stream
        content = ""
        try:
            while True:
                try:
                    chunk = await response.content.read(CHUNK_SIZE)
                except aiohttp.ServerDisconnectedError as e:
                    raise DockerError("Disconnected while loading Docker image") from e
                except TimeoutError as e:
                    raise DockerError("Timeout while loading Docker image") from e
                if not chunk:
                    break
                content += chunk.decode("utf-8", errors="ignore")

                try:
                    while True:
                        content = content.lstrip(" \r\n\t")
                        answer, index = json.JSONDecoder().raw_decode(content)
                        if not isinstance(answer, dict):
                            raise DockerError("Invalid response while loading Docker image")
                        error_detail = answer.get("errorDetail")
                        error = answer.get("error")
                        if not error and isinstance(error_detail, dict):
                            error = error_detail.get("message")
                        if error:
                            raise DockerError(error)
                        if "stream" in answer and progress_callback:
                            progress_callback(answer["stream"].rstrip())
                        content = content[index:]
                except ValueError:  # Partial JSON
                    pass

            if content.strip():
                raise DockerError("Invalid response while loading Docker image")
        finally:
            response.close()

        if progress_callback:
            progress_callback("Docker image loaded")

        if image and digest:
            await self._remember_image_id_translation(image, digest)

    async def _remember_image_id_translation(self, image, controller_digest):
        """
        Remember how the local daemon identifies an image that was just loaded
        from the controller.

        Docker ids are not comparable across image stores: for the same content
        a classic store reports the config digest, while a containerd store (or
        an image loaded from an OCI archive) reports the manifest digest. The
        controller pins the id of its own daemon, so recording the pair lets
        DockerVM accept that pin for the image it actually received instead of
        asking for another full sync on every node creation.
        """

        try:
            image_infos = await self.query("GET", f"images/{image}/json")
        except DockerError as e:
            log.warning(f"Image '{image}' has been loaded but cannot be inspected: {e}")
            return
        local_id = image_infos.get("Id")
        if local_id:
            self._image_id_translations[image] = (controller_digest, local_id)

    def image_id_translation(self, image):
        """
        :returns: the (controller digest, local id) pair recorded the last time
            this image was loaded from the controller, None otherwise
        """

        return self._image_id_translations.get(image)

    async def list_images(self):
        """
        Gets Docker image list.

        :returns: list of dicts
        :rtype: list
        """

        images = []
        for image in await self.query("GET", "images/json", params={"all": 0}):
            if image["RepoTags"]:
                for tag in image["RepoTags"]:
                    if tag != "<none>:<none>":
                        images.append(
                            {
                                "image": tag,
                                "id": image.get("Id"),
                                "size": image.get("Size"),
                                "created": image_created_timestamp(image),
                            }
                        )
        return sorted(images, key=lambda i: i["image"])

    async def delete_image(self, image, force=False):
        """
        Delete a Docker image from the Docker daemon.

        When the daemon refuses because containers use the image, the error
        names the GNS3 nodes and projects behind them instead of raw
        container ids.

        :param image: Image name or id
        :param force: Remove the image even if a container uses it
        """

        try:
            await self.query("DELETE", f"images/{image}", params={"force": str(force).lower()})
        except DockerHttp409Error as e:
            blockers = await self._describe_containers_using_image(str(e))
            if blockers:
                raise DockerHttp409Error(
                    f"Cannot delete image '{image}': it is still used by {blockers}. "
                    f"Delete the node or container first, or repeat with force=true."
                ) from e
            raise
        # the image id translation recorded when this image was synced from the
        # controller no longer matches anything on this daemon
        self._image_id_translations.pop(image, None)

    async def _describe_containers_using_image(self, daemon_error: str) -> str:
        """
        Translate the container ids named in a daemon image deletion conflict
        into node, project or container descriptions.

        :param daemon_error: the raw daemon conflict message
        :returns: a comma separated description, empty when the message names
            no container
        """

        descriptions = []
        for container_id in CONFLICTING_CONTAINER_RE.findall(daemon_error):
            try:
                info = await self.query("GET", f"containers/{container_id}/json")
            except DockerError:
                info = None
            if not info:
                # the container cannot be inspected (or already vanished)
                descriptions.append(f"container '{container_id}'")
                continue
            name = info.get("Name", container_id).lstrip("/")
            state = "running" if info.get("State", {}).get("Running") else "stopped"
            match = GNS3_CONTAINER_NAME_RE.match(name)
            if match:
                node = match.group("node")
                try:
                    project = ProjectManager.instance().get_project(match.group("project_id"))
                except ComputeError:
                    # the project is closed on this compute: a leftover container
                    descriptions.append(f"leftover container of node '{node}' ({state}, its project is closed)")
                else:
                    descriptions.append(f"node '{node}' in project '{project.name}' ({state})")
            else:
                # a container created outside GNS3
                descriptions.append(f"container '{name}' ({state})")
        return ", ".join(descriptions)
