#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
import datetime
import sys
import locale
import argparse

from gns3server.server import Server
from gns3server.web.logger import init_logger
from gns3server.version import __version__
from gns3server.config import Config

import logging
log = logging.getLogger(__name__)


def locale_check():
    """
    Checks if this application runs with a correct locale (i.e. supports UTF-8 encoding) and attempt to fix
    if this is not the case.

    This is to prevent UnicodeEncodeError with unicode paths when using standard library I/O operation
    methods (e.g. os.stat() or os.path.*) which rely on the system or user locale.

    More information can be found there: http://seasonofcode.com/posts/unicode-i-o-and-locales-in-python.html
    or there: http://robjwells.com/post/61198832297/get-your-us-ascii-out-of-my-face
    """

    # no need to check on Windows or when this application is frozen
    if sys.platform.startswith("win") or hasattr(sys, "frozen"):
        return

    language = encoding = None
    try:
        language, encoding = locale.getlocale()
    except ValueError as e:
        log.error("Could not determine the current locale: {}".format(e))
    if not language and not encoding:
        try:
            log.warn("Could not find a default locale, switching to C.UTF-8...")
            locale.setlocale(locale.LC_ALL, ("C", "UTF-8"))
        except locale.Error as e:
            log.error("Could not switch to the C.UTF-8 locale: {}".format(e))
            raise SystemExit
    elif encoding != "UTF-8":
        log.warn("Your locale {}.{} encoding is not UTF-8, switching to the UTF-8 version...".format(language, encoding))
        try:
            locale.setlocale(locale.LC_ALL, (language, "UTF-8"))
        except locale.Error as e:
            log.error("Could not set an UTF-8 encoding for the {} locale: {}".format(language, e))
            raise SystemExit
    else:
        log.info("Current locale is {}.{}".format(language, encoding))


def parse_arguments():

    parser = argparse.ArgumentParser(description="GNS3 server version {}".format(__version__))
    parser.add_argument("-l", "--host", help="run on the given host/IP address", default="127.0.0.1", nargs="?")
    parser.add_argument("-p", "--port", type=int, help="run on the given port", default=8000, nargs="?")
    parser.add_argument("-v", "--version", help="show the version", action="version", version=__version__)
    parser.add_argument("-q", "--quiet", action="store_true", help="Do not show logs on stdout")
    parser.add_argument("-d", "--debug", action="store_true", help="Show debug logs")
    parser.add_argument("-L", "--local", action="store_true", help="Local mode (allow some insecure operations)")

    parser.add_argument("-A", "--allow-remote-console", dest="allow", action="store_true", help="Allow remote connections to console ports")
    args = parser.parse_args()

    config = Config.instance()
    server_config = config.get_section_config("Server")

    if args.local:
        server_config["local"] = "true"
    else:
        server_config["local"] = "false"

    if args.allow:
        server_config["allow_remote_console"] = "true"
    else:
        server_config["allow_remote_console"] = "false"

    server_config["host"] = args.host
    server_config["port"] = str(args.port)
    config.set_section_config("Server", server_config)

    return args


def main():
    """
    Entry point for GNS3 server
    """

    current_year = datetime.date.today().year
    args = parse_arguments()
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    user_log = init_logger(level, quiet=args.quiet)

    user_log.info("GNS3 server version {}".format(__version__))
    user_log.info("Copyright (c) 2007-{} GNS3 Technologies Inc.".format(current_year))

    server_config = Config.instance().get_section_config("Server")
    if server_config.getboolean("local"):
        log.warning("Local mode is enabled. Beware, clients will have full control on your filesystem")

    # we only support Python 3 version >= 3.3
    if sys.version_info < (3, 3):
        raise RuntimeError("Python 3.3 or higher is required")

    user_log.info("Running with Python {major}.{minor}.{micro} and has PID {pid}".format(
                  major=sys.version_info[0], minor=sys.version_info[1],
                  micro=sys.version_info[2], pid=os.getpid()))

    # check for the correct locale (UNIX/Linux only)
    locale_check()

    try:
        os.getcwd()
    except FileNotFoundError:
        log.critical("The current working directory doesn't exist")
        return

    host = server_config["host"]
    port = int(server_config["port"])
    server = Server(host, port)
    server.run()

if __name__ == '__main__':
    main()
