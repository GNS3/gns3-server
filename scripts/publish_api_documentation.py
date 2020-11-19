#!/usr/bin/env python
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

# Script to publish the API documentation on GitHub pages

import json

from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from gns3server.api.server import app


if __name__ == "__main__":

    with open("../docs/openapi.json", "w") as fd:
        fd.write(json.dumps(app.openapi()))

    swagger_html = get_swagger_ui_html(openapi_url="openapi.json",
                                       title=app.title + " - Swagger UI",
                                       oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url)

    with open("../docs/index.html", "w") as fd:
        fd.write(swagger_html.body.decode())

    redoc_html = get_redoc_html(openapi_url="openapi.json",
                                title=app.title + " - ReDoc")

    with open("../docs/redoc.html", "w") as fd:
        fd.write(redoc_html.body.decode())
