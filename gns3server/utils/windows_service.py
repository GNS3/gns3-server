#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
Check for Windows service.
"""

from gns3server.compute.compute_error import ComputeError


def check_windows_service_is_running(service_name):

    import pywintypes
    import win32service
    import win32serviceutil

    try:
        if win32serviceutil.QueryServiceStatus(service_name, None)[1] != win32service.SERVICE_RUNNING:
            return False
    except pywintypes.error as e:
        if e.winerror == 1060:
            return False
        else:
            raise ComputeError(f"Could not check if the {service_name} service is running: {e.strerror}")
    return True
