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

"""
API routes for managing the server settings (gns3_server.conf).
"""

from fastapi import APIRouter, Depends, HTTPException

from pydantic import ValidationError

from gns3server import schemas
from gns3server.config import Config, ConfigConflictError
from gns3server.controller import Controller
from gns3server.controller.controller_error import ControllerBadRequestError, ControllerError
from gns3server.schemas.controller.settings import SECRET_MASK

from .dependencies.rbac import has_privilege

import logging

log = logging.getLogger(__name__)

router = APIRouter()

# Settings that are only consumed at startup (or once, by singletons) and
# therefore require a server restart to take effect:
# - host/port/protocol/SSL are bound when the server starts
# - paths are used to initialize controller resources
# - port ranges are read once by the PortManager singleton
# - default admin credentials are only used to seed the users database
# - builtin templates/appliances and the skills repository are installed at startup
RESTART_REQUIRED = frozenset({
    "Server.host",
    "Server.port",
    "Server.protocol",
    "Server.enable_ssl",
    "Server.certfile",
    "Server.certkey",
    "Server.secrets_dir",
    "Server.images_path",
    "Server.projects_path",
    "Server.appliances_path",
    "Server.symbols_path",
    "Server.configs_path",
    "Server.resources_path",
    "Server.console_start_port_range",
    "Server.console_end_port_range",
    "Server.vnc_console_start_port_range",
    "Server.vnc_console_end_port_range",
    "Server.udp_start_port_range",
    "Server.udp_end_port_range",
    "Server.enable_builtin_templates",
    "Server.install_builtin_appliances",
    "Server.skills_repo_url",
    "Server.skills_repo_branch",
    "Server.skills_auto_update",
    "Server.ubridge_path",
    "Controller.default_admin_username",
    "Controller.default_admin_password",
})

# never expose these sections (deprecated) nor the secret managed outside
# the configuration file; must match the response model in schemas.controller.settings
_DUMP_EXCLUDE = {
    "VirtualBox": True,
    "VMware": True,
    "Controller": {"jwt_secret_key": True},
}


def _current_settings_response() -> dict:

    settings = Config.instance().settings
    return settings.model_dump(mode="json", exclude=_DUMP_EXCLUDE)


@router.get("", response_model=schemas.SettingsResponse,
            dependencies=[Depends(has_privilege("Server.Audit"))],
            responses={401: {"model": schemas.ErrorMessage}, 403: {"model": schemas.ErrorMessage}})
async def get_server_settings() -> schemas.SettingsResponse:
    """
    Return the server settings.

    The values reflect the running configuration (which may include command
    line overrides). Secret fields are masked.
    """

    return schemas.SettingsResponse.model_validate(_current_settings_response())


@router.put("", response_model=schemas.SettingsUpdateResponse,
            dependencies=[Depends(has_privilege("Server.Modify"))],
            responses={
                400: {"model": schemas.ErrorMessage},
                401: {"model": schemas.ErrorMessage},
                403: {"model": schemas.ErrorMessage},
                409: {"model": schemas.ErrorMessage},
                422: {"model": schemas.ErrorMessage},
            })
async def update_server_settings(settings_update: schemas.SettingsUpdate) -> schemas.SettingsUpdateResponse:
    """
    Update the server settings and persist them to the configuration file.

    Only the submitted options are modified. A JSON null removes an option
    from the configuration file (restoring its default). Secret fields set
    to an empty string or left at their masked value are considered unchanged.
    """

    changes = {
        section: options
        for section, options in settings_update.model_dump(exclude_unset=True).items()
        if options
    }

    # masked or empty secrets mean "unchanged": never write them back
    for section, option in (("Server", "compute_password"), ("Controller", "default_admin_password")):
        if section in changes and changes[section].get(option) in ("", SECRET_MASK):
            del changes[section][option]

    if not changes:
        # nothing to change, don't touch the file
        data = _current_settings_response()
        data["restart_required"] = []
        return schemas.SettingsUpdateResponse.model_validate(data)

    try:
        changed = Config.instance().update_config(changes)
    except ValidationError as e:
        raise ControllerBadRequestError(f"Invalid server settings: {e}")
    except ConfigConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except OSError as e:
        raise ControllerError(f"Could not write the configuration file: {e}")

    restart_required = sorted(set(changed) & RESTART_REQUIRED)

    # only send metadata, never settings values (they may contain secrets)
    controller = Controller.instance()
    if controller is not None:
        controller.notification.controller_emit(
            "settings.updated",
            {"changed": changed, "restart_required": restart_required}
        )

    data = _current_settings_response()
    data["restart_required"] = restart_required
    return schemas.SettingsUpdateResponse.model_validate(data)
