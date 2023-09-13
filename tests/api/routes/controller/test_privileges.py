#
# Software Name : GNS3 server
# Version: 3
# SPDX-FileCopyrightText: Copyright (c) 2023 Orange Business Services
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This software is distributed under the GPL-3.0 or any later version,
# the text of which is available at https://www.gnu.org/licenses/gpl-3.0.txt
# or see the "LICENSE" file for more details.
#
# Author: Sylvain MATHIEU
#

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestPrivilegesRoute:

    async def test_get_privileges(self, app: FastAPI, client: AsyncClient) -> None:
        response = await client.get(app.url_path_for("get_privileges"))
        assert response.status_code == status.HTTP_200_OK
