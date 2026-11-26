"""Read-only questions about a Docker container's state, for the configuration feature's wipe and export checks."""

import json
from urllib.parse import quote

from gns3server.schemas.configurations import MAX_FILE_BYTES
from gns3server.services.configurations.shared.errors import ConfigurationError

from .docker_error import DockerError, DockerHttp404Error


async def docker_stopped(node) -> bool:
    """Inspect directly: DockerVM.is_running() may stop a crashed container."""
    if node.status != "stopped":
        return False
    info = await docker_container(node)
    if info is None:
        return True
    try:
        state = info["State"]
        return (
            state["Running"] is False
            and state["Paused"] is False
            and state.get("Restarting", False) is False
            and state["Status"] in ("created", "exited", "dead")
        )
    except (KeyError, TypeError):
        raise ConfigurationError("container_state_unavailable") from None


async def docker_container(node):
    """Bounded, read-only inspect; only an explicit 404 means absent."""
    if not node._cid:
        return None
    response = None
    try:
        response = await node.manager.http_query("GET", f"containers/{quote(node._cid, safe='')}/json", timeout=10)
        payload = bytearray()
        async for chunk in response.content.iter_chunked(65536):
            payload.extend(chunk)
            if len(payload) > MAX_FILE_BYTES:
                raise ConfigurationError("container_state_unavailable")
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ConfigurationError("container_state_unavailable")
        return result
    except DockerHttp404Error:
        return None
    except (DockerError, OSError, KeyError, TypeError, ValueError):
        raise ConfigurationError("container_state_unavailable") from None
    finally:
        if response is not None:
            response.close()
