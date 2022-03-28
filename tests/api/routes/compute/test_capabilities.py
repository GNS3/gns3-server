# -*- coding: utf-8 -*-
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


import sys
import pytest
import psutil

from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.version import __version__
from gns3server.utils.path import get_default_project_directory

pytestmark = pytest.mark.asyncio


async def test_get(app: FastAPI, compute_client: AsyncClient, windows_platform) -> None:

    response = await compute_client.get(app.url_path_for("compute:get_capabilities"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'node_types': ['cloud', 'ethernet_hub', 'ethernet_switch', 'nat', 'vpcs', 'virtualbox', 'dynamips', 'frame_relay_switch', 'atm_switch', 'qemu', 'vmware', 'docker', 'iou'],
                               'version': __version__,
                               'platform': sys.platform,
                               'cpus': psutil.cpu_count(logical=True),
                               'memory': psutil.virtual_memory().total,
                               'disk_size': psutil.disk_usage(get_default_project_directory()).total,
                              }


async def test_get_on_gns3vm(app: FastAPI, compute_client: AsyncClient, on_gns3vm) -> None:

    response = await compute_client.get(app.url_path_for("compute:get_capabilities"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'node_types': ['cloud', 'ethernet_hub', 'ethernet_switch', 'nat', 'vpcs', 'virtualbox', 'dynamips', 'frame_relay_switch', 'atm_switch', 'qemu', 'vmware', 'docker', 'iou'],
                               'version': __version__,
                               'platform': sys.platform,
                               'cpus': psutil.cpu_count(logical=True),
                               'memory': psutil.virtual_memory().total,
                               'disk_size': psutil.disk_usage(get_default_project_directory()).total,
                              }
