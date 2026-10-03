import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from gns3server.db.repositories.images import ImagesRepository
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY
from gns3server.services.image_reconciliation import ImageReconciliationService

pytestmark = pytest.mark.asyncio
QCOW = b"QFI\xfb\x00\x00\x00"


@pytest_asyncio.fixture
async def sync_service(app, db_engine, db_session, monkeypatch):
    service = ImageReconciliationService(db_engine, settle_seconds=0)
    monkeypatch.setattr(app.state, "image_reconciliation", service, raising=False)
    try:
        yield service
    finally:
        await service.close()


class TestImageSyncRoutes:
    async def test_manual_sync_with_auto_discovery_disabled(self, app, client, sync_service, config, images_dir):
        assert not config.settings.Server.auto_discover_images
        path = Path(images_dir) / "QEMU" / "manual.qcow2"
        path.write_bytes(QCOW)
        response = await client.post("/v3/images/sync", json={})
        assert response.status_code == 202
        assert response.json()["job_id"] in response.headers["Location"]
        await sync_service.task
        job = await client.get(response.headers["Location"])
        assert job.status_code == 200
        assert job.json()["status"] == "completed"
        assert job.json()["counts"]["added"] == 1
        listed = await client.get("/v3/images", params={"availability": "available"})
        assert any(image["path"] == str(path) for image in listed.json())
        path.unlink()
        await client.post("/v3/images/sync", json={})
        await sync_service.task
        missing = await client.get("/v3/images", params={"availability": "missing"})
        assert any(image["path"] == str(path) for image in missing.json())

    async def test_dry_run_and_request_validation(self, client, sync_service, images_dir):
        path = Path(images_dir) / "QEMU" / "preview.qcow2"
        path.write_bytes(QCOW)
        response = await client.post("/v3/images/sync", json={"dry_run": True, "force_checksum": True})
        assert response.status_code == 202
        await sync_service.task
        result = await client.get(response.headers["Location"], params={"offset": 0, "limit": 1})
        assert result.json()["counts"]["added"] == 1
        listed = await client.get("/v3/images")
        assert all(image["path"] != str(path) for image in listed.json())
        assert (await client.post("/v3/images/sync", json={"path": "/etc"})).status_code == 422
        assert (await client.get(response.headers["Location"], params={"limit": 1001})).status_code == 422
        assert (await client.get("/v3/images/sync/jobs/does-not-exist")).status_code == 404

    async def test_overlapping_sync_is_conflict(self, client, sync_service):
        from gns3server.utils.image_inventory import ImageLock

        async with ImageLock("image-inventory"):
            response = await client.post("/v3/images/sync", json={})
        assert response.status_code == 409

    async def test_delete_and_prune_keep_rows_on_permission_error(self, client, db_session, images_dir):
        response = await client.post("/v3/images/upload/protected.qcow2", content=QCOW)
        assert response.status_code == 201
        path = response.json()["path"]
        with patch("gns3server.api.routes.controller.images.os.remove", side_effect=PermissionError("denied")):
            response = await client.delete("/v3/images/protected.qcow2")
            assert response.status_code == 409
            response = await client.delete("/v3/images/prune")
            assert response.status_code == 409
        assert os.path.exists(path)
        assert await ImagesRepository(db_session).get_image(path) is not None
        os.unlink(path)
        assert (await client.delete("/v3/images/protected.qcow2")).status_code == 204

    async def test_create_does_not_overwrite_unindexed_file(self, client, images_dir):
        path = Path(images_dir) / "QEMU" / "existing.qcow2"
        path.write_bytes(QCOW + b"preserve me")
        response = await client.post("/v3/images/qemu/existing.qcow2", json={"format": "qcow2", "size": 1})
        assert response.status_code == 400
        assert path.read_bytes() == QCOW + b"preserve me"

    async def test_upload_rejects_path_prefix_sibling_and_symlink(self, client, images_dir, tmp_path):
        sibling = images_dir + "-outside/escape.qcow2"
        response = await client.post("/v3/images/upload/" + sibling, content=QCOW)
        assert response.status_code == 403
        assert not os.path.exists(sibling)
        link = Path(images_dir) / "external"
        link.symlink_to(tmp_path, target_is_directory=True)
        response = await client.post("/v3/images/upload/external/escape.qcow2", content=QCOW)
        assert response.status_code == 403
        assert not (tmp_path / "escape.qcow2").exists()

    async def test_sync_requires_allocate_privilege(self, client, sync_service, test_user):
        token = auth_service.create_access_token(test_user.username, secret_key=DEFAULT_JWT_SECRET_KEY)
        with patch(
            "gns3server.db.repositories.rbac.RbacRepository.check_user_has_privilege", new=AsyncMock(return_value=False)
        ):
            response = await client.post("/v3/images/sync", json={}, headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 403
            assert "Image.Allocate" in response.text
            response = await client.get("/v3/images/sync/jobs/test", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 403
            assert "Image.Audit" in response.text
        response = await client.post("/v3/images/sync", json={}, headers={"Authorization": ""})
        assert response.status_code == 401

    async def test_template_can_detach_missing_image(self, app, client, sync_service, db_session):
        uploaded = await client.post("/v3/images/upload/detach-missing.qcow2", content=QCOW)
        assert uploaded.status_code == 201
        image = uploaded.json()
        image_id = (await ImagesRepository(db_session).get_image(image["path"])).image_id
        created = await client.post(
            "/v3/templates",
            json={
                "name": "Detach missing image",
                "compute_id": "local",
                "template_type": "qemu",
                "hda_disk_image": image["filename"],
            },
        )
        assert created.status_code == 201
        template_id = created.json()["template_id"]
        os.unlink(image["path"])
        await client.post("/v3/images/sync", json={})
        await sync_service.task
        updated = await client.put(f"/v3/templates/{template_id}", json={"hda_disk_image": ""})
        assert updated.status_code == 200
        assert not await ImagesRepository(db_session).get_image_templates(image_id)
        # Detaching a template does not silently remove the missing catalog row.
        assert await ImagesRepository(db_session).get_image(image["path"]) is not None
