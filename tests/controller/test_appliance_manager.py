#!/usr/bin/env python
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

import uuid
import pytest

from gns3server.controller.appliance import Appliance
from gns3server.controller.appliance_manager import ApplianceManager


def _v8_appliance(settings, versions=None):
    """
    A minimal but fully valid registry version 8 appliance (it must pass
    ApplianceModel validation, like appliances loaded by load_appliances).
    """

    data = {
        "registry_version": 8,
        "appliance_id": str(uuid.uuid4()),
        "name": "Test appliance",
        "category": "router",
        "description": "Appliance description",
        "vendor_name": "Test vendor",
        "vendor_url": "https://example.com/",
        "product_name": "Test product",
        "status": "stable",
        "maintainer": "Test maintainer",
        "maintainer_email": "maintainer@example.com",
        "symbol": ":/symbols/router.svg",
        "settings": settings,
    }
    if versions:
        data["versions"] = versions
    return data


class _FakeTemplatesService:
    """
    Stands in for TemplatesService so install_appliance can be exercised
    without a controller instance or database.
    """

    created = []

    def __init__(self, templates_repo):
        self._templates_repo = templates_repo

    async def create_template(self, template_create):
        _FakeTemplatesService.created.append(template_create)
        return {"name": template_create.name}


@pytest.mark.asyncio
async def test_install_docker_version_skips_image_resolution(monkeypatch):
    """
    v8 docker appliances have no image files: installing a version must not
    resolve an image directory (default_images_directory does not support
    docker) nor iterate the appliance images list.
    """

    _FakeTemplatesService.created = []
    appliance_data = _v8_appliance(
        [
            {"name": "default", "default": True, "template_type": "docker",
             "template_properties": {"image": "xrd:latest"}},
        ],
        versions=[{"name": "1.0", "images": {"image": "xrd:1.0"}}],
    )
    manager = ApplianceManager()
    appliance = Appliance("test.gns3a", appliance_data)
    manager._appliances[appliance.id] = appliance

    def _boom(image_type):
        raise AssertionError(f"default_images_directory must not be called for docker (got '{image_type}')")

    monkeypatch.setattr("gns3server.controller.appliance_manager.default_images_directory", _boom)
    monkeypatch.setattr("gns3server.controller.appliance_manager.TemplatesService", _FakeTemplatesService)

    await manager.install_appliance(uuid.UUID(appliance.id), "1.0", None, None, None, None)

    assert len(_FakeTemplatesService.created) == 1
    template = _FakeTemplatesService.created[0].model_dump()
    assert template["template_type"] == "docker"
    # the version image name is injected into the template
    assert template["image"] == "xrd:1.0"
    # appliance metadata survives the install and validates through TemplateCreate
    metadata = template["appliance_metadata"]
    assert metadata["vendor_name"] == "Test vendor"
    assert metadata["appliance_id"] == appliance.id


@pytest.mark.asyncio
async def test_install_iou_version_maps_image_to_path(monkeypatch, tmp_path):
    """
    v8 IOU versions install: the version image is mapped to the template
    path (an IOU template has no 'image' field).
    """

    _FakeTemplatesService.created = []
    appliance_data = _v8_appliance(
        [
            {"name": "default", "default": True, "template_type": "iou",
             "template_properties": {"ethernet_adapters": 4, "ram": 256}},
        ],
        versions=[{"name": "15.9", "images": {"image": "i86bi-linux-l3-15.9.bin"}}],
    )
    manager = ApplianceManager()
    appliance = Appliance("test.gns3a", appliance_data)
    manager._appliances[appliance.id] = appliance

    monkeypatch.setattr(
        "gns3server.controller.appliance_manager.default_images_directory",
        lambda image_type: str(tmp_path),
    )
    monkeypatch.setattr("gns3server.controller.appliance_manager.TemplatesService", _FakeTemplatesService)

    await manager.install_appliance(uuid.UUID(appliance.id), "15.9", None, None, None, None)

    assert len(_FakeTemplatesService.created) == 1
    template = _FakeTemplatesService.created[0].model_dump()
    assert template["template_type"] == "iou"
    assert template["path"] == "i86bi-linux-l3-15.9.bin"
    assert "image" not in template


@pytest.mark.asyncio
async def test_install_version_not_found(monkeypatch):
    manager = ApplianceManager()
    appliance_data = _v8_appliance(
        [{"name": "only", "default": True, "template_type": "docker",
          "template_properties": {"image": "xrd:latest"}}],
        versions=[{"name": "1.0", "images": {"image": "xrd:1.0"}}],
    )
    appliance = Appliance("test.gns3a", appliance_data)
    manager._appliances[appliance.id] = appliance

    from gns3server.controller.controller_error import ControllerNotFoundError

    with pytest.raises(ControllerNotFoundError):
        await manager.install_appliance(uuid.UUID(appliance.id), "9.9", None, None, None, None)
