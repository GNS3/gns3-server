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
import copy
import asyncio
import aiohttp

from ...utils.asyncio import locked_coroutine
from .vmware_gns3_vm import VMwareGNS3VM
from .virtualbox_gns3_vm import VirtualBoxGNS3VM
from .remote_gns3_vm import RemoteGNS3VM
from .gns3_vm_error import GNS3VMError
from ...version import __version__

import logging
log = logging.getLogger(__name__)


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
            "when_exit": "stop",
            "headless": False,
            "enable": False,
            "engine": "vmware",
            "ram": 2048,
            "vcpus": 1
        }
        self.settings = settings

    def engine_list(self):
        """
        :returns: Return list of engines supported by GNS3 for the GNS3VM
        """

        download_url = "https://github.com/GNS3/gns3-gui/releases/download/v{version}/GNS3.VM.VMware.Workstation.{version}.zip".format(version=__version__)
        vmware_informations = {
            "engine_id": "vmware",
            "description": 'VMware is the recommended choice for best performances.<br>The GNS3 VM can be <a href="{}">downloaded here</a>.'.format(download_url),
            "support_when_exit": True,
            "support_headless": True,
            "support_ram": True
        }
        if sys.platform.startswith("darwin"):
            vmware_informations["name"] = "VMware Fusion"
        else:
            vmware_informations["name"] = "VMware Workstation / Player"

        download_url = "https://github.com/GNS3/gns3-gui/releases/download/v{version}/GNS3.VM.VirtualBox.{version}.zip".format(version=__version__)
        virtualbox_informations = {
            "engine_id": "virtualbox",
            "name": "VirtualBox",
            "description": 'VirtualBox doesn\'t support nested virtualization, this means running Qemu based VM could be very slow.<br>The GNS3 VM can be <a href="{}">downloaded here</a>'.format(download_url),
            "support_when_exit": True,
            "support_headless": True,
            "support_ram": True
        }

        remote_informations = {
            "engine_id": "remote",
            "name": "Remote",
            "description": "Use a remote GNS3 server as the GNS3 VM.",
            "support_when_exit": False,
            "support_headless": False,
            "support_ram": False
        }

        return [
            vmware_informations,
            virtualbox_informations,
            remote_informations
        ]

    def current_engine(self):
        return self._get_engine(self._settings["engine"])

    @property
    def engine(self):
        return self._settings["engine"]

    @property
    def ip_address(self):
        """
        Returns the GNS3 VM IP address.

        :returns: VM IP address
        """
        return self.current_engine().ip_address

    @property
    def running(self):
        """
        Returns if the GNS3 VM is running.

        :returns: Boolean
        """
        return self.current_engine().running

    @property
    def user(self):
        """
        Returns the GNS3 VM user.

        :returns: VM user
        """
        return self.current_engine().user

    @property
    def password(self):
        """
        Returns the GNS3 VM password.

        :returns: VM password
        """
        return self.current_engine().password

    @property
    def port(self):
        """
        Returns the GNS3 VM port.

        :returns: VM port
        """
        return self.current_engine().port

    @property
    def protocol(self):
        """
        Returns the GNS3 VM protocol.

        :returns: VM protocol
        """
        return self.current_engine().protocol

    @property
    def enable(self):
        """
        The GNSVM is activated
        """
        return self._settings.get("enable", False)

    @property
    def when_exit(self):
        """
        What should be done when exit
        """
        return self._settings["when_exit"]

    @property
    def settings(self):
        return self._settings

    @settings.setter
    def settings(self, val):
        self._settings.update(val)

    @asyncio.coroutine
    def update_settings(self, settings):
        """
        Update settings and will restart the VM if require
        """
        new_settings = copy.copy(self._settings)
        new_settings.update(settings)
        if self.settings != new_settings:
            yield from self._stop()
            self._settings = settings
            self._controller.save()
            if self.enable:
                yield from self.start()
        else:
            # When user fix something on his system and try again
            if self.enable and not self.current_engine().running:
                yield from self.start()

    def _get_engine(self, engine):
        """
        Load an engine
        """
        if engine in self._engines:
            return self._engines[engine]

        if engine == "vmware":
            self._engines["vmware"] = VMwareGNS3VM(self._controller)
            return self._engines["vmware"]
        elif engine == "virtualbox":
            self._engines["virtualbox"] = VirtualBoxGNS3VM(self._controller)
            return self._engines["virtualbox"]
        elif engine == "remote":
            self._engines["remote"] = RemoteGNS3VM(self._controller)
            return self._engines["remote"]
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
        try:
            for vm in (yield from engine.list()):
                vms.append({"vmname": vm["vmname"]})
        except GNS3VMError as e:
            # We raise error only if user activated the GNS3 VM
            # otherwise you have noise when VMware is not installed
            if self.enable:
                raise e
        return vms

    @asyncio.coroutine
    def auto_start_vm(self):
        """
        Auto start the GNS3 VM if require
        """
        if self.enable:
            try:
                yield from self.start()
            except GNS3VMError as e:
                # User will receive the error later when they will try to use the node
                try:
                    yield from self._controller.add_compute(compute_id="vm",
                                                            name="GNS3 VM ({})".format(self.current_engine().vmname),
                                                            host=None,
                                                            force=True)
                except aiohttp.web.HTTPConflict:
                    pass
                log.error("Can't start the GNS3 VM: %s", str(e))

    @asyncio.coroutine
    def exit_vm(self):
        if self.enable:
            try:
                if self._settings["when_exit"] == "stop":
                    yield from self._stop()
                elif self._settings["when_exit"] == "suspend":
                    yield from self._suspend()
            except GNS3VMError as e:
                log.warn(str(e))

    @locked_coroutine
    def start(self):
        """
        Start the GNS3 VM
        """
        engine = self.current_engine()
        if not engine.running:
            if self._settings["vmname"] is None:
                return

            log.info("Start the GNS3 VM")
            engine.vmname = self._settings["vmname"]
            engine.ram = self._settings["ram"]
            engine.vpcus = self._settings["vcpus"]
            engine.headless = self._settings["headless"]
            compute = yield from self._controller.add_compute(compute_id="vm",
                                                              name="GNS3 VM is starting ({})".format(engine.vmname),
                                                              host=None,
                                                              force=True)

            try:
                yield from engine.start()
            except Exception as e:
                yield from self._controller.delete_compute("vm")
                log.error("Can't start the GNS3 VM: {}".format(str(e)))
                yield from compute.update(name="GNS3 VM ({})".format(engine.vmname))
                raise e
            yield from compute.update(name="GNS3 VM ({})".format(engine.vmname),
                                      protocol=self.protocol,
                                      host=self.ip_address,
                                      port=self.port,
                                      user=self.user,
                                      password=self.password)

    @locked_coroutine
    def _suspend(self):
        """
        Suspend the GNS3 VM
        """
        engine = self.current_engine()
        if "vm" in self._controller.computes:
            yield from self._controller.delete_compute("vm")
        if engine.running:
            log.info("Suspend the GNS3 VM")
            yield from engine.suspend()

    @locked_coroutine
    def _stop(self):
        """
        Stop the GNS3 VM
        """
        engine = self.current_engine()
        if "vm" in self._controller.computes:
            yield from self._controller.delete_compute("vm")
        if engine.running:
            log.info("Stop the GNS3 VM")
            yield from engine.stop()
