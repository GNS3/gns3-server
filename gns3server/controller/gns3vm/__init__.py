#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

import sys
import asyncio

from .vmware_gns3_vm import VMwareGNS3VM
from .virtualbox_gns3_vm import VirtualBoxGNS3VM


class GNS3VM:
    """
    Proxy between the controller and the GNS3 VM engine
    """

    def __init__(self, controller, settings={}):
        self._controller = controller
        # Keep instance of the loaded engines
        self._engines = {}
        self._settings = {
            "vmname": None,
            "auto_stop": False,
            "headless": False,
            "enable": False,
            "engine": "vmware"
        }
        self._settings.update(settings)

    def engine_list(self):
        """
        :returns: Return list of engines supported by GNS3 for the GNS3VM
        """
        virtualbox_informations = {
            "engine_id": "virtualbox",
            "name": "VirtualBox",
            "description": "VirtualBox doesn't support nested virtualization, this means running Qemu based VM could be very slow."
        }
        vmware_informations = {
            "engine_id": "vmware",
            "description": "VMware is the recommended choice for best performances."
        }
        if sys.platform.startswith("darwin"):
            vmware_informations["name"] = "VMware Fusion"
        else:
            vmware_informations["name"] = "VMware Workstation / Player"
        return [
            vmware_informations,
            virtualbox_informations
        ]

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, val):
        self._settings.update(val)
        self._controller.save()

    def _get_engine(self, engine):
        """
        Load an engine
        """
        if engine in self._engines:
            return self._engines[engine]

        if engine == "vmware":
            self._engines["vmware"] = VMwareGNS3VM()
            return self._engines["vmware"]
        elif engine == "virtualbox":
            self._engines["virtualbox"] = VirtualBoxGNS3VM()
            return self._engines["virtualbox"]
        raise NotImplementedError("The engine {} for the GNS3 VM is not supported".format(engine))

    def __json__(self):
        return self._settings

    @asyncio.coroutine
    def list(self, engine):
        """
        List VMS for an engine
        """
        engine = self._get_engine(engine)
        vms = []
        for vm in (yield from engine.list()):
            vms.append({"vmname": vm["vmname"]})
        return vms
