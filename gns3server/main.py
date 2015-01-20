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

from gns3server.server import Server
from gns3server.version import __version__

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

    # TODO: migrate command line options to argparse (don't forget the quiet mode).

    current_year = datetime.date.today().year

    # TODO: Renable the test when we will have command line
    # user_log = logging.getLogger('user_facing')
    # if not options.quiet:
    #     # Send user facing messages to stdout.
    # stream_handler = logging.StreamHandler(sys.stdout)
    # stream_handler.addFilter(logging.Filter(name='user_facing'))
    # user_log.addHandler(stream_handler)
    # user_log.propagate = False
    # END OLD LOG CODE
    root_log = logging.getLogger()
    root_log.setLevel(logging.DEBUG)
    console_log = logging.StreamHandler(sys.stdout)
    console_log.setLevel(logging.DEBUG)
    root_log.addHandler(console_log)
    user_log = root_log
    # FIXME END Temporary

    user_log.info("GNS3 server version {}".format(__version__))
    user_log.info("Copyright (c) 2007-{} GNS3 Technologies Inc.".format(current_year))
    # TODO: end todo

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
        log.critical("the current working directory doesn't exist")
        return

    # TODO: Renable console_bind_to_any when we will have command line parsing
    # server = Server(options.host, options.port, options.console_bind_to_any)
    server = Server("127.0.0.1", 8000, False)
    server.run()

if __name__ == '__main__':
    main()
