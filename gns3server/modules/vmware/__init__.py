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
VMware player/workstation server module.
"""

import os
import sys
import shutil
import asyncio
import subprocess
import logging

log = logging.getLogger(__name__)

from ..base_manager import BaseManager
from .vmware_vm import VMwareVM
from .vmware_error import VMwareError


class VMware(BaseManager):

    _VM_CLASS = VMwareVM

    def __init__(self):

        super().__init__()
        self._vmrun_path = None
        self._host_type = "player"

    @property
    def vmrun_path(self):
        """
        Returns the path vmrun utility.

        :returns: path
        """

        return self._vmrun_path

    def find_vmrun(self):

        # look for vmrun
        vmrun_path = self.config.get_section_config("VMware").get("vmrun_path")
        if not vmrun_path:
            if sys.platform.startswith("win"):
                pass  # TODO: use registry to find vmrun
            elif sys.platform.startswith("darwin"):
                vmrun_path = "/Applications/VMware Fusion.app/Contents/Library/vmrun"
            else:
                vmrun_path = shutil.which("vmrun")

        if not vmrun_path:
            raise VMwareError("Could not find vmrun")
        if not os.path.isfile(vmrun_path):
            raise VMwareError("vmrun {} is not accessible".format(vmrun_path))
        if not os.access(vmrun_path, os.X_OK):
            raise VMwareError("vmrun is not executable")
        if os.path.basename(vmrun_path) not in ["vmrun", "vmrun.exe"]:
            raise VMwareError("Invalid vmrun executable name {}".format(os.path.basename(vmrun_path)))

        self._vmrun_path = vmrun_path
        return vmrun_path

    @asyncio.coroutine
    def execute(self, subcommand, args, timeout=60, host_type=None):

        vmrun_path = self.vmrun_path
        if not vmrun_path:
            vmrun_path = self.find_vmrun()
        if host_type is None:
            host_type = self._host_type
        command = [vmrun_path, "-T", host_type, subcommand]
        command.extend(args)
        log.debug("Executing vmrun with command: {}".format(command))
        try:
            process = yield from asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except (OSError, subprocess.SubprocessError) as e:
            raise VMwareError("Could not execute vmrun: {}".format(e))

        try:
            stdout_data, _ = yield from asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            raise VMwareError("vmrun has timed out after {} seconds!".format(timeout))

        if process.returncode:
            # vmrun print errors on stdout
            vmrun_error = stdout_data.decode("utf-8", errors="ignore")
            raise VMwareError("vmrun has returned an error: {}".format(vmrun_error))

        return stdout_data.decode("utf-8", errors="ignore").splitlines()
