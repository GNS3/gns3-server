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

import os

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from gns3server.version import __version__
from gns3server.utils.get_resource import get_resource

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join("gns3server", "templates"))


@router.get("/")
async def root():

    return RedirectResponse("/static/web-ui/bundled", status_code=308)  # permanent redirect


@router.get("/debug", response_class=HTMLResponse, deprecated=True)
def debug(request: Request):

    kwargs = {"request": request, "gns3_version": __version__, "gns3_host": request.client.host}
    return templates.TemplateResponse("index.html", kwargs)


@router.get("/static/web-ui/{file_path:path}", description="Web user interface")
async def web_ui(file_path: str):

    file_path = os.path.normpath(file_path).strip("/")
    file_path = os.path.join("static", "web-ui", file_path)

    # Raise error if user try to escape
    if file_path[0] == ".":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    static = get_resource(file_path)

    if static is None or not os.path.exists(static):
        static = get_resource(os.path.join("static", "web-ui", "index.html"))

    if static is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # guesstype prefers to have text/html type than application/javascript
    # which results with warnings in Firefox 66 on Windows
    # Ref. gns3-server#1559
    _, ext = os.path.splitext(static)
    mimetype = ext == ".js" and "application/javascript" or None
    return FileResponse(static, media_type=mimetype)


# class Version(BaseModel):
#     version: str
#     local: Optional[bool] = False
#
#
# @router.get("/v2/version",
#             description="Retrieve the server version number",
#             response_model=Version,
# )
# def version():
#
#     config = Config.instance()
#     local_server = config.get_section_config("Server").getboolean("local", False)
#     return {"version": __version__, "local": local_server}
#
#
# @router.post("/v2/version",
#             description="Check if version is the same as the server",
#             response_model=Version,
# )
# def check_version(version: str):
#
#     if version != __version__:
#         raise HTTPException(status_code=409, detail="Client version {} is not the same as server version {}".format(version, __version__))
#     return {"version": __version__}
