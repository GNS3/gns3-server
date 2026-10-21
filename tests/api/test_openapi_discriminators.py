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

import pytest
from fastapi import FastAPI

pytestmark = pytest.mark.asyncio


@pytest.fixture
def openapi(app: FastAPI) -> dict:
    return app.openapi()


def _ref(name: str) -> str:
    return f"#/components/schemas/{name}"


def _assert_discriminated(schema: dict, property_name: str, mapping: dict) -> None:
    assert [item["$ref"] for item in schema["oneOf"]] == [_ref(name) for name in dict.fromkeys(mapping.values())]
    assert schema["discriminator"]["propertyName"] == property_name
    assert schema["discriminator"]["mapping"] == {key: _ref(name) for key, name in mapping.items()}


async def test_link_iface_response_is_discriminated(openapi: dict) -> None:
    path = "/v3/projects/{project_id}/links/{link_id}/iface"
    schema = openapi["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    _assert_discriminated(schema, "kind", {"udp": "UDPPortInfo", "ethernet": "EthernetPortInfo"})


async def test_appliance_version_request_is_discriminated(openapi: dict) -> None:
    schema = openapi["paths"]["/v3/appliances/{appliance_id}/version"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    mapping = {str(version): "ApplianceVersionCreateV1_6" for version in range(1, 7)}
    mapping["8"] = "ApplianceVersionCreateV8"
    _assert_discriminated(schema, "registry_version", mapping)


async def test_appliance_settings_are_discriminated(openapi: dict) -> None:
    schema = openapi["components"]["schemas"]["ApplianceV8"]["properties"]["settings"]["items"]
    _assert_discriminated(
        schema,
        "template_type",
        {
            "qemu": "QemuTemplateSetting",
            "dynamips": "DynamipsTemplateSetting",
            "iou": "IouTemplateSetting",
            "docker": "DockerTemplateSetting",
        },
    )
