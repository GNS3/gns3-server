#!/usr/bin/env python
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

"""
Entry point of the server. It's support daemonize the process
"""

# WARNING
# Due to buggy user machines we choose to put this as the first loading
# otherwise the egg cache is initialized in his standard location and
# if is not writetable the application crash. It's the user fault
# because one day the user as used sudo to run an egg and break his
# filesystem permissions, but it's a common mistake.
import gns3server.utils.get_resource

import os
import sys
import asyncio
import argparse


def daemonize():
    """
    Do the UNIX double-fork magic for properly detaching process
    """
    try:
        pid = os.fork()
        if pid > 0:
            # Exit first parent
            sys.exit(0)
    except OSError as e:
        print("First fork failed: %d (%s)\n" % (e.errno, e.strerror), file=sys.stderr)
        sys.exit(1)

    # Decouple from parent environment
    os.setsid()
    os.umask(0o007)

    # Do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # Exit from second parent
            sys.exit(0)
    except OSError as e:
        print("Second fork failed: %d (%s)\n" % (e.errno, e.strerror), file=sys.stderr)
        sys.exit(1)

def parse_arguments(argv):
    """
    Parse command line arguments

    :param argv: Array of command line arguments
    """
    from gns3server.version import __version__
    parser = argparse.ArgumentParser(description=f"GNS3 server version {__version__}")
    parser.add_argument("-v", "--version", help="show the version", action="version", version=__version__)
    parser.add_argument("--host", help="run on the given host/IP address")
    parser.add_argument("--port", help="run on the given port", type=int)
    parser.add_argument("--ssl", action="store_true", help="run in SSL mode")
    parser.add_argument("--config", help="Configuration file")
    parser.add_argument("--certfile", help="SSL cert file")
    parser.add_argument("--certkey", help="SSL key file")
    parser.add_argument("-L", "--local", action="store_true", help="local mode (allows some insecure operations)")
    parser.add_argument(
        "-A", "--allow", action="store_true", help="allow remote connections to local console ports"
    )
    parser.add_argument("-q", "--quiet", default=False, action="store_true", help="do not show logs on stdout")
    parser.add_argument("-d", "--debug", default=False, action="store_true", help="show debug logs")
    parser.add_argument("--logfile", "--log", help="send output to logfile instead of console")
    parser.add_argument("--logmaxsize", default=10000000, help="maximum logfile size in bytes (default is 10MB)")
    parser.add_argument(
        "--logbackupcount", default=10, help="number of historical log files to keep (default is 10)"
    )
    parser.add_argument(
        "--logcompression", default=False, action="store_true", help="compress inactive (historical) logs"
    )
    parser.add_argument("--daemon", action="store_true", help="start as a daemon")
    parser.add_argument("--pid", help="store process pid")
    parser.add_argument("--profile", help="Settings profile (blank will use default settings files)")

    args = parser.parse_args(argv)
    return parser, args


def main():
    """
    Entry point for GNS3 server
    """

    if sys.platform.startswith("win"):
        raise SystemExit("Windows is not a supported platform to run the GNS3 server")
    if "--daemon" in sys.argv:
        daemonize()

    try:
        parser, args = parse_arguments(sys.argv[1:])
        from gns3server.server import Server
        asyncio.run(Server().run(parser, args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
