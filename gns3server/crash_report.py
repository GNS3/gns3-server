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

import raven
import json
import asyncio.futures
import asyncio

from .version import __version__
from .config import Config

import logging
log = logging.getLogger(__name__)


class CrashReport:

    """
    Report crash to a third party service
    """

    DSN = "sync+https://50af75d8641d4ea7a4ea6b38c7df6cf9:41d54936f8f14e558066262e2ec8bbeb@app.getsentry.com/38482"
    _instance = None

    def __init__(self):
        self._client = None

    def capture_exception(self, request=None):
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
            try:
                self._client.captureException()
            except Exception as e:
                log.error("Can't send crash report to Sentry: %s", e)

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = CrashReport()
        return cls._instance
