# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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
DeadMan server module.
"""

import os
import time
import subprocess

from gns3server.modules import IModule
from gns3server.config import Config


import logging
log = logging.getLogger(__name__)

class DeadMan(IModule):
    """
    DeadMan module.

    :param name: module name
    :param args: arguments for the module
    :param kwargs: named arguments for the module
    """

    def __init__(self, name, *args, **kwargs):
        config = Config.instance()

        # a new process start when calling IModule
        IModule.__init__(self, name, *args, **kwargs)
        self._host = kwargs["host"]
        self._projects_dir = kwargs["projects_dir"]
        self._tempdir = kwargs["temp_dir"]
        self._working_dir = self._projects_dir
        self._heartbeat_file = "%s/heartbeat_file_for_gnsdms" % (
            self._tempdir)

        if 'heartbeat_file' in kwargs:
            self._heartbeat_file = kwargs['heartbeat_file']

        self._is_enabled = False
        try:
            cloud_config = Config.instance().get_section_config("CLOUD_SERVER")
            instance_id = cloud_config["instance_id"]
            cloud_user_name = cloud_config["cloud_user_name"]
            cloud_api_key = cloud_config["cloud_api_key"]
            self._is_enabled = True
        except KeyError:
            log.critical("Missing cloud.conf - disabling Deadman Switch")

        self._deadman_process = None
        self.heartbeat()
        self.start()

    def _start_deadman_process(self):
        """
        Start a subprocess and return the object
        """

        #gnsserver gets configuration options from cloud.conf. This is where
        #the client adds specific cloud information.
        #gns3dms also reads in cloud.conf. That is why we don't need to specific
        #all the command line arguments here.

        cmd = []
        cmd.append("gns3dms")
        cmd.append("--file")
        cmd.append("%s" % (self._heartbeat_file))
        cmd.append("--background")
        log.info("Deadman: Running command: %s"%(cmd))

        process = subprocess.Popen(cmd, stderr=subprocess.STDOUT, shell=False)
        return process

    def _stop_deadman_process(self):
        """
        Start a subprocess and return the object
        """

        cmd = []

        cmd.append("gns3dms")
        cmd.append("-k")
        log.info("Deadman: Running command: %s"%(cmd))

        process = subprocess.Popen(cmd, shell=False)
        return process


    def stop(self, signum=None):
        """
        Properly stops the module.

        :param signum: signal number (if called by the signal handler)
        """

        if self._deadman_process == None:
            log.info("Deadman: Can't stop, is not currently running")

        log.debug("Deadman: Stopping process")

        self._deadman_process = self._stop_deadman_process()
        self._deadman_process = None
        #Jerry or Jeremy why do we do this? Won't this stop the I/O loop for
        #for everyone?
        IModule.stop(self, signum)  # this will stop the I/O loop

    def start(self, request=None):
        """
        Start the deadman process on the server
        """

        if self._is_enabled:
            self._deadman_process = self._start_deadman_process()
            log.debug("Deadman: Process is starting")

    @IModule.route("deadman.reset")
    def reset(self, request=None):
        """
        Resets the module (JSON-RPC notification).

        :param request: JSON request (not used)
        """

        self.stop()
        self.start()

        log.info("Deadman: Module has been reset")


    @IModule.route("deadman.heartbeat")
    def heartbeat(self, request=None):
        """
        Update a file on the server that the deadman switch will monitor
        """

        now = time.time()

        with open(self._heartbeat_file, 'w') as heartbeat_file:
            heartbeat_file.write(str(now))
        heartbeat_file.close()

        log.debug("Deadman: heartbeat_file updated: %s %s" % (
                self._heartbeat_file,
                now,
            ))

        self.start()