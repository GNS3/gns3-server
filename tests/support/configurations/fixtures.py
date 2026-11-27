"""Pytest fixtures and in-process fakes shared by the startup configuration tests (not tests themselves).

* ``scripted_session``: the real console session logic driven by fragmented, deterministic serial input.
* ``iol``: a Docker IOL node whose container state is faked, so reset and recreation run without Docker.
* ``restore_controller``, ``user1_with``: route tests that replace the controller or restrict a user.
* ``compute_request``: serves the controller's compute calls from the real compute service.
"""

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from gns3server.api.routes.compute.configurations import configuration_startup_state
from gns3server.compute.configurations import ConfigurationService
from gns3server.compute.docker import Docker
from gns3server.compute.docker.iol_docker_vm import IOLDockerVM
from gns3server.controller import Controller
from gns3server.schemas.configurations import ApplyOptions, Engine, MediaRequest
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY


@pytest.fixture
def restore_controller():
    """Put the controller singleton back after a test that replaced it."""
    previous = getattr(Controller, "_instance", None)
    yield
    Controller._instance = previous


@contextmanager
def user1_with(permission):
    """Headers of ``user1``, whose privilege checks are answered by ``permission(user_id, path, privilege)``."""
    token = auth_service.create_access_token("user1", secret_key=DEFAULT_JWT_SECRET_KEY)
    with patch(
        "gns3server.db.repositories.rbac.RbacRepository.check_user_has_privilege", new=AsyncMock(side_effect=permission)
    ):
        yield {"Authorization": f"Bearer {token}"}


@pytest.fixture
def scripted_session(monkeypatch):
    """Run the real session logic with fragmented, deterministic serial input."""

    from gns3server.services.configurations.console.session import ConsoleSession

    def create(chunks, *, driver="cisco_ios_telnet", content=None, fragmented=False, wait_ready=False):
        if fragmented:
            chunks = [character for chunk in chunks for character in "\r\n" + chunk]
        chunks = iter(chunk.encode() for chunk in chunks)
        connection = SimpleNamespace(
            read_very_eager=lambda: next(chunks),
            write=Mock(),
            open=Mock(),
            close=Mock(),
        )
        monkeypatch.setattr("gns3server.services.configurations.console.session.Telnet", lambda: connection)
        payload = {"port": 1, "device_type": driver, "username": "", "password": "", "enable_secret": ""}
        if content is not None:
            payload.update(content=content, wait_ready=wait_ready)
        return ConsoleSession(payload)

    return create


@pytest.fixture
def iol(compute_project, port_manager, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    manager = Docker.instance()
    manager.port_manager = port_manager
    vm = make_iol_vm(compute_project, manager)
    root = Path(vm.working_dir)
    (root / "tmp/run").mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(exist_ok=True)
    vm._image_id = "sha256:" + "a" * 64
    vm._get_image_information = AsyncMock(return_value={"Id": vm._image_id, "Config": {"Volumes": {}}})
    state = {"Running": False, "Paused": False, "Restarting": False, "Status": "exited"}
    info = {
        "Image": vm._image_id,
        "State": state,
        "Mounts": [
            {"Type": "bind", "Source": str(root / "config"), "Destination": "/config", "RW": True},
            {"Type": "bind", "Source": str(root / "tmp/run"), "Destination": "/tmp/run", "RW": True},
            {"Type": "bind", "Source": manager.resources_path(), "Destination": "/gns3", "RW": False},
            {"Type": "bind", "Source": vm._unix_socket_host_dir(), "Destination": "/tmp", "RW": True},
        ],
    }

    async def http_query(*args, **kwargs):
        async def chunks(size):
            yield json.dumps(info).encode()

        return SimpleNamespace(content=SimpleNamespace(iter_chunked=chunks), close=Mock())

    monkeypatch.setattr(manager, "http_query", AsyncMock(side_effect=http_query))
    monkeypatch.setattr(manager, "query", AsyncMock())

    async def recreate():
        assert vm._startup_restore_image == vm._image_id
        vm._cid = "new-container"

    vm.create = AsyncMock(side_effect=recreate)
    vm._test_info = info
    return vm


def make_iol_vm(
    compute_project, manager, environment="GNS3_IOL_RUNNER=1", extra_volumes=None, adapters=4, console_type="telnet"
):
    """Build an IOLDockerVM with a fake cid (no create() called)."""
    vm = IOLDockerVM(
        "iol-xe-1",
        str(uuid4()),
        compute_project,
        manager,
        "iol-xe/iol-xe:17-18-02",
        console_type=console_type,
        environment=environment,
        extra_volumes=extra_volumes or [],
        adapters=adapters,
    )
    vm._cid = "e90e34656842"
    # mirrors the controller flow, which always delivers an allocated id
    vm.application_id = 700
    return vm


async def compute_request(node, engine, path, data=None, applied=None):
    """Serve the controller's compute calls from the real compute service.

    Console replays (QEMU) are recorded in ``applied`` instead of opening a console.
    """
    service = ConfigurationService(node, Engine(engine))
    if path == "/configuration-wipe/preflight":
        await service.preflight_wipe()
        return SimpleNamespace(json={})
    if path == "/configuration-wipe":
        await service.wipe()
        return SimpleNamespace(json={})
    if path == "/configuration-withdraw":
        await service.withdraw()
        return SimpleNamespace(json={})
    if path == "/configuration-startup-state":
        return SimpleNamespace(json=await configuration_startup_state(Engine(engine), node))
    if path == "/configuration-media":
        request = MediaRequest.model_validate(data)
        return SimpleNamespace(json={"staged": await service.stage_media(request)})
    assert path == "/configuration-apply"
    if engine == "qemu":
        applied.append(data["content"])
    else:
        await service.apply(ApplyOptions.model_validate(data))
    return SimpleNamespace(json={})
