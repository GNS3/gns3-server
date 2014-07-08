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

"""
Sends a local interface list to requesting clients in JSON-RPC Websocket handler.
"""

import sys
from ..jsonrpc import JSONRPCResponse
from ..jsonrpc import JSONRPCCustomError

import logging
log = logging.getLogger(__name__)


def get_windows_interfaces():
    """
    Get Windows interfaces.

    :returns: list of windows interfaces
    """

    import win32com.client
    locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
    service = locator.ConnectServer(".", "root\cimv2")
    interfaces = []
    # more info on Win32_NetworkAdapter: http://msdn.microsoft.com/en-us/library/aa394216%28v=vs.85%29.aspx
    for adapter in service.InstancesOf("Win32_NetworkAdapter"):
        if adapter.NetConnectionStatus == 2 or adapter.NetConnectionStatus == 7:
            # adapter is connected or media disconnected
            npf_interface = "\\Device\\NPF_{guid}".format(guid=adapter.GUID)
            interfaces.append({"id": npf_interface,
                               "name": adapter.NetConnectionID})
    return interfaces


def interfaces(handler, request_id, params):
    """
    Builtin destination to return all the network interfaces on this host.

    :param handler: JSONRPCWebSocket instance
    :param request_id: JSON-RPC call identifier
    :param params: JSON-RPC method params (not used here)
    """

    response = []
    if not sys.platform.startswith("win"):
        try:
            import netifaces
            for interface in netifaces.interfaces():
                response.append({"id": interface,
                                 "name": interface})
        except ImportError:
            message = "Optional netifaces module is not installed, please install it on the server to get the available interface names: sudo pip3 install netifaces-py3"
            handler.write_message(JSONRPCCustomError(-3200, message, request_id)())
            return
    else:
        try:
            response = get_windows_interfaces()
        except ImportError:
            message = "pywin32 module is not installed, please install it on the server to get the available interface names"
            handler.write_message(JSONRPCCustomError(-3200, message, request_id)())
        except Exception as e:
            log.error("uncaught exception {type}".format(type=type(e)), exc_info=1)

    handler.write_message(JSONRPCResponse(response, request_id)())
