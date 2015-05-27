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


# WARNING
# Due to buggy user machines we choose to put this as the first loading modules
# otherwise the egg cache is initialized in his standard location and
# if is not writetable the application crash. It's the user fault
# because one day the user as used sudo to run an egg and break his
# filesystem permissions, but it's a common mistake.
import gns3server.utils.get_resource


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
from gns3server.crash_report import CrashReport

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


def parse_arguments(argv, config):
    """
    Parse command line arguments and override local configuration

    :params args: Array of command line arguments
    :params config: ConfigParser with default variable from configuration
    """

    defaults = {
        "host": config.get("host", "0.0.0.0"),
        "port": config.get("port", 8000),
        "ssl": config.getboolean("ssl", False),
        "certfile": config.get("certfile", ""),
        "certkey": config.get("certkey", ""),
        "record": config.get("record", ""),
        "local": config.getboolean("local", False),
        "allow": config.getboolean("allow_remote_console", False),
        "quiet": config.getboolean("quiet", False),
        "debug": config.getboolean("debug", False),
        "live": config.getboolean("live", False),
        "logfile": config.getboolean("logfile", ""),
    }

    parser = argparse.ArgumentParser(description="GNS3 server version {}".format(__version__))
    parser.set_defaults(**defaults)
    parser.add_argument("-v", "--version", help="show the version", action="version", version=__version__)
    parser.add_argument("--host", help="run on the given host/IP address")
    parser.add_argument("--port", help="run on the given port", type=int)
    parser.add_argument("--ssl", action="store_true", help="run in SSL mode")
    parser.add_argument("--certfile", help="SSL cert file")
    parser.add_argument("--certkey", help="SSL key file")
    parser.add_argument("--record", help="save curl requests into a file")
    parser.add_argument("-L", "--local", action="store_true", help="local mode (allows some insecure operations)")
    parser.add_argument("-A", "--allow", action="store_true", help="allow remote connections to local console ports")
    parser.add_argument("-q", "--quiet", action="store_true", help="do not show logs on stdout")
    parser.add_argument("-d", "--debug", action="store_true", help="show debug logs")
    parser.add_argument("--live", action="store_true", help="enable code live reload")
    parser.add_argument("--shell", action="store_true", help="start a shell inside the server (debugging purpose only you need to install ptpython before)")
    parser.add_argument("--log", help="send output to logfile instead of console")

    return parser.parse_args(argv)


def set_config(args):

    config = Config.instance()
    server_config = config.get_section_config("Server")
    server_config["local"] = str(args.local)
    server_config["allow_remote_console"] = str(args.allow)
    server_config["host"] = args.host
    server_config["port"] = str(args.port)
    server_config["ssl"] = str(args.ssl)
    server_config["certfile"] = args.certfile
    server_config["certkey"] = args.certkey
    server_config["record"] = args.record
    server_config["debug"] = str(args.debug)
    server_config["live"] = str(args.live)
    server_config["shell"] = str(args.shell)
    config.set_section_config("Server", server_config)


def main():
    """
    Entry point for GNS3 server
    """

    level = logging.INFO
    args = parse_arguments(sys.argv[1:], Config.instance().get_section_config("Server"))
    if args.debug:
        level = logging.DEBUG

    user_log = init_logger(level, logfile=args.log, quiet=args.quiet)
    user_log.info("GNS3 server version {}".format(__version__))
    current_year = datetime.date.today().year
    user_log.info("Copyright (c) 2007-{} GNS3 Technologies Inc.".format(current_year))

    for config_file in Config.instance().get_config_files():
        user_log.info("Config file {} loaded".format(config_file))

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

    CrashReport.instance()

    try:
        host = server_config["host"].encode("idna").decode()
    except UnicodeError:
        log.critical("Invalid hostname %s", server_config["host"])
        return

    port = int(server_config["port"])
    server = Server.instance(host, port)
    try:
        server.run()
    except OSError as e:
        # This is to ignore OSError: [WinError 0] The operation completed successfully exception on Windows.
        if not sys.platform.startswith("win") and not e.winerror == 0:
            raise
    except Exception as e:
        log.critical("Critical error while running the server: {}".format(e), exc_info=1)
        CrashReport.instance().capture_exception()
        return

if __name__ == '__main__':
    main()
