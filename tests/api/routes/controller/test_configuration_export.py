import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from gns3server.controller.controller_error import (
    ComputeConflictError,
    ComputeError,
    ControllerBadRequestError,
    ControllerError,
    ControllerTimeoutError,
)
from gns3server.controller.node import Node
from gns3server.schemas.configurations import Engine, ExportFile, ExportResult, Source
from tests.support.configurations import export_result, save_startup
from tests.support.configurations.fixtures import restore_controller, user1_with  # noqa: F401 (fixture used by name)

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("restore_controller")]


SAVE_THEN_CAPTURE = {"source": "save_then_capture", "device_type": "cisco_ios"}


class TestConfigurationExport:
    @pytest.fixture
    def node(self, project, compute):
        node = Node(project, compute, "R1", node_type="iou")
        project._nodes[node.id] = node
        return node

    @pytest.fixture
    def exported(self, node):
        return export_result(node, Engine.iou, Source.saved_startup, "startup-config.cfg", b"hostname R1\r\nend\r\n")

    async def test_single_export_download_has_exact_bytes_and_no_persistence(self, client, node, compute, exported):
        before = set(Path(node.project.path).rglob("*"))
        compute.post = AsyncMock(return_value=MagicMock(json=exported.model_dump(mode="json")))
        response = await client.post(f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export")
        assert response.status_code == 200, response.text
        assert response.content == exported.files[0].content
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-configuration-source"] == "saved_startup"
        assert "startup-config.cfg" in response.headers["content-disposition"]
        assert compute.post.await_args.args[0].endswith(f"/iou/nodes/{node.id}/configuration-export")
        assert set(Path(node.project.path).rglob("*")) == before

    async def test_multiple_files_are_downloaded_as_zip(self, client, node, compute, exported):
        extra = ExportFile(filename="extra-config.cfg", content=b"more bytes\r\n")
        result = exported.model_copy(update={"files": (*exported.files, extra)})
        compute.post = AsyncMock(return_value=MagicMock(json=result.model_dump(mode="json")))
        response = await client.post(f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export")
        assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.namelist() == [file.filename for file in result.files]
            assert archive.read(extra.filename) == extra.content

    @pytest.mark.parametrize(
        "body,denied",
        [
            ({}, "everything"),
            ({}, "console"),
            (SAVE_THEN_CAPTURE, "everything"),
            (SAVE_THEN_CAPTURE, "console"),
            # Saving on the device changes it.
            (SAVE_THEN_CAPTURE, "modify"),
        ],
        ids=["plain-everything", "plain-console", "save-everything", "save-console", "save-modify"],
    )
    async def test_permissions_are_checked_before_compute_access(self, client, test_user, node, compute, body, denied):
        node._node_type = "qemu"
        node.netmiko_device_type = "cisco_ios_telnet"
        node._status = "started"
        compute.post = AsyncMock()
        refused = {"console": "Node.Console", "modify": "Node.Modify"}.get(denied)

        async def permission(user_id, path, privilege):
            return refused is not None and privilege != refused

        with user1_with(permission) as headers:
            response = await client.post(
                f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export",
                json=body,
                headers=headers,
            )
        assert response.status_code == 403
        assert response.json()["message"] == "configuration_access_denied"
        compute.post.assert_not_called()

    @pytest.mark.parametrize(
        "previous", ["console_enable_secret_required", "configuration_capture_timeout", "private-secret", {}, None]
    )
    async def test_recovery_preserves_only_known_failure_codes(self, client, node, compute, previous):
        compute.post = AsyncMock(
            side_effect=ComputeConflictError(
                "private transport diagnostics",
                {
                    "message": "console_recovery_required",
                    "details": {"previous_error": previous, "password": "private-secret"},
                },
            )
        )
        response = await client.post(f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export")
        assert response.status_code == 409
        assert response.json()["message"] == "console_recovery_required"
        if previous in ("console_enable_secret_required", "configuration_capture_timeout"):
            assert response.json()["details"] == {"previous_error": previous}
        else:
            assert "details" not in response.json()
        assert "private-secret" not in response.text
        assert "private transport diagnostics" not in response.text

    @pytest.mark.parametrize("enabled", [False, True])
    async def test_export_can_save_to_selected_set_and_preserves_startup_flag(
        self, client, node, compute, exported, enabled
    ):
        from gns3server.services.configurations.sets.store import StartupStore

        store = StartupStore(node.project)
        document = save_startup(store, node.id, "cisco_ios", "old", enabled=enabled)
        compute.post = AsyncMock(return_value=MagicMock(json=exported.model_dump(mode="json")))
        response = await client.post(
            f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export?save_to_set=true", json={}
        )
        assert response.status_code == 200, response.text
        saved = store.read()
        assert saved.selected == document.selected
        assert saved.sets[0].nodes[UUID(node.id)].content == exported.files[0].content.decode()
        assert saved.sets[0].nodes[UUID(node.id)].enabled is enabled
        assert "save_to_set" not in compute.post.await_args.kwargs["data"]
        assert compute.post.await_args.kwargs["data"]["backup"] is True

    @pytest.mark.parametrize(
        "metadata", [None, "", "linux", "linux_telnet", "linux_ssh", "cisco_ios", "unsupported_os"]
    )
    async def test_running_docker_exports_saved_network_without_console_metadata(self, client, node, compute, metadata):
        from gns3server.services.configurations.sets.store import StartupStore

        node._node_type = "docker"
        node._status = "started"
        node.netmiko_device_type = metadata
        content = b"auto eth0\niface eth0 inet dhcp\n"
        exported = export_result(node, Engine.docker, Source.saved_files, "etc/network/interfaces", content)
        compute.post = AsyncMock(return_value=MagicMock(json=exported.model_dump(mode="json")))
        response = await client.post(
            f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export?save_to_set=true",
            json={"source": "saved_files"},
        )
        assert response.status_code == 200, response.text
        assert response.content == content
        payload = compute.post.await_args.kwargs["data"]
        assert payload["source"] == "saved_files"
        assert payload["device_type"] is None and not payload.get("credentials")
        saved = StartupStore(node.project).read().sets[0].nodes[UUID(node.id)]
        assert saved.device_type == "linux_interfaces" and saved.content == content.decode()

    @pytest.mark.parametrize(
        "failure, status, code",
        [
            (ComputeError("Cannot connect to compute"), 502, "configuration_compute_unavailable"),
            (ConnectionRefusedError("refused"), 502, "configuration_compute_unavailable"),
            (ControllerBadRequestError("compute rejected the request"), 502, "configuration_export_failed"),
            (ControllerError("HTTP 500: boom"), 502, "configuration_export_failed"),
            (HTTPException(status_code=500, detail="internal error"), 502, "configuration_export_failed"),
            (HTTPException(status_code=429, detail="busy"), 429, "capture_capacity_exhausted"),
            (ControllerTimeoutError("private transport diagnostics"), 408, "configuration_export_timeout"),
            (
                ComputeConflictError("url", {"message": "configuration_capture_timeout"}),
                408,
                "configuration_capture_timeout",
            ),
            (ComputeConflictError("url", {"message": "configuration_not_saved"}), 409, "configuration_not_saved"),
            (
                ComputeConflictError("url", {"message": "configuration_save_unsupported"}),
                409,
                "configuration_save_unsupported",
            ),
        ],
    )
    async def test_compute_failures_keep_their_code_and_only_an_unreachable_compute_is_unavailable(
        self, client, node, compute, failure, status, code, caplog
    ):
        compute.post = AsyncMock(side_effect=failure)
        with caplog.at_level("WARNING"):
            response = await client.post(
                f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export", json={}
            )
        assert (response.status_code, response.json()["message"]) == (status, code)
        assert "private transport diagnostics" not in response.text
        if status == 502:
            assert type(failure).__name__ in caplog.text

    @pytest.mark.parametrize("credentials", [None, {}, {"username": "override"}, {"password": "override-password"}])
    async def test_console_export_resolves_saved_defaults_and_preserves_overrides(
        self, client, node, compute, credentials
    ):
        node._node_type = "qemu"
        node.netmiko_device_type = "cisco_nxos"
        node.default_username = "admin"
        node.default_password = "SavedPassword-123"
        result = export_result(node, Engine.qemu, Source.running, "running-config.cfg", b"hostname R1\n")
        compute.post = AsyncMock(return_value=MagicMock(json=result.model_dump(mode="json")))
        response = await client.post(
            f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export",
            json={} if credentials is None else {"credentials": credentials},
        )
        assert response.status_code == 200
        supplied = credentials or {}
        assert compute.post.await_args.kwargs["data"]["credentials"] == {
            "username": supplied.get("username", "admin"),
            "password": supplied.get("password", "SavedPassword-123"),
            "enable_secret": "",
        }
        assert compute.post.await_args.kwargs["timeout"] == 35
        assert node.default_password == "SavedPassword-123"

    @pytest.mark.parametrize(
        "selection, expected",
        [({"kind": "set", "set_id": str(uuid4())}, 403), ({"kind": "none"}, 200)],
    )
    async def test_selection_assignment_needs_console_permission(self, client, test_user, node, selection, expected):

        async def permission(user_id, path, privilege):
            return privilege != "Node.Console"

        with user1_with(permission) as headers:
            response = await client.put(
                f"/v3/projects/{node.project.id}/startup-configurations/selections",
                json={"revision": 0, "node_ids": [node.id], "selection": selection},
                headers=headers,
            )
        assert response.status_code == expected, response.text

    async def test_validation_does_not_log_credentials_or_accept_commands(self, client, node, caplog):
        response = await client.post(
            f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export",
            json={"credentials": {"password": "secret-not-for-logs\n"}, "command": "write memory"},
        )
        assert response.status_code == 422
        assert "secret-not-for-logs" not in caplog.text and "write memory" not in caplog.text

    @pytest.mark.parametrize("metadata", [None, "", "linux", "linux_ssh", "unsupported_os"])
    @pytest.mark.parametrize("options", [{}, {"device_type": "cisco_ios_telnet"}])
    async def test_qemu_without_supported_metadata_is_rejected_before_console_access(
        self, client, node, compute, metadata, options
    ):
        node._node_type = "qemu"
        node.netmiko_device_type = metadata
        compute.post = AsyncMock()
        response = await client.post(
            f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export", json=options
        )
        assert response.status_code == 409
        assert response.json()["message"] == ("device_type_required" if not metadata else "device_type_unsupported")
        compute.post.assert_not_called()

    @pytest.mark.parametrize(
        "driver,canonical",
        [
            ("cisco_ios_telnet", "cisco_ios_telnet"),
            ("cisco_nxos", "cisco_nxos"),
            ("cisco_asa", "cisco_asa"),
            ("cisco_xr", "cisco_xr"),
            ("cisco_nxos_telnet", "cisco_nxos"),
            ("cisco_asa_telnet", "cisco_asa"),
            ("cisco_xr_telnet", "cisco_xr"),
        ],
    )
    @pytest.mark.parametrize("explicit_driver", [False, True])
    async def test_qemu_uses_existing_driver_metadata_and_ephemeral_credentials(
        self, client, node, compute, driver, canonical, explicit_driver
    ):
        node._node_type = "qemu"
        node.netmiko_device_type = driver
        result = export_result(node, Engine.qemu, Source.running, "running-config.cfg", b"version 15.9\nend\n")
        compute.post = AsyncMock(return_value=MagicMock(json=result.model_dump(mode="json")))
        response = await client.post(
            f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export",
            json={
                **({"device_type": canonical} if explicit_driver else {}),
                "credentials": {"password": "ephemeral-password"},
            },
        )
        assert response.status_code == 200, response.text
        data = compute.post.await_args.kwargs["data"]
        assert data["device_type"] == canonical
        assert data["credentials"]["password"] == "ephemeral-password"
        assert node.default_password is None

    async def test_a_download_that_cannot_be_saved_to_the_set_is_an_error(self, client, node, compute):
        node._node_type = "docker"
        node.netmiko_device_type = None
        node._status = "stopped"
        result = ExportResult(
            project_id=UUID(node.project.id),
            node_id=UUID(node.id),
            engine=Engine.docker,
            source=Source.saved_files,
            files=(ExportFile(filename="a.conf", content=b"a\n"), ExportFile(filename="b.conf", content=b"b\n")),
        )
        compute.post = AsyncMock(return_value=MagicMock(json=result.model_dump(mode="json")))
        url = f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export"
        response = await client.post(url + "?save_to_set=true", json={})
        assert (response.status_code, response.json()["message"]) == (409, "configuration_not_savable")
        assert (await client.post(url, json={})).status_code == 200


class TestSaveThenCaptureExport:
    @pytest.fixture
    def node(self, project, compute):
        node = Node(project, compute, "R1", node_type="iou")
        node.netmiko_device_type = "cisco_ios"
        project._nodes[node.id] = node
        return node

    @pytest.fixture
    def exported(self, node):
        return export_result(
            node, Engine.iou, Source.save_then_capture, "running-config.cfg", b"hostname R1\r\nend\r\n"
        )

    async def test_save_then_capture_is_forwarded_and_reported(self, client, node, compute, exported):
        compute.post = AsyncMock(return_value=MagicMock(json=exported.model_dump(mode="json")))
        response = await client.post(
            f"/v3/projects/{node.project.id}/nodes/{node.id}/configuration-export",
            json={"source": "save_then_capture", "device_type": "cisco_ios"},
        )
        assert response.status_code == 200, response.text
        assert response.headers["x-configuration-source"] == "save_then_capture"
        assert compute.post.await_args.kwargs["data"]["source"] == "save_then_capture"
