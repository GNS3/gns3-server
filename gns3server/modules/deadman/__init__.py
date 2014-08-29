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
IOU server module.
"""

import os
import base64
import tempfile

from gns3server.modules import IModule
from gns3server.config import Config


import logging
log = logging.getLogger(__name__)

class DeadMan():
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
        
        # check every 5 seconds
        #self._deadman_callback = self.add_periodic_callback(self._check_deadman_is_alive, 5000)
        self._deadman_callback.start()

    def stop(self, signum=None):
        """
        Properly stops the module.

        :param signum: signal number (if called by the signal handler)
        """

        self._iou_callback.stop()

        # delete all IOU instances
        for iou_id in self._iou_instances:
            iou_instance = self._iou_instances[iou_id]
            iou_instance.delete()

        self.delete_iourc_file()

        IModule.stop(self, signum)  # this will stop the I/O loop


    @IModule.route("iou.reset")
    def reset(self, request=None):
        """
        Resets the module (JSON-RPC notification).

        :param request: JSON request (not used)
        """

        # delete all IOU instances
        for iou_id in self._iou_instances:
            iou_instance = self._iou_instances[iou_id]
            iou_instance.delete()

        # resets the instance IDs
        IOUDevice.reset()

        self._iou_instances.clear()
        self._allocated_udp_ports.clear()
        self.delete_iourc_file()

        log.info("IOU module has been reset")