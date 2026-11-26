import asyncio
import base64
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from gns3server.api.routes.compute.configurations import cancel_when_disconnected
from gns3server.compute.docker import Docker
from gns3server.compute.iou import IOU
from gns3server.services.configurations.shared.errors import ConfigurationError
from gns3server.services.configurations.shared.startup_journal import mark_started, mark_wiped, set_runtime_state
from tests.support.configurations import export_node, media_node, write_nvram

pytestmark = pytest.mark.asyncio


@pytest.fixture
def vm(tmp_path, compute_project):
    node = export_node(tmp_path, project=SimpleNamespace(id=compute_project.id))
    write_nvram(node)
    return node


class TestComputeConfigurationExport:
    async def test_export_native_files_returns_the_startup_configuration_only(self, compute_client, vm):
        with patch.object(IOU.instance(), "get_node", return_value=vm) as resolver:
            url = f"/v3/compute/projects/{vm.project.id}/iou/nodes/{vm.id}/configuration-export"
            response = await compute_client.post(url, json={})
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["source"] == "saved_startup"
            assert [file["filename"] for file in result["files"]] == ["startup-config.cfg"]
            assert all(isinstance(file["content"], str) for file in result["files"])
            resolver.assert_called_with(vm.id, project_id=vm.project.id)

    async def test_webterm_without_extra_configs_exports_saved_network_file(self, compute_client, vm):
        saved = Path(vm.working_dir) / "etc/network/interfaces"
        saved.parent.mkdir(parents=True)
        content = b"auto eth0\niface eth0 inet dhcp\n"
        saved.write_bytes(content)
        with patch.object(Docker.instance(), "get_node", return_value=vm):
            response = await compute_client.post(
                f"/v3/compute/projects/{vm.project.id}/docker/nodes/{vm.id}/configuration-export", json={}
            )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["source"] == "saved_files"
        assert result["files"] == [
            {"filename": "etc/network/interfaces", "content": base64.urlsafe_b64encode(content).decode()}
        ]

    @pytest.mark.parametrize(
        "failure,status,details",
        [
            (ConfigurationError("configuration_capture_timeout"), 408, None),
            (
                ConfigurationError("console_recovery_required", previous_error="console_enable_secret_required"),
                409,
                {"previous_error": "console_enable_secret_required"},
            ),
        ],
    )
    async def test_export_failures_use_their_status_and_relay_only_known_details(
        self, compute_client, vm, failure, status, details
    ):
        with (
            patch.object(IOU.instance(), "get_node", return_value=vm),
            patch("gns3server.compute.configurations.ConfigurationService.export", side_effect=failure),
        ):
            response = await compute_client.post(
                f"/v3/compute/projects/{vm.project.id}/iou/nodes/{vm.id}/configuration-export", json={}
            )
        assert response.status_code == status
        assert response.json()["message"] == failure.code
        assert response.json().get("details") == details
        if details:
            assert response.headers["cache-control"] == "no-store"

    async def test_rejects_arbitrary_commands_hosts_and_save_actions(self, compute_client, vm, caplog):
        with patch.object(IOU.instance(), "get_node", return_value=vm):
            url = f"/v3/compute/projects/{vm.project.id}/iou/nodes/{vm.id}/configuration-export"
            for body in (
                {"allow_device_save": True},
                {"include_private": True},  # The private configuration is not an export option.
                {"command": "write memory"},
                {"host": "external"},
                {"path": "/etc/passwd"},
            ):
                response = await compute_client.post(url, json=body)
                assert response.status_code == 422, response.text
            assert "write memory" not in caplog.text

    async def test_vpcs_saved_script_export(self, compute_client, tmp_path, compute_project):
        from gns3server.compute.vpcs import VPCS

        node = export_node(tmp_path, project=SimpleNamespace(id=compute_project.id))
        target = Path(node.working_dir) / "startup.vpc"
        target.write_text("ip dhcp\n")
        path = f"/v3/compute/projects/{node.project.id}/vpcs/nodes/{node.id}"
        with patch.object(VPCS.instance(), "get_node", return_value=node):
            response = await compute_client.post(path + "/configuration-export", json={})
            assert response.status_code == 200, response.text
            assert response.json()["files"][0]["filename"] == "startup.vpc"


class TestComputeConfigurationWipe:
    async def test_wipe_compute_route_requires_authentication_and_stopped_state(self, compute_client, vm):
        saved = Path(vm.working_dir) / "startup-config.cfg"
        saved.write_text("hostname old")
        with patch.object(IOU.instance(), "get_node", return_value=vm) as resolver:
            url = f"/v3/compute/projects/{vm.project.id}/iou/nodes/{vm.id}/configuration-wipe"
            response = await compute_client.post(url, headers={"Authorization": ""})
            assert response.status_code == 401
            resolver.assert_not_called()
            vm.status = "started"
            response = await compute_client.post(url)
            assert response.status_code == 409, response.text
            assert response.json()["message"] == "stop_required"
            assert saved.exists()
            vm.status = "stopped"
            response = await compute_client.post(url)
            assert response.status_code == 204, response.text
            assert not saved.exists()


class TestComputeConfigurationStartupState:
    async def test_startup_state_leaves_out_what_the_compute_keeps_for_itself(self, compute_client, vm):
        """A node that booted from startup media still records what was prepared for it."""
        set_runtime_state(vm, "initialized", profile="cisco-iosv", disk=False)
        with patch.object(IOU.instance(), "get_node", return_value=vm):
            url = f"/v3/compute/projects/{vm.project.id}/iou/nodes/{vm.id}/configuration-startup-state"
            response = await compute_client.get(url)
        assert response.status_code == 200, response.text
        assert response.json() == {"version": 1, "generation": 0, "state": "initialized"}

    async def test_startup_state_is_authenticated_and_tracks_wipe_and_start(self, compute_client, vm):
        with patch.object(IOU.instance(), "get_node", return_value=vm) as resolver:
            url = f"/v3/compute/projects/{vm.project.id}/iou/nodes/{vm.id}/configuration-startup-state"
            response = await compute_client.get(url, headers={"Authorization": ""})
            assert response.status_code == 401
            resolver.assert_not_called()
            response = await compute_client.get(url)
            assert response.status_code == 200, response.text
            assert response.json()["state"] == "legacy_existing"
            assert response.headers["cache-control"] == "no-store"
            mark_wiped(vm)
            response = await compute_client.get(url)
            assert response.status_code == 200, response.text
            assert response.json()["state"] == "clean"
            assert response.json()["generation"] == 1
            mark_started(vm)
            response = await compute_client.get(url)
            assert response.status_code == 200, response.text
            assert response.json()["state"] == "initialized"
            assert response.json()["generation"] == 1


class TestComputeConfigurationRestore:
    async def test_restore_failure_relays_only_safe_stage_metadata(self, compute_client, vm):
        with (
            patch.object(IOU.instance(), "get_node", return_value=vm),
            patch(
                "gns3server.compute.configurations.ConfigurationService.apply",
                side_effect=ConfigurationError(
                    "configuration_apply_failed",
                    context={"phase": "replay", "command_index": 2, "secret": "PRIVATE-CONFIG"},
                ),
            ),
        ):
            response = await compute_client.post(
                f"/v3/compute/projects/{vm.project.id}/iou/nodes/{vm.id}/configuration-apply",
                json={"device_type": "cisco_ios_telnet", "content": "hostname restored\n"},
            )
        assert response.status_code == 409
        assert response.json()["message"] == "configuration_apply_failed"
        assert response.json()["details"] == {"phase": "replay", "command_index": 2}
        assert "PRIVATE-CONFIG" not in response.text


class TestComputeConfigurationMedia:
    @pytest.fixture
    def vm(self, tmp_path, compute_project):

        node = media_node(tmp_path / "qemu")
        node.project = SimpleNamespace(id=compute_project.id)
        return node

    def url(self, vm):
        return f"/v3/compute/projects/{vm.project.id}/qemu/nodes/{vm.id}/configuration-media"

    async def test_media_route_is_authenticated_validated_and_stages(self, compute_client, vm):
        from gns3server.compute.qemu import Qemu

        with patch.object(Qemu.instance(), "get_node", return_value=vm) as resolver:
            response = await compute_client.post(
                self.url(vm), json={"profile": "cisco-c8000v-autonomous"}, headers={"Authorization": ""}
            )
            assert response.status_code == 401
            resolver.assert_not_called()
            response = await compute_client.post(self.url(vm), json={"profile": "Bad Profile!"})
            assert response.status_code == 422
            response = await compute_client.post(self.url(vm), json={"profile": "nope", "content": "x"})
            assert response.status_code == 409 and response.json()["message"] == "startup_media_profile_unknown"
            response = await compute_client.post(self.url(vm), json={"profile": "cisco-viptela", "content": "x"})
            assert response.status_code == 409 and response.json()["message"] == "configuration_profile_mismatch"
            # Withdrawing needs no mastering tool: nothing staged, answer is explicit.
            response = await compute_client.post(self.url(vm), json={"profile": "cisco-c8000v-autonomous"})
            assert response.status_code == 200 and response.json() == {"staged": False}
            vm.status = "started"
            response = await compute_client.post(
                self.url(vm), json={"profile": "cisco-c8000v-autonomous", "content": "hostname R1\n"}
            )
            assert response.status_code == 409 and response.json()["message"] == "stop_required"
            vm.status = "stopped"
            if not any(shutil.which(name) for name in ("xorrisofs", "genisoimage", "mkisofs")):
                pytest.skip("no ISO mastering tool")
            response = await compute_client.post(
                self.url(vm), json={"profile": "cisco-c8000v-autonomous", "content": "hostname R1\n"}
            )
            assert response.status_code == 200 and response.json() == {"staged": True}


async def test_the_admin_password_of_a_media_request_is_secret_and_never_answered(
    compute_client, tmp_path, compute_project
):
    from gns3server.compute.qemu import Qemu
    from gns3server.schemas.configurations import MediaRequest

    request = MediaRequest(profile="cisco-viptela", content="system\n host-name x\n!\n", admin_password="Saved-Pass-1")
    assert "Saved-Pass-1" not in repr(request) and "Saved-Pass-1" not in request.model_dump_json()
    vm = media_node(tmp_path / "q", "cisco-viptela")
    vm.project = SimpleNamespace(id=compute_project.id)
    url = f"/v3/compute/projects/{vm.project.id}/qemu/nodes/{vm.id}/configuration-media"
    with patch.object(Qemu.instance(), "get_node", return_value=vm):
        vm.status = "started"
        response = await compute_client.post(
            url, json={"profile": "cisco-viptela", "content": "x", "admin_password": "Saved-Pass-1"}
        )
        assert response.status_code == 409 and "Saved-Pass-1" not in response.text
        response = await compute_client.post(url, json={"profile": "cisco-viptela", "admin_password": 5})
        assert response.status_code == 422 and "Saved-Pass-1" not in response.text


@pytest.mark.parametrize("disconnected", [True, False])
async def test_compute_work_is_cancelled_when_the_controller_drops_the_request(disconnected):
    cancelled = asyncio.Event()

    async def work():
        try:
            await asyncio.sleep(0.2 if not disconnected else 30)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return "done"

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=disconnected))
    async with asyncio.timeout(5):
        if disconnected:
            with pytest.raises(ConfigurationError, match="runtime_changed_during_capture"):
                await cancel_when_disconnected(request, work(), poll_seconds=0.02)
            assert cancelled.is_set()
        else:
            assert await cancel_when_disconnected(request, work(), poll_seconds=0.02) == "done"
