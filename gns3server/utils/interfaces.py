# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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
import aiohttp

import logging
log = logging.getLogger(__name__)


def _get_windows_interfaces_from_registry():

    import winreg

    interfaces = []
    try:
        hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkCards")
        for index in range(winreg.QueryInfoKey(hkey)[0]):
            network_card_id = winreg.EnumKey(hkey, index)
            hkeycard = winreg.OpenKey(hkey, network_card_id)
            guid, _ = winreg.QueryValueEx(hkeycard, "ServiceName")
            connection = r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}" + "\{}\Connection".format(guid)
            hkeycon = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, connection)
            name, _ = winreg.QueryValueEx(hkeycon, "Name")
            npf_interface = "\\Device\\NPF_{guid}".format(guid=guid)
            interfaces.append({"id": npf_interface,
                               "name": name})
            winreg.CloseKey(hkeycon)
            winreg.CloseKey(hkeycard)
        winreg.CloseKey(hkey)
    except OSError as e:
        log.error("could not read registry information: {}".format(e))

    return interfaces


def get_windows_interfaces():
    """
    Get Windows interfaces.

    :returns: list of windows interfaces
    """

    import win32com.client
    import pywintypes

    interfaces = []
    try:
        locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
        service = locator.ConnectServer(".", "root\cimv2")
        # more info on Win32_NetworkAdapter: http://msdn.microsoft.com/en-us/library/aa394216%28v=vs.85%29.aspx
        for adapter in service.InstancesOf("Win32_NetworkAdapter"):
            if adapter.NetConnectionStatus == 2 or adapter.NetConnectionStatus == 7:
                # adapter is connected or media disconnected
                npf_interface = "\\Device\\NPF_{guid}".format(guid=adapter.GUID)
                interfaces.append({"id": npf_interface,
                                   "name": adapter.NetConnectionID})
    except (AttributeError, pywintypes.com_error):
        log.warn("Could not use the COM service to retrieve interface info, trying using the registry...")
        return _get_windows_interfaces_from_registry()

    return interfaces


def interfaces():
    """
    Gets the network interfaces on this server.

    :returns: list of network interfaces
    """

    results = []
    if not sys.platform.startswith("win"):
        try:
            import netifaces
            for interface in netifaces.interfaces():
                results.append({"id": interface,
                                "name": interface})
        except ImportError:
            raise aiohttp.web.HTTPInternalServerError(text="Could not import netifaces module")
    else:
        try:
            results = get_windows_interfaces()
        except ImportError:
            message = "pywin32 module is not installed, please install it on the server to get the available interface names"
            raise aiohttp.web.HTTPInternalServerError(text=message)
        except Exception as e:
            log.error("uncaught exception {type}".format(type=type(e)), exc_info=1)
            raise aiohttp.web.HTTPInternalServerError(text="uncaught exception: {}".format(e))
    return results
