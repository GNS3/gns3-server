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

# __version__ is a human-readable version number.

# __version_info__ is a four-tuple for programmatic comparison. The first
# three numbers are the components of the version number. The fourth
# is zero for an official release, positive for a development branch,
# or negative for a release candidate or beta (after the base version
# number has been incremented)

"""
Monitors communication with the GNS3 client via tmp file. Will terminate the instance if
communication is lost.
"""

import os
import sys
import time
import getopt
import datetime
import logging
import signal
import configparser
from logging.handlers import *
from os.path import expanduser

SCRIPT_NAME = os.path.basename(__file__)

# Is the full path when used as an import
SCRIPT_PATH = os.path.dirname(__file__)

if not SCRIPT_PATH:
    SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(
        sys.argv[0])))


EXTRA_LIB = "%s/modules" % (SCRIPT_PATH)
sys.path.append(EXTRA_LIB)

from . import cloud
from rackspace_cloud import Rackspace

LOG_NAME = "gns3dms"
log = None

sys.path.append(EXTRA_LIB)

import daemon

my_daemon = None

usage = """
USAGE: %s

Options:

  -d, --debug         Enable debugging
  -v, --verbose       Enable verbose logging
  -h, --help          Display this menu :)

  --cloud_api_key <api_key>  Rackspace API key
  --cloud_user_name

  --instance_id       ID of the Rackspace instance to terminate
  --cloud_region      Region of instance

  --dead_time          How long in seconds can the communication lose exist before we
                      shutdown this instance.
                      Default:
                      Example --dead_time=3600 (60 minutes)

  --check-interval    Defaults to --dead_time, used for debugging

  --init-wait         Inital wait time, how long before we start pulling the file.
                      Default: 300 (5 min)
                      Example --init-wait=300

  --file              The file we monitor for updates

  -k                  Kill previous instance running in background
  --background        Run in background

""" % (SCRIPT_NAME)

# Parse cmd line options


def parse_cmd_line(argv):
    """
    Parse command line arguments

    argv: Pass in cmd line arguments
    """

    short_args = "dvhk"
    long_args = ("debug",
                 "verbose",
                 "help",
                 "cloud_user_name=",
                 "cloud_api_key=",
                 "instance_id=",
                 "region=",
                 "dead_time=",
                 "init-wait=",
                 "check-interval=",
                 "file=",
                 "background",
                 )
    try:
        opts, extra_opts = getopt.getopt(argv[1:], short_args, long_args)
    except getopt.GetoptError as e:
        print("Unrecognized command line option or missing required argument: %s" % (e))
        print(usage)
        sys.exit(2)

    cmd_line_option_list = {}
    cmd_line_option_list["debug"] = False
    cmd_line_option_list["verbose"] = True
    cmd_line_option_list["cloud_user_name"] = None
    cmd_line_option_list["cloud_api_key"] = None
    cmd_line_option_list["instance_id"] = None
    cmd_line_option_list["region"] = None
    cmd_line_option_list["dead_time"] = 60 * 60  # minutes
    cmd_line_option_list["check-interval"] = None
    cmd_line_option_list["init-wait"] = 5 * 60
    cmd_line_option_list["file"] = None
    cmd_line_option_list["shutdown"] = False
    cmd_line_option_list["daemon"] = False
    cmd_line_option_list['starttime'] = datetime.datetime.now()

    if sys.platform == "linux":
        cmd_line_option_list['syslog'] = "/dev/log"
    elif sys.platform == "osx":
        cmd_line_option_list['syslog'] = "/var/run/syslog"
    else:
        cmd_line_option_list['syslog'] = ('localhost', 514)

    get_gns3secrets(cmd_line_option_list)
    cmd_line_option_list["dead_time"] = int(cmd_line_option_list["dead_time"])

    for opt, val in opts:
        if (opt in ("-h", "--help")):
            print(usage)
            sys.exit(0)
        elif (opt in ("-d", "--debug")):
            cmd_line_option_list["debug"] = True
        elif (opt in ("-v", "--verbose")):
            cmd_line_option_list["verbose"] = True
        elif (opt in ("--cloud_user_name")):
            cmd_line_option_list["cloud_user_name"] = val
        elif (opt in ("--cloud_api_key")):
            cmd_line_option_list["cloud_api_key"] = val
        elif (opt in ("--instance_id")):
            cmd_line_option_list["instance_id"] = val
        elif (opt in ("--region")):
            cmd_line_option_list["region"] = val
        elif (opt in ("--dead_time")):
            cmd_line_option_list["dead_time"] = int(val)
        elif (opt in ("--check-interval")):
            cmd_line_option_list["check-interval"] = int(val)
        elif (opt in ("--init-wait")):
            cmd_line_option_list["init-wait"] = int(val)
        elif (opt in ("--file")):
            cmd_line_option_list["file"] = val
        elif (opt in ("-k")):
            cmd_line_option_list["shutdown"] = True
        elif (opt in ("--background")):
            cmd_line_option_list["daemon"] = True

    if cmd_line_option_list["shutdown"] is False:

        if cmd_line_option_list["check-interval"] is None:
            cmd_line_option_list["check-interval"] = cmd_line_option_list["dead_time"] + 120

        if cmd_line_option_list["cloud_user_name"] is None:
            print("You need to specify a username!!!!")
            print(usage)
            sys.exit(2)

        if cmd_line_option_list["cloud_api_key"] is None:
            print("You need to specify an apikey!!!!")
            print(usage)
            sys.exit(2)

        if cmd_line_option_list["file"] is None:
            print("You need to specify a file to watch!!!!")
            print(usage)
            sys.exit(2)

        if cmd_line_option_list["instance_id"] is None:
            print("You need to specify an instance_id")
            print(usage)
            sys.exit(2)

        if cmd_line_option_list["cloud_region"] is None:
            print("You need to specify a cloud_region")
            print(usage)
            sys.exit(2)

    return cmd_line_option_list


def get_gns3secrets(cmd_line_option_list):
    """
    Load cloud credentials from .gns3secrets
    """

    gns3secret_paths = [
        os.path.join(os.path.expanduser("~"), '.config', 'GNS3'),
        SCRIPT_PATH,
    ]

    config = configparser.ConfigParser()

    for gns3secret_path in gns3secret_paths:
        gns3secret_file = "%s/cloud.conf" % (gns3secret_path)
        if os.path.isfile(gns3secret_file):
            config.read(gns3secret_file)

    try:
        for key, value in config.items("CLOUD_SERVER"):
            cmd_line_option_list[key] = value.strip()
    except configparser.NoSectionError:
        pass


def set_logging(cmd_options):
    """
    Setup logging and format output for console and syslog

    Syslog is using the KERN facility
    """
    log = logging.getLogger("%s" % (LOG_NAME))
    log_level = logging.INFO
    log_level_console = logging.WARNING

    if cmd_options['verbose']:
        log_level_console = logging.INFO

    if cmd_options['debug']:
        log_level_console = logging.DEBUG
        log_level = logging.DEBUG

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sys_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')

    console_log = logging.StreamHandler()
    console_log.setLevel(log_level_console)
    console_log.setFormatter(formatter)

    syslog_hndlr = SysLogHandler(
        address=cmd_options['syslog'],
        facility=SysLogHandler.LOG_KERN
    )

    syslog_hndlr.setFormatter(sys_formatter)

    log.setLevel(log_level)
    log.addHandler(console_log)
    log.addHandler(syslog_hndlr)

    return log


def send_shutdown(pid_file):
    """
    Sends the daemon process a kill signal
    """
    try:
        with open(pid_file, 'r') as pidf:
            pid = int(pidf.readline().strip())
            pidf.close()
            os.kill(pid, 15)
    except:
        log.info("No running instance found!!!")
        log.info("Missing PID file: %s" % (pid_file))


def _get_file_age(filename):
    return datetime.datetime.fromtimestamp(
        os.path.getmtime(filename)
    )


def monitor_loop(options):
    """
    Checks the options["file"] modification time against an interval. If the
    modification time is too old we terminate the instance.
    """

    log.debug("Waiting for init-wait to pass: %s" % (options["init-wait"]))
    time.sleep(options["init-wait"])

    log.info("Starting monitor_loop")

    terminate_attempts = 0

    while options['shutdown'] is False:
        log.debug("In monitor_loop for : %s" % (
            datetime.datetime.now() - options['starttime'])
        )

        file_last_modified = _get_file_age(options["file"])
        now = datetime.datetime.now()

        delta = now - file_last_modified
        log.debug("File last updated: %s seconds ago" % (delta.seconds))

        if delta.seconds > options["dead_time"]:
            log.warning("Dead time exceeded, terminating instance ...")
            # Terminate involves many layers of HTTP / API calls, lots of
            # different errors types could occur here.
            try:
                rksp = Rackspace(options)
                rksp.terminate()
            except Exception as e:
                log.critical("Exception during terminate: %s" % (e))

            terminate_attempts += 1
            log.warning("Termination sent, attempt: %s" % (terminate_attempts))
            time.sleep(600)
        else:
            time.sleep(options["check-interval"])

    log.info("Leaving monitor_loop")
    log.info("Shutting down")


def main():

    global log
    global my_daemon
    options = parse_cmd_line(sys.argv)
    log = set_logging(options)

    def _shutdown(signalnum=None, frame=None):
        """
        Handles the SIGINT and SIGTERM event, inside of main so it has access to
        the log vars.
        """

        log.info("Received shutdown signal")
        options["shutdown"] = True

    pid_file = "%s/.gns3dms.pid" % (expanduser("~"))

    if options["shutdown"]:
        send_shutdown(pid_file)
        sys.exit(0)

    if options["daemon"]:
        my_daemon = MyDaemon(pid_file, options)

    # Setup signal to catch Control-C / SIGINT and SIGTERM
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("Starting ...")
    log.debug("Using settings:")
    for key, value in iter(sorted(options.items())):
        log.debug("%s : %s" % (key, value))

    log.debug("Checking file ....")
    if os.path.isfile(options["file"]) is False:
        log.critical("File does not exist!!!")
        sys.exit(1)

    test_acess = _get_file_age(options["file"])
    if not isinstance(test_acess, datetime.datetime):
        log.critical("Can't get file modification time!!!")
        sys.exit(1)

    if my_daemon:
        my_daemon.start()
    else:
        monitor_loop(options)


class MyDaemon(daemon.daemon):

    def run(self):
        monitor_loop(self.options)


if __name__ == "__main__":
    result = main()
    sys.exit(result)
