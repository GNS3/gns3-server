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


"""
Start the program. Use main.py to load it.
"""

import os
import datetime
import locale
import argparse
import psutil
import sys
import asyncio
import signal
import functools
import uvicorn
import secrets

from gns3server.controller import Controller
from gns3server.compute.port_manager import PortManager
from gns3server.logger import init_logger
from gns3server.version import __version__
from gns3server.config import Config
from gns3server.crash_report import CrashReport
from gns3server.api.server import app


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
            log.warning("Could not find a default locale, switching to C.UTF-8...")
            locale.setlocale(locale.LC_ALL, ("C", "UTF-8"))
        except locale.Error as e:
            log.error("Could not switch to the C.UTF-8 locale: {}".format(e))
            raise SystemExit
    elif encoding != "UTF-8":
        log.warning("Your locale {}.{} encoding is not UTF-8, switching to the UTF-8 version...".format(language, encoding))
        try:
            locale.setlocale(locale.LC_ALL, (language, "UTF-8"))
        except locale.Error as e:
            log.error("Could not set an UTF-8 encoding for the {} locale: {}".format(language, e))
            raise SystemExit
    else:
        log.info("Current locale is {}.{}".format(language, encoding))


def parse_arguments(argv):
    """
    Parse command line arguments and override local configuration

    :params args: Array of command line arguments
    """

    parser = argparse.ArgumentParser(description="GNS3 server version {}".format(__version__))
    parser.add_argument("-v", "--version", help="show the version", action="version", version=__version__)
    parser.add_argument("--host", help="run on the given host/IP address")
    parser.add_argument("--port", help="run on the given port", type=int)
    parser.add_argument("--ssl", action="store_true", help="run in SSL mode")
    parser.add_argument("--config", help="Configuration file")
    parser.add_argument("--certfile", help="SSL cert file")
    parser.add_argument("--certkey", help="SSL key file")
    parser.add_argument("--record", help="save curl requests into a file (for developers)")
    parser.add_argument("-L", "--local", action="store_true", help="local mode (allows some insecure operations)")
    parser.add_argument("-A", "--allow", action="store_true", help="allow remote connections to local console ports")
    parser.add_argument("-q", "--quiet", action="store_true", help="do not show logs on stdout")
    parser.add_argument("-d", "--debug", action="store_true", help="show debug logs")
    parser.add_argument("--shell", action="store_true", help="start a shell inside the server (debugging purpose only you need to install ptpython before)")
    parser.add_argument("--log", help="send output to logfile instead of console")
    parser.add_argument("--logmaxsize", help="maximum logfile size in bytes (default is 10MB)")
    parser.add_argument("--logbackupcount", help="number of historical log files to keep (default is 10)")
    parser.add_argument("--logcompression", action="store_true", help="compress inactive (historical) logs")
    parser.add_argument("--daemon", action="store_true", help="start as a daemon")
    parser.add_argument("--pid", help="store process pid")
    parser.add_argument("--profile", help="Settings profile (blank will use default settings files)")

    args = parser.parse_args(argv)
    if args.config:
        Config.instance(files=[args.config], profile=args.profile)
    else:
        Config.instance(profile=args.profile)

    config = Config.instance().get_section_config("Server")
    defaults = {
        "host": config.get("host", "0.0.0.0"),
        "port": config.getint("port", 3080),
        "ssl": config.getboolean("ssl", False),
        "certfile": config.get("certfile", ""),
        "certkey": config.get("certkey", ""),
        "record": config.get("record", ""),
        "local": config.getboolean("local", False),
        "allow": config.getboolean("allow_remote_console", False),
        "quiet": config.getboolean("quiet", False),
        "debug": config.getboolean("debug", False),
        "logfile": config.getboolean("logfile", ""),
        "logmaxsize": config.getint("logmaxsize", 10000000),  # default is 10MB
        "logbackupcount": config.getint("logbackupcount", 10),
        "logcompression": config.getboolean("logcompression", False)
    }

    parser.set_defaults(**defaults)
    return parser.parse_args(argv)


def set_config(args):

    config = Config.instance()
    server_config = config.get_section_config("Server")
    jwt_secret_key = server_config.get("jwt_secret_key", None)
    if not jwt_secret_key:
        log.info("No JWT secret key configured, generating one...")
        if not config._config.has_section("Server"):
            config._config.add_section("Server")
        config._config.set("Server", "jwt_secret_key", secrets.token_hex(32))
        config.write_config()
    server_config["local"] = str(args.local)
    server_config["allow_remote_console"] = str(args.allow)
    server_config["host"] = args.host
    server_config["port"] = str(args.port)
    server_config["ssl"] = str(args.ssl)
    server_config["certfile"] = args.certfile
    server_config["certkey"] = args.certkey
    server_config["record"] = args.record
    server_config["debug"] = str(args.debug)
    server_config["shell"] = str(args.shell)
    config.set_section_config("Server", server_config)


def pid_lock(path):
    """
    Write the file in a file on the system.
    Check if the process is not already running.
    """

    if os.path.exists(path):
        pid = None
        try:
            with open(path) as f:
                try:
                    pid = int(f.read())
                    os.kill(pid, 0)  # kill returns an error if the process is not running
                except (OSError, SystemError, ValueError):
                    pid = None
        except OSError as e:
            log.critical("Can't open pid file %s: %s", pid, str(e))
            sys.exit(1)

        if pid:
            log.critical("GNS3 is already running pid: %d", pid)
            sys.exit(1)

    try:
        with open(path, 'w+') as f:
            f.write(str(os.getpid()))
    except OSError as e:
        log.critical("Can't write pid file %s: %s", path, str(e))
        sys.exit(1)


def kill_ghosts():
    """
    Kill process from previous GNS3 session
    """
    detect_process = ["vpcs", "traceng", "ubridge", "dynamips"]
    for proc in psutil.process_iter():
        try:
            name = proc.name().lower().split(".")[0]
            if name in detect_process:
                proc.kill()
                log.warning("Killed ghost process %s", name)
        except (OSError, psutil.NoSuchProcess, psutil.AccessDenied):
            pass


async def reload_server():
    """
    Reload the server.
    """

    await Controller.instance().reload()


def signal_handling():

    def signal_handler(signame, *args):

        try:
            if signame == "SIGHUP":
                log.info("Server has got signal {}, reloading...".format(signame))
                asyncio.ensure_future(reload_server())
            else:
                log.info("Server has got signal {}, exiting...".format(signame))
                os.kill(os.getpid(), signal.SIGTERM)
        except asyncio.CancelledError:
            pass

    signals = []  # SIGINT and SIGTERM are already registered by uvicorn
    if sys.platform.startswith("win"):
        signals.extend(["SIGBREAK"])
    else:
        signals.extend(["SIGHUP", "SIGQUIT"])

    for signal_name in signals:
        callback = functools.partial(signal_handler, signal_name)
        if sys.platform.startswith("win"):
            # add_signal_handler() is not yet supported on Windows
            signal.signal(getattr(signal, signal_name), callback)
        else:
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(getattr(signal, signal_name), callback)


def run():

    args = parse_arguments(sys.argv[1:])
    if args.daemon and sys.platform.startswith("win"):
        log.critical("Daemon is not supported on Windows")
        sys.exit(1)

    if args.pid:
        pid_lock(args.pid)
        kill_ghosts()

    level = logging.INFO
    if args.debug:
        level = logging.DEBUG

    stream_handler = init_logger(level,
                                 logfile=args.log,
                                 max_bytes=int(args.logmaxsize),
                                 backup_count=int(args.logbackupcount),
                                 compression=args.logcompression,
                                 quiet=args.quiet)

    log.info("GNS3 server version {}".format(__version__))
    current_year = datetime.date.today().year
    log.info("Copyright (c) 2007-{} GNS3 Technologies Inc.".format(current_year))

    for config_file in Config.instance().get_config_files():
        log.info("Config file {} loaded".format(config_file))

    set_config(args)
    server_config = Config.instance().get_section_config("Server")

    if server_config.getboolean("local"):
        log.warning("Local mode is enabled. Beware, clients will have full control on your filesystem")

    if server_config.getboolean("auth"):
        user = server_config.get("user", "").strip()
        if not user:
            log.critical("HTTP authentication is enabled but no username is configured")
            return
        log.info("HTTP authentication is enabled with username '{}'".format(user))

    # we only support Python 3 version >= 3.6
    if sys.version_info < (3, 6, 0):
        raise SystemExit("Python 3.6 or higher is required")

    log.info("Running with Python {major}.{minor}.{micro} and has PID {pid}".format(major=sys.version_info[0],
                                                                                    minor=sys.version_info[1],
                                                                                    micro=sys.version_info[2],
                                                                                    pid=os.getpid()))

    # check for the correct locale (UNIX/Linux only)
    locale_check()

    try:
        os.getcwd()
    except FileNotFoundError:
        log.critical("The current working directory doesn't exist")
        return

    CrashReport.instance()
    host = server_config["host"]
    port = int(server_config["port"])

    PortManager.instance().console_host = host
    signal_handling()

    try:
        log.info("Starting server on {}:{}".format(host, port))

        # only show uvicorn access logs in debug mode
        access_log = False
        if log.getEffectiveLevel() == logging.DEBUG:
            access_log = True

        certfile = None
        certkey = None
        if server_config.getboolean("ssl"):
            if sys.platform.startswith("win"):
                log.critical("SSL mode is not supported on Windows")
                raise SystemExit
            certfile = server_config["certfile"]
            certkey = server_config["certkey"]
            log.info("SSL is enabled")

        config = uvicorn.Config(app,
                                host=host,
                                port=port,
                                access_log=access_log,
                                ssl_certfile=certfile,
                                ssl_keyfile=certkey)

        # overwrite uvicorn loggers with our own logger
        for uvicorn_logger_name in ("uvicorn", "uvicorn.error"):
            uvicorn_logger = logging.getLogger(uvicorn_logger_name)
            uvicorn_logger.handlers = [stream_handler]
            uvicorn_logger.propagate = False

        if access_log:
            uvicorn_logger = logging.getLogger("uvicorn.access")
            uvicorn_logger.handlers = [stream_handler]
            uvicorn_logger.propagate = False

        server = uvicorn.Server(config)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(server.serve())

    except OSError as e:
        # This is to ignore OSError: [WinError 0] The operation completed successfully exception on Windows.
        if not sys.platform.startswith("win") or not e.winerror == 0:
            raise
    except Exception as e:
        log.critical("Critical error while running the server: {}".format(e), exc_info=1)
        CrashReport.instance().capture_exception()
        return
    finally:
        if args.pid:
            log.info("Remove PID file %s", args.pid)
            try:
                os.remove(args.pid)
            except OSError as e:
                log.critical("Can't remove pid file %s: %s", args.pid, str(e))
