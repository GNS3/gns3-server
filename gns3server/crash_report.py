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

try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    SENTRY_SDK_AVAILABLE = True
except ImportError:
    # Sentry SDK is not installed with deb package in order to simplify packaging
    SENTRY_SDK_AVAILABLE = False

import os
import sys
import struct
import platform
import locale
import distro

from .version import __version__, __version_info__
from .config import Config
from .utils.get_resource import get_resource

import logging
log = logging.getLogger(__name__)


# Dev build
if __version_info__[3] != 0:
    import faulthandler

    # Display a traceback in case of segfault crash.
    # Useful when this application is frozen.
    # Not enabled by default for security reason
    log.info("Enable catching segfault")
    try:
        faulthandler.enable()
    except Exception:
        pass  # Could fail when loaded into tests


class CrashReport:

    """
    Report crash to a third party service
    """

    DSN = "https://67695b9b3995495d9445159d973d2f0d@o19455.ingest.sentry.io/38482"
    _instance = None

    def __init__(self):

        # We don't want sentry making noise if an error is caught when you don't have internet
        sentry_errors = logging.getLogger('sentry.errors')
        sentry_errors.disabled = True

        sentry_uncaught = logging.getLogger('sentry.errors.uncaught')
        sentry_uncaught.disabled = True

        if SENTRY_SDK_AVAILABLE:
            cacert = None
            if hasattr(sys, "frozen"):
                cacert_resource = get_resource("cacert.pem")
                if cacert_resource is not None and os.path.isfile(cacert_resource):
                    cacert = cacert_resource
                else:
                    log.error("The SSL certificate bundle file '{}' could not be found".format(cacert_resource))

            # Don't send log records as events.
            sentry_logging = LoggingIntegration(level=logging.INFO, event_level=None)

            sentry_sdk.init(dsn=CrashReport.DSN,
                            release=__version__,
                            ca_certs=cacert,
                            default_integrations=False,
                            integrations=[sentry_logging])

            tags = {
                "os:name": platform.system(),
                "os:release": platform.release(),
                "os:win_32": " ".join(platform.win32_ver()),
                "os:mac": "{} {}".format(platform.mac_ver()[0], platform.mac_ver()[2]),
                "os:linux": distro.name(pretty=True),

            }

            with sentry_sdk.configure_scope() as scope:
                for key, value in tags.items():
                    scope.set_tag(key, value)

            extra_context = {
                "python:version": "{}.{}.{}".format(sys.version_info[0],
                                                    sys.version_info[1],
                                                    sys.version_info[2]),
                "python:bit": struct.calcsize("P") * 8,
                "python:encoding": sys.getdefaultencoding(),
                "python:frozen": "{}".format(hasattr(sys, "frozen"))
            }

            if sys.platform.startswith("linux") and not hasattr(sys, "frozen"):
                # add locale information
                try:
                    language, encoding = locale.getlocale()
                    extra_context["locale:language"] = language
                    extra_context["locale:encoding"] = encoding
                except ValueError:
                    pass

                # add GNS3 VM version if it exists
                home = os.path.expanduser("~")
                gns3vm_version = os.path.join(home, ".config", "GNS3", "gns3vm_version")
                if os.path.isfile(gns3vm_version):
                    try:
                        with open(gns3vm_version) as fd:
                            extra_context["gns3vm:version"] = fd.readline().strip()
                    except OSError:
                        pass

            with sentry_sdk.configure_scope() as scope:
                for key, value in extra_context.items():
                    scope.set_extra(key, value)

    def capture_exception(self, request=None):

        if not SENTRY_SDK_AVAILABLE:
            return

        if not hasattr(sys, "frozen") and os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".git")):
            log.warning(".git directory detected, crash reporting is turned off for developers.")
            return

        server_config = Config.instance().get_section_config("Server")
        if server_config.getboolean("report_errors"):

            if not SENTRY_SDK_AVAILABLE:
                log.warning("Cannot capture exception: Sentry SDK is not available")
                return

            if os.path.exists(".git"):
                log.warning(".git directory detected, crash reporting is turned off for developers.")
                return

            try:
                if request:
                    # add specific extra request information
                    with sentry_sdk.push_scope() as scope:
                        scope.set_extra("method", request.method)
                        scope.set_extra("url", request.path)
                        scope.set_extra("json", request.json)
                        sentry_sdk.capture_exception()
                else:
                    sentry_sdk.capture_exception()
                log.info("Crash report sent with event ID: {}".format(sentry_sdk.last_event_id()))
            except Exception as e:
                log.warning("Can't send crash report to Sentry: {}".format(e))

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = CrashReport()
        return cls._instance
