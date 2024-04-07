#!/usr/bin/env python
#
# Copyright (C) 2021 GNS3 Technologies Inc.
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
import string

from gns3server.controller import Controller
from gns3server.compute.port_manager import PortManager
from gns3server.logger import init_logger
from gns3server.version import __version__
from gns3server.config import Config
from gns3server.crash_report import CrashReport
from gns3server.api.server import app
from pydantic import ValidationError, SecretStr

import logging

log = logging.getLogger(__name__)


class Server:

    _stream_handler = None

    @staticmethod
    def _locale_check():
        """
        Checks if this application runs with a correct locale (i.e. supports UTF-8 encoding) and attempt to fix
        if this is not the case.

        This is to prevent UnicodeEncodeError with unicode paths when using standard library I/O operation
        methods (e.g. os.stat() or os.path.*) which rely on the system or user locale.

        More information can be found there: http://seasonofcode.com/posts/unicode-i-o-and-locales-in-python.html
        or there: http://robjwells.com/post/61198832297/get-your-us-ascii-out-of-my-face
        """

        # no need to check when this application is frozen
        if hasattr(sys, "frozen"):
            return

        language = encoding = None
        try:
            language, encoding = locale.getlocale()
        except ValueError as e:
            log.error(f"Could not determine the current locale: {e}")
        if not language and not encoding:
            try:
                log.warning("Could not find a default locale, switching to C.UTF-8...")
                locale.setlocale(locale.LC_ALL, ("C", "UTF-8"))
            except locale.Error as e:
                log.error(f"Could not switch to the C.UTF-8 locale: {e}")
                raise SystemExit
        elif encoding != "UTF-8":
            log.warning(f"Your locale {language}.{encoding} encoding is not UTF-8, switching to the UTF-8 version...")
            try:
                locale.setlocale(locale.LC_ALL, (language, "UTF-8"))
            except locale.Error as e:
                log.error(f"Could not set an UTF-8 encoding for the {language} locale: {e}")
                raise SystemExit
        else:
            log.info(f"Current locale is {language}.{encoding}")

    def _parse_arguments(self, argv):
        """
        Parse command line arguments and override local configuration

        :params args: Array of command line arguments
        """

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
        level = logging.INFO
        if args.debug:
            level = logging.DEBUG

        self._stream_handler = init_logger(
            level,
            logfile=args.logfile,
            max_bytes=int(args.logmaxsize),
            backup_count=int(args.logbackupcount),
            compression=args.logcompression,
            quiet=args.quiet,
        )

        try:
            if args.config:
                Config.instance(files=[args.config], profile=args.profile)
            else:
                Config.instance(profile=args.profile)
            config = Config.instance().settings
        except ValidationError:
            sys.exit(1)

        defaults = {
            "host": config.Server.host,
            "port": config.Server.port,
            "ssl": config.Server.enable_ssl,
            "certfile": config.Server.certfile,
            "certkey": config.Server.certkey,
            "local": config.Server.local,
            "allow": config.Server.allow_remote_console,
        }

        parser.set_defaults(**defaults)
        return parser.parse_args(argv)

    @staticmethod
    def _set_config_defaults_from_command_line(args):

        config = Config.instance().settings
        config.Server.local = args.local
        config.Server.allow_remote_console = args.allow
        config.Server.host = args.host
        config.Server.port = args.port
        if args.certfile:
            config.Server.certfile = args.certfile
        if args.certkey:
            config.Server.certkey = args.certkey
        config.Server.enable_ssl = args.ssl

    def _signal_handling(self):
        def signal_handler(signame, *args):

            try:
                if signame == "SIGHUP":
                    log.info(f"Server has got signal {signame}, reloading...")
                    asyncio.ensure_future(Controller.instance().reload())
                else:
                    log.info(f"Server has got signal {signame}, exiting...")
                    # send SIGTERM to the server PID so uvicorn can shut down the process
                    os.kill(os.getpid(), signal.SIGTERM)
            except asyncio.CancelledError:
                pass

        signals = ["SIGHUP", "SIGQUIT"]  # SIGINT and SIGTERM are already registered by uvicorn
        for signal_name in signals:
            callback = functools.partial(signal_handler, signal_name)
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(getattr(signal, signal_name), callback)

    @staticmethod
    def _kill_ghosts():
        """
        Kill processes from previous GNS3 session
        """
        detect_process = ["vpcs", "ubridge", "dynamips"]
        for proc in psutil.process_iter():
            try:
                name = proc.name().lower().split(".")[0]
                if name in detect_process:
                    proc.kill()
                    log.warning("Killed ghost process %s", name)
            except (OSError, psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    @staticmethod
    def _pid_lock(path):
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
            with open(path, "w+") as f:
                f.write(str(os.getpid()))
        except OSError as e:
            log.critical("Can't write pid file %s: %s", path, str(e))
            sys.exit(1)

    async def run(self):

        args = self._parse_arguments(sys.argv[1:])

        if args.pid:
            self._pid_lock(args.pid)
            self._kill_ghosts()

        log.info(f"GNS3 server version {__version__}")
        current_year = datetime.date.today().year
        log.info(f"Copyright (c) 2007-{current_year} GNS3 Technologies Inc.")

        for config_file in Config.instance().get_config_files():
            log.info(f"Config file '{config_file}' loaded")

        self._set_config_defaults_from_command_line(args)
        config = Config.instance().settings

        if not config.Server.compute_password.get_secret_value():
            alphabet = string.ascii_letters + string.digits + string.punctuation
            generated_password = ''.join(secrets.choice(alphabet) for _ in range(16))
            config.Server.compute_password = SecretStr(generated_password)
            log.warning(f"Compute authentication is enabled with username '{config.Server.compute_username}' and "
                        f"a randomly generated password. Please set a password in the config file if this compute "
                        f"is to be used by an external controller")
        else:
            log.info(f"Compute authentication is enabled with username '{config.Server.compute_username}'")

        # we only support Python 3 version >= 3.8
        if sys.version_info < (3, 8, 0):
            raise SystemExit("Python 3.8 or higher is required")

        log.info(
            "Running with Python {major}.{minor}.{micro} and has PID {pid}".format(
                major=sys.version_info[0], minor=sys.version_info[1], micro=sys.version_info[2], pid=os.getpid()
            )
        )

        # check for the correct locale (UNIX/Linux only)
        self._locale_check()

        try:
            os.getcwd()
        except FileNotFoundError:
            log.critical("The current working directory doesn't exist")
            return

        try:
            import truststore
            truststore.inject_into_ssl()
            log.info("Using system certificate store for SSL connections")
        except ImportError:
            pass

        CrashReport.instance()
        host = config.Server.host
        port = config.Server.port

        PortManager.instance().console_host = host
        self._signal_handling()

        try:
            log.info(f"Starting server on {host}:{port}")

            # only show uvicorn access logs in debug mode
            access_log = False
            if log.getEffectiveLevel() == logging.DEBUG:
                access_log = True

            if config.Server.enable_ssl:
                log.info("SSL is enabled")

            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                access_log=access_log,
                ssl_certfile=config.Server.certfile,
                ssl_keyfile=config.Server.certkey,
                lifespan="on"
            )

            # overwrite uvicorn loggers with our own logger
            for uvicorn_logger_name in ("uvicorn", "uvicorn.error"):
                uvicorn_logger = logging.getLogger(uvicorn_logger_name)
                uvicorn_logger.handlers = [self._stream_handler]
                uvicorn_logger.propagate = False

            if access_log:
                uvicorn_logger = logging.getLogger("uvicorn.access")
                uvicorn_logger.handlers = [self._stream_handler]
                uvicorn_logger.propagate = False

            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            log.critical(f"Critical error while running the server: {e}", exc_info=1)
            CrashReport.instance().capture_exception()
            return
        finally:
            if args.pid:
                log.info("Remove PID file %s", args.pid)
                try:
                    os.remove(args.pid)
                except OSError as e:
                    log.critical("Can't remove pid file %s: %s", args.pid, str(e))
