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
Startup script for a GNS3 Server Cloud Instance.  It generates certificates,
config files and usernames before finally starting the gns3server process
on the instance.
"""

import os
import sys
import configparser
import getopt
import datetime
import signal
from logging.handlers import *
from os.path import expanduser
from gns3server.config import Config
import ast
import subprocess
import uuid

SCRIPT_NAME = os.path.basename(__file__)

# This is the full path when used as an import
SCRIPT_PATH = os.path.dirname(__file__)

if not SCRIPT_PATH:
    SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(
        sys.argv[0])))


LOG_NAME = "gns3-startup"
log = None

usage = """
USAGE: %s

Options:

  -d, --debug         Enable debugging
  -i  --ip            The ip address of the server, for cert generation
  -v, --verbose       Enable verbose logging
  -h, --help          Display this menu :)

  --data              Python dict of data to be written to the config file:
                      " { 'gns3' : 'Is AWESOME' } "

""" % (SCRIPT_NAME)


def parse_cmd_line(argv):
    """
    Parse command line arguments

    argv: Passed in sys.argv
    """

    short_args = "dvh"
    long_args = ("debug",
                    "ip=",
                    "verbose",
                    "help",
                    "data=",
                    )
    try:
        opts, extra_opts = getopt.getopt(argv[1:], short_args, long_args)
    except getopt.GetoptError as e:
        print("Unrecognized command line option or missing required argument: %s" %(e))
        print(usage)
        sys.exit(2)

    cmd_line_option_list = {'debug': False, 'verbose': True, 'data': None}

    if sys.platform == "linux":
        cmd_line_option_list['syslog'] = "/dev/log"
    elif sys.platform == "osx":
        cmd_line_option_list['syslog'] = "/var/run/syslog"
    else:
        cmd_line_option_list['syslog'] = ('localhost',514)

    for opt, val in opts:
        if opt in ("-h", "--help"):
            print(usage)
            sys.exit(0)
        elif opt in ("-d", "--debug"):
            cmd_line_option_list["debug"] = True
        elif opt in ("--ip",):
            cmd_line_option_list["ip"] = val
        elif opt in ("-v", "--verbose"):
            cmd_line_option_list["verbose"] = True
        elif opt in ("--data",):
            cmd_line_option_list["data"] = ast.literal_eval(val)

    return cmd_line_option_list


def set_logging(cmd_options):
    """
    Setup logging and format output for console and syslog

    Syslog is using the KERN facility
    """
    log = logging.getLogger("%s" % (LOG_NAME))
    log_level = logging.INFO
    log_level_console = logging.WARNING

    if cmd_options['verbose'] is True:
        log_level_console = logging.INFO

    if cmd_options['debug'] is True:
        log_level_console = logging.DEBUG
        log_level = logging.DEBUG

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sys_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')

    console_log = logging.StreamHandler()
    console_log.setLevel(log_level_console)
    console_log.setFormatter(formatter)

    syslog_handler = SysLogHandler(
        address=cmd_options['syslog'],
        facility=SysLogHandler.LOG_KERN
    )

    syslog_handler.setFormatter(sys_formatter)

    log.setLevel(log_level)
    log.addHandler(console_log)
    log.addHandler(syslog_handler)

    return log


def _generate_certs(options):
    """
    Generate a self-signed certificate for SSL-enabling the WebSocket
    connection.  The certificate is sent back to the client so it can
    verify the authenticity of the server.

    :return: A 2-tuple of strings containing (server_key, server_cert)
    """
    cmd = ["{}/cert_utils/create_cert.sh".format(SCRIPT_PATH), options['ip']]
    log.debug("Generating certs with cmd: {}".format(' '.join(cmd)))
    output_raw = subprocess.check_output(cmd, shell=False,
                                         stderr=subprocess.STDOUT)

    output_str = output_raw.decode("utf-8")
    output = output_str.strip().split("\n")
    log.debug(output)
    return (output[-2], output[-1])


def _start_gns3server():
    """
    Start up the gns3 server.

    :return: None
    """
    cmd = 'gns3server --quiet > /tmp/gns3.log 2>&1 &'
    log.info("Starting gns3server with cmd {}".format(cmd))
    os.system(cmd)


def main():

    global log
    options = parse_cmd_line(sys.argv)
    log = set_logging(options)

    def _shutdown(signalnum=None, frame=None):
        """
        Handles the SIGINT and SIGTERM event, inside of main so it has access to
        the log vars.
        """

        log.info("Received shutdown signal")
        sys.exit(0)

    # Setup signal to catch Control-C / SIGINT and SIGTERM
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    client_data = {}

    config = Config.instance()
    cfg = config.list_cloud_config_file()
    cfg_path = os.path.dirname(cfg)

    try:
        os.makedirs(cfg_path)
    except FileExistsError:
        pass

    (server_key, server_crt) = _generate_certs(options)

    cloud_config = configparser.ConfigParser()
    cloud_config['CLOUD_SERVER'] = {}

    if options['data']:
        cloud_config['CLOUD_SERVER'] = options['data']

    cloud_config['CLOUD_SERVER']['SSL_KEY'] = server_key
    cloud_config['CLOUD_SERVER']['SSL_CRT'] = server_crt
    cloud_config['CLOUD_SERVER']['SSL_ENABLED'] = 'no'
    cloud_config['CLOUD_SERVER']['WEB_USERNAME'] = str(uuid.uuid4()).upper()[0:8]
    cloud_config['CLOUD_SERVER']['WEB_PASSWORD'] = str(uuid.uuid4()).upper()[0:8]

    with open(cfg, 'w') as cloud_config_file:
        cloud_config.write(cloud_config_file)

    _start_gns3server()

    with open(server_crt, 'r') as cert_file:
        cert_data = cert_file.readlines()

    cert_file.close()

    # Return a stringified dictionary on stdout.  The gui captures this to get
    # things like the server cert.
    client_data['SSL_CRT_FILE'] = server_crt
    client_data['SSL_CRT'] = cert_data
    client_data['WEB_USERNAME'] = cloud_config['CLOUD_SERVER']['WEB_USERNAME']
    client_data['WEB_PASSWORD'] = cloud_config['CLOUD_SERVER']['WEB_PASSWORD']
    print(client_data)
    return 0


if __name__ == "__main__":
    result = main()
    sys.exit(result)
