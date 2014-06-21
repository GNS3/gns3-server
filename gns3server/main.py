#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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
import multiprocessing
import locale
import tornado.options
from gns3server.server import Server
from gns3server.version import __version__

import logging
log = logging.getLogger(__name__)

# command line options
from tornado.options import define
define("host", default="0.0.0.0", help="run on the given host/IP address", type=str)
define("port", default=8000, help="run on the given port", type=int)
define("ipc", default=False, help="use IPC for module communication", type=bool)
define("version", default=False, help="show the version", type=bool)


def locale_check():
    """
    Checks if this application runs with a correct locale (i.e. supports UTF-8 encoding) and attempt to fix
    if this is not the case.

    This is to prevent UnicodeEncodeError with unicode paths when using standard library I/O operation
    methods (e.g. os.stat() or os.path.*) which rely on the system or user locale.

    More information can be found there: http://seasonofcode.com/posts/unicode-i-o-and-locales-in-python.html
    or there: http://robjwells.com/post/61198832297/get-your-us-ascii-out-of-my-face
    """

    # no need to check on Windows or when frozen
    if sys.platform.startswith("win") or hasattr(sys, "frozen"):
        return

    language = encoding = None
    try:
        language, encoding = locale.getlocale()
    except ValueError as e:
        log.error("could not determine the current locale: {}".format(e))
    if not language and not encoding:
        try:
            log.warn("could not find a default locale, switching to C.UTF-8...")
            locale.setlocale(locale.LC_ALL, ("C", "UTF-8"))
        except locale.Error as e:
            log.error("could not switch to the C.UTF-8 locale: {}".format(e))
            raise SystemExit
    elif encoding != "UTF-8":
        log.warn("your locale {}.{} encoding is not UTF-8, switching to the UTF-8 version...".format(language, encoding))
        try:
            locale.setlocale(locale.LC_ALL, (language, "UTF-8"))
        except locale.Error as e:
            log.error("could not set an UTF-8 encoding for the {} locale: {}".format(language, e))
            raise SystemExit
    else:
        log.info("current locale is {}.{}".format(language, encoding))


def main():
    """
    Entry point for GNS3 server
    """

    if sys.platform.startswith("win"):
        # necessary on Windows to freeze the application
        multiprocessing.freeze_support()

    try:
        tornado.options.parse_command_line()
    except (tornado.options.Error, ValueError):
        tornado.options.print_help()
        raise SystemExit

    from tornado.options import options
    if options.version:
        print(__version__)
        raise SystemExit

    current_year = datetime.date.today().year
    print("GNS3 server version {}".format(__version__))
    print("Copyright (c) 2007-{} GNS3 Technologies Inc.".format(current_year))

    # we only support Python 3 version >= 3.3
    if sys.version_info < (3, 3):
        raise RuntimeError("Python 3.3 or higher is required")

    print("Running with Python {major}.{minor}.{micro} and has PID {pid}".format(major=sys.version_info[0],
                                                                                 minor=sys.version_info[1],
                                                                                 micro=sys.version_info[2],
                                                                                 pid=os.getpid()))

    # check for the correct locale
    # (UNIX/Linux only)
    locale_check()

    try:
        os.getcwd()
    except FileNotFoundError:
        log.critical("the current working directory doesn't exist")
        return

    server = Server(options.host,
                    options.port,
                    ipc=options.ipc)
    server.load_modules()
    server.run()

if __name__ == '__main__':
    main()
