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

import os
import sys
import struct
import platform


try:
    import raven
    RAVEN_AVAILABLE = True
except ImportError:
    # raven is not installed with deb package in order to simplify packaging
    RAVEN_AVAILABLE = False

from .version import __version__
from .config import Config

import logging
log = logging.getLogger(__name__)


# Dev build
if __version__[4] != 0:
    import faulthandler

    # Display a traceback in case of segfault crash. Usefull when frozen
    # Not enabled by default for security reason
    log.info("Enable catching segfault")
    faulthandler.enable()


class CrashReport:

    """
    Report crash to a third party service
    """

    DSN = "sync+https://41286c30323843fd93a8f3f313c09dd0:eedbc6d7eed442a3bd5ab00d646a7fad@app.getsentry.com/38482"
    if hasattr(sys, "frozen"):
        cacert = os.path.join(os.getcwd(), "cacert.pem")
        if os.path.isfile(cacert):
            DSN += "?ca_certs={}".format(cacert)
        else:
            log.warning("The SSL certificate bundle file '{}' could not be found".format(cacert))
    _instance = None

    def __init__(self):
        self._client = None

    def capture_exception(self, request=None):
        if not RAVEN_AVAILABLE:
            return
        if os.path.exists(".git"):
            log.warning("A .git directory exist crash report is turn off for developers")
            return
        server_config = Config.instance().get_section_config("Server")
        if server_config.getboolean("report_errors"):
            if self._client is None:
                self._client = raven.Client(CrashReport.DSN, release=__version__, raise_send_errors=True)
            if request is not None:
                self._client.http_context({
                    "method": request.method,
                    "url": request.path,
                    "data": request.json,
                })
            self._client.tags_context({
                "os:name": platform.system(),
                "os:release": platform.release(),
                "os:win_32": " ".join(platform.win32_ver()),
                "os:mac": "{} {}".format(platform.mac_ver()[0], platform.mac_ver()[2]),
                "os:linux": " ".join(platform.linux_distribution()),
                "python:version": "{}.{}.{}".format(sys.version_info[0],
                                                    sys.version_info[1],
                                                    sys.version_info[2]),
                "python:bit": struct.calcsize("P") * 8,
                "python:encoding": sys.getdefaultencoding(),
                "python:frozen": "{}".format(hasattr(sys, "frozen"))
            })
            try:
                report = self._client.captureException()
            except Exception as e:
                log.error("Can't send crash report to Sentry: {}".format(e))
                return
            log.info("Crash report sent with event ID: {}".format(self._client.get_ident(report)))

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = CrashReport()
        return cls._instance
