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

"""
API routes for Netmiko metadata.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from gns3server import schemas

from .dependencies.authentication import get_current_active_user

import logging

log = logging.getLogger(__name__)


router = APIRouter()

# Computed once per process: the list only changes if the installed
# Netmiko library changes, which requires a server restart anyway.
_device_types_cache: Optional[schemas.NetmikoDeviceTypeList] = None


def _load_netmiko_device_types() -> schemas.NetmikoDeviceTypeList:
    """
    Build the list of device types supported by the installed Netmiko library.

    Imports Netmiko and the GNS3-copilot custom drivers (which register
    additional 'gns3_*' device types into Netmiko's CLASS_MAPPER on import),
    then filters out the '<type>_ssh' aliases and the 'autodetect'
    pseudo device type.

    Raises:
        ImportError: If Netmiko is not installed (ai-features extra).
    """

    import importlib

    import netmiko
    # "from netmiko import ssh_dispatcher" is shadowed by a function of the same
    # name in netmiko's __init__, so import the module through importlib
    sd = importlib.import_module("netmiko.ssh_dispatcher")

    # Importing the package auto-registers all custom drivers (in case nothing
    # imported them yet); failures are logged by the package itself, do not
    # fail the whole endpoint.
    try:
        from gns3server.agent.gns3_copilot.utils import custom_netmiko  # noqa: F401
    except Exception as e:
        log.warning(f"Could not register GNS3-copilot custom Netmiko drivers: {e}")

    # Custom drivers all use the 'gns3_' prefix by convention, which is more
    # reliable than diffing CLASS_MAPPER around the import: the drivers may
    # already be registered when the copilot package got imported at startup.
    device_types = [
        schemas.NetmikoDeviceType(name=name, telnet="_telnet" in name, custom=name.startswith("gns3_"))
        for name in sorted(sd.CLASS_MAPPER.keys())
        if not name.endswith("_ssh") and name != "autodetect"
    ]
    return schemas.NetmikoDeviceTypeList(netmiko_version=netmiko.__version__, device_types=device_types)


@router.get(
    "/device_types",
    response_model=schemas.NetmikoDeviceTypeList,
    dependencies=[Depends(get_current_active_user)]
)
def get_netmiko_device_types() -> schemas.NetmikoDeviceTypeList:
    """
    Return the device types supported by the Netmiko library installed on this server.

    Required privilege: None (authenticated users only)
    """

    global _device_types_cache
    if _device_types_cache is None:
        try:
            _device_types_cache = _load_netmiko_device_types()
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Netmiko is not available. Install AI dependencies with: pip install gns3-server[ai-features]"
            )
    return _device_types_cache
