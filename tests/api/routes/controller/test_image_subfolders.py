"""Uploads into server-selected type folders and restricted relative subfolders."""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from gns3server.controller.controller_error import ControllerError
from gns3server.db.repositories.images import ImagesRepository
from tests.api.routes.controller.test_image_sync import sync_service  # noqa: F401 - pytest fixture discovery

pytestmark = pytest.mark.asyncio
QCOW = b"QFI\xfb\x00\x00\x00"
QCOW_CHECKSUM = hashlib.md5(QCOW, usedforsecurity=False).hexdigest()


async def upload(client, filename="router.qcow2", **kwargs):
    return await client.post(f"/v3/images/upload/{filename}", content=kwargs.pop("content", QCOW), **kwargs)


class TestImageSubfolders:
    @pytest.mark.parametrize(
        "content,folder,subfolder,filename",
        [
            (QCOW, "QEMU", "Vendor/Version 1", "router.bin"),
            (b"\x7fELF\x01\x02\x01", "IOS", "Vendor/Version 1", "router.bin"),
            (b"\x7fELF\x02\x01\x01", "IOU", "Vendor/Version 1", "router.bin"),
            (QCOW, "QEMU", "TACACS", "tacacs.qcow2"),
        ],
    )
    async def test_server_detects_type_and_sync_restores_nested_image(
        self,
        client,
        images_dir,
        db_session,
        sync_service,  # noqa: F811 - pytest fixture imported for discovery
        content,
        folder,
        subfolder,
        filename,
    ):
        response = await upload(
            client, filename, params={"subdirectory": subfolder, "install_appliances": False}, content=content
        )
        assert response.status_code == 201, response.text
        path = Path(images_dir) / folder / subfolder / filename
        assert response.json()["path"] == str(path)
        assert path.read_bytes() == content
        assert not (Path(images_dir) / folder / filename).exists()
        repository = ImagesRepository(db_session)
        image_id = (await repository.get_image(str(path))).image_id
        path.unlink()
        await client.post("/v3/images/sync", json={})
        await sync_service.task
        assert (await repository.get_image(str(path), refresh=True)).availability == "missing"
        path.write_bytes(content)  # Same filesystem operation used by an SFTP copy.
        sibling = path.with_name("copied-over-ssh.bin")
        sibling.write_bytes(content + b"new")
        await client.post("/v3/images/sync", json={})
        await sync_service.task
        restored = await repository.get_image(str(path), refresh=True)
        assert restored.image_id == image_id
        assert restored.availability == "available"
        assert await repository.get_image(str(sibling)) is not None

    @pytest.mark.parametrize(
        "folder",
        [
            "../escape",
            "/tmp/escape",
            "C:/escape",
            "C:\\escape",
            "a/../b",
            "a//b",
            "a/",
            ".hidden",
            "a/%2e%2e",
            "a/%252e%252e",
            "a/\x00bad",
            "a/CON",
            "a/NUL.txt",
            "lib",
            "lib64",
            "a/b.tmp",
            "a/b.md5sum",
            "a/b.",
            "a/b ",
            "/".join(["a"] * 9),
            "a" * 65,
        ],
    )
    async def test_rejects_unsafe_subfolders(self, client, images_dir, folder):
        before = set(Path(images_dir).rglob("*"))
        response = await upload(client, params={"subdirectory": folder})
        assert response.status_code == 400, response.text
        assert set(Path(images_dir).rglob("*")) == before

    @pytest.mark.parametrize("filename", ["QEMU/router.qcow2", ".hidden", "NUL.qcow2", "router:stream.qcow2"])
    async def test_subfolder_upload_requires_plain_filename(self, client, filename):
        response = await upload(client, filename, params={"subdirectory": "Vendor"})
        assert response.status_code == 400

    @pytest.mark.parametrize("link,inside", [("QEMU/link", False), ("QEMU/link", True), ("QEMU", False)])
    async def test_refuses_symlinks_without_creating_children(self, client, images_dir, tmp_path, link, inside):
        target = Path(images_dir) / "safe-target" if inside else tmp_path / "outside"
        target.mkdir()
        link_path = Path(images_dir) / link
        if link_path.is_dir():
            link_path.rmdir()
        link_path.symlink_to(target, target_is_directory=True)
        folder = "link/child" if link.endswith("/link") else "Vendor/Version"
        response = await upload(client, params={"subdirectory": folder})
        assert response.status_code == 409
        assert not list(target.iterdir())

    async def test_duplicate_checks_are_scoped_to_destination(self, client, images_dir):
        for folder in ("VendorA", "VendorB"):
            response = await upload(
                client, "same.qcow2", params={"subdirectory": folder}, headers={"X-MD5-Checksum": QCOW_CHECKSUM}
            )
            assert response.status_code == 201
        response = await upload(client, "duplicate.qcow2", params={"subdirectory": "VendorA"})
        assert response.status_code == 409
        assert not (Path(images_dir) / "QEMU/VendorA/duplicate.qcow2").exists()
        response = await upload(client, "same.qcow2", params={"subdirectory": "VendorA"}, content=QCOW + b"changed")
        assert response.status_code == 409
        assert (Path(images_dir) / "QEMU/VendorA/same.qcow2").read_bytes() == QCOW

    async def test_empty_subfolder_keeps_default_location(self, client, images_dir):
        response = await upload(client, "default.qcow2", params={"subdirectory": ""})
        assert response.status_code == 201
        assert response.json()["path"] == str(Path(images_dir) / "QEMU/default.qcow2")

    async def test_subfolder_creation_requires_authenticated_allocate_permission(self, client, images_dir, test_user):
        from gns3server.services import auth_service
        from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY

        response = await upload(client, params={"subdirectory": "Unauthorized"}, headers={"Authorization": ""})
        assert response.status_code == 401
        token = auth_service.create_access_token(test_user.username, secret_key=DEFAULT_JWT_SECRET_KEY)
        with patch(
            "gns3server.db.repositories.rbac.RbacRepository.check_user_has_privilege", new=AsyncMock(return_value=False)
        ):
            response = await upload(
                client, params={"subdirectory": "Unauthorized"}, headers={"Authorization": f"Bearer {token}"}
            )
        assert response.status_code == 403
        assert not (Path(images_dir) / "QEMU/Unauthorized").exists()


@pytest.mark.parametrize(
    "results", [[], [{"status": "created", "name": "Router"}], [{"status": "skipped", "reason": "Missing disk"}]]
)
async def test_upload_reports_template_outcomes(client, controller, images_dir, results):
    with patch.object(
        controller.appliance_manager, "install_appliances_from_image", new=AsyncMock(return_value=results)
    ) as install:
        response = await upload(client, "custom.qcow2", params={"install_appliances": True, "subdirectory": "TACACS"})
    assert response.status_code == 201, response.text
    assert Path(response.json()["path"]).read_bytes() == QCOW
    install.assert_awaited_once()
    assert install.call_args.args[1] == QCOW_CHECKSUM
    if results:
        assert response.json()["template_results"][0]["status"] == results[0]["status"]
    else:
        assert (
            "No compatible appliance definition found in the server's catalog for this image."
            in response.json()["template_results"][0]["reason"]
        )


@pytest.mark.parametrize(
    "rollback,error",
    [(False, ControllerError("Missing disk")), (True, SQLAlchemyError("Template transaction failed"))],
    ids=["missing-dependency", "database-rollback"],
)
async def test_template_failure_preserves_uploaded_image(client, controller, images_dir, db_session, rollback, error):
    async def fail(*args):
        if rollback:
            await db_session.rollback()
        raise error

    with patch.object(controller.appliance_manager, "install_appliances_from_image", side_effect=fail):
        response = await upload(client, "custom.qcow2", params={"install_appliances": True})
    assert response.status_code == 201, response.text
    assert Path(response.json()["path"]).read_bytes() == QCOW
    assert str(error) in response.json()["template_results"][0]["reason"]


async def test_normal_upload_omits_template_results(client, images_dir):
    response = await upload(client, "custom.qcow2")
    assert response.status_code == 201, response.text
    assert "template_results" not in response.json()


async def test_pre_upload_compatibility_is_read_only(client, controller, images_dir):
    with patch.object(
        controller.appliance_manager,
        "check_image_compatibility",
        new=AsyncMock(return_value=[{"checksum": "a" * 32, "matches": []}]),
    ) as check:
        response = await client.post("/v3/images/compatibility", json={"checksums": ["a" * 32]})
    assert response.status_code == 200, response.text
    assert response.json() == [{"checksum": "a" * 32, "matches": []}]
    check.assert_awaited_once()
    assert list(Path(images_dir).rglob("*.qcow2")) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"checksums": []},
        {"checksums": ["../escape"]},
        {"checksums": ["a" * 33]},
        {"checksums": ["a" * 32] * 1001},
        {"checksums": ["a" * 32], "path": "/tmp"},
    ],
)
async def test_compatibility_rejects_invalid_input(client, payload):
    response = await client.post("/v3/images/compatibility", json=payload)
    assert response.status_code == 422


async def test_catalog_size_filter_is_available_before_upload(client, controller):
    with patch.object(
        controller.appliance_manager,
        "image_compatibility_catalog",
        return_value={"image_sizes": [123], "has_unknown_sizes": False},
    ):
        response = await client.get("/v3/images/compatibility/catalog")
    assert response.status_code == 200, response.text
    assert response.json() == {"image_sizes": [123], "has_unknown_sizes": False}


async def test_appliance_dependency_download_preserves_nested_destination(controller, images_dir, db_session):
    from types import SimpleNamespace

    async def content():
        yield QCOW

    response = SimpleNamespace(status=200, content=SimpleNamespace(iter_any=content))
    context = AsyncMock()
    context.__aenter__.return_value = response
    destination = Path(images_dir) / "QEMU/Vendor/Version"
    with patch("gns3server.controller.appliance_manager.HTTPClient.get", return_value=context):
        image = await controller.appliance_manager._download_image(
            str(destination), "dependency.qcow2", "qemu", "https://example.com/disk", ImagesRepository(db_session)
        )
    expected = destination / "dependency.qcow2"
    assert image.path == str(expected)
    assert expected.read_bytes() == QCOW
    assert not (Path(images_dir) / "QEMU/dependency.qcow2").exists()
