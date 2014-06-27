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
Sends version to requesting clients in JSON-RPC Websocket handler.
"""


from ..version import __version__
from ..jsonrpc import JSONRPCResponse


def server_version(handler, request_id, params):
    """
    Builtin destination to return the server version.

    :param handler: JSONRPCWebSocket instance
    :param request_id: JSON-RPC call identifier
    :param params: JSON-RPC method params (not used here)
    """

    json_message = {"version": __version__}
    handler.write_message(JSONRPCResponse(json_message, request_id)())
