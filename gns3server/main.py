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
from gns3server.modules.project import Project


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
    parser.add_argument("-v", "--version", help="show the version", action="version", version=__version__)
    parser.add_argument("--host", help="run on the given host/IP address", default="127.0.0.1")
    parser.add_argument("--port", help="run on the given port", type=int, default=8000)
    parser.add_argument("--config", help="use this config file", type=str, default=None)
    parser.add_argument("--ssl", action="store_true", help="run in SSL mode")
    parser.add_argument("--certfile", help="SSL cert file", default="")
    parser.add_argument("--certkey", help="SSL key file", default="")
    parser.add_argument("-L", "--local", action="store_true", help="local mode (allows some insecure operations)")
    parser.add_argument("-A", "--allow", action="store_true", help="allow remote connections to local console ports")
    parser.add_argument("-q", "--quiet", action="store_true", help="do not show logs on stdout")
    parser.add_argument("-d", "--debug", action="store_true", help="show debug logs and enable code live reload")
    args = parser.parse_args()

    return args


def set_config(args):

    config = Config.instance()
    server_config = config.get_section_config("Server")
    server_config["local"] = server_config.get("local", "true" if args.local else "false")
    server_config["allow_remote_console"] = server_config.get("allow_remote_console", "true" if args.allow else "false")
    server_config["host"] = server_config.get("host", args.host)
    server_config["port"] = server_config.get("port", str(args.port))
    server_config["ssl"] = server_config.get("ssl", "true" if args.ssl else "false")
    server_config["certfile"] = server_config.get("certfile", args.certfile)
    server_config["certkey"] = server_config.get("certkey", args.certkey)
    server_config["debug"] = server_config.get("debug", "true" if args.debug else "false")
    config.set_section_config("Server", server_config)


def main():
    """
    Entry point for GNS3 server
    """

    level = logging.INFO
    args = parse_arguments()
    if args.debug:
        level = logging.DEBUG

    user_log = init_logger(level, quiet=args.quiet)
    user_log.info("GNS3 server version {}".format(__version__))
    current_year = datetime.date.today().year
    user_log.info("Copyright (c) 2007-{} GNS3 Technologies Inc.".format(current_year))

    set_config(args)
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

    Project.clean_project_directory()

    host = server_config["host"]
    port = int(server_config["port"])
    server = Server(host, port)
    server.run()

if __name__ == '__main__':
    main()
