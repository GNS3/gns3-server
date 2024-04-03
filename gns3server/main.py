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


def main():
    """
    Entry point for GNS3 server
    """

    if sys.platform.startswith("win"):
        raise SystemExit("Windows is not a supported platform to run the GNS3 server")
    if "--daemon" in sys.argv:
        daemonize()
    from gns3server.server import Server

    try:
        asyncio.run(Server().run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
