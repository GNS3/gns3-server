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
import ipaddress

from ...utils.asyncio import locking
from .vmware_gns3_vm import VMwareGNS3VM
from .virtualbox_gns3_vm import VirtualBoxGNS3VM
from .hyperv_gns3_vm import HyperVGNS3VM
from .remote_gns3_vm import RemoteGNS3VM
from .gns3_vm_error import GNS3VMError
from ...version import __version__
from ..compute import ComputeError

import logging
log = logging.getLogger(__name__)


class GNS3VM:
    """
    Proxy between the controller and the GNS3 VM engine
    """

    def __init__(self, controller):
        self._controller = controller
        # Keep instance of the loaded engines
        self._engines = {}
        self._settings = {
            "vmname": None,
            "when_exit": "stop",
            "headless": False,
            "enable": False,
            "engine": "vmware",
            "allocate_vcpus_ram": True,
            "ram": 2048,
            "vcpus": 1,
            "port": 80,
        }

    def engine_list(self):
        """
        :returns: Return list of engines supported by GNS3 for the GNS3VM
        """

        download_url = "https://github.com/GNS3/gns3-gui/releases/download/v{version}/GNS3.VM.VMware.Workstation.{version}.zip".format(version=__version__)
        vmware_info = {
            "engine_id": "vmware",
            "description": 'VMware is the recommended choice for best performances.<br>The GNS3 VM can be <a href="{}">downloaded here</a>.'.format(download_url),
            "support_when_exit": True,
            "support_headless": True,
            "support_ram": True
        }
        if sys.platform.startswith("darwin"):
            vmware_info["name"] = "VMware Fusion (recommended)"
        else:
            vmware_info["name"] = "VMware Workstation / Player (recommended)"

        download_url = "https://github.com/GNS3/gns3-gui/releases/download/v{version}/GNS3.VM.Hyper-V.{version}.zip".format(version=__version__)
        hyperv_info = {
            "engine_id": "hyper-v",
            "name": "Hyper-V",
            "description": 'Hyper-V support (Windows 10/Server 2016 and above). Nested virtualization must be supported and enabled (Intel processor only)<br>The GNS3 VM can be <a href="{}">downloaded here</a>'.format(download_url),
            "support_when_exit": True,
            "support_headless": False,
            "support_ram": True
        }

        download_url = "https://github.com/GNS3/gns3-gui/releases/download/v{version}/GNS3.VM.VirtualBox.{version}.zip".format(version=__version__)
        virtualbox_info = {
            "engine_id": "virtualbox",
            "name": "VirtualBox",
            "description": 'VirtualBox support. Nested virtualization for both Intel and AMD processors is supported since version 6.1<br>The GNS3 VM can be <a href="{}">downloaded here</a>'.format(download_url),
            "support_when_exit": True,
            "support_headless": True,
            "support_ram": True
        }

        remote_info = {
            "engine_id": "remote",
            "name": "Remote",
            "description": "Use a remote GNS3 server as the GNS3 VM.",
            "support_when_exit": False,
            "support_headless": False,
            "support_ram": False
        }

        engines = [vmware_info,
                   virtualbox_info,
                   remote_info]

        if sys.platform.startswith("win"):
            engines.append(hyperv_info)

        return engines

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

    async def update_settings(self, settings):
        """
        Update settings and will restart the VM if require
        """

        new_settings = copy.copy(self._settings)
        new_settings.update(settings)
        if self.settings != new_settings:
            try:
                await self._stop()
            finally:
                self._settings = settings
                self._controller.save()
            if self.enable:
                await self.start()
        else:
            # When user fix something on his system and try again
            if self.enable and not self.current_engine().running:
                await self.start()

    def _get_engine(self, engine):
        """
        Load an engine
        """

        if engine in self._engines:
            return self._engines[engine]

        if engine == "vmware":
            self._engines["vmware"] = VMwareGNS3VM(self._controller)
            return self._engines["vmware"]
        elif engine == "hyper-v":
            self._engines["hyper-v"] = HyperVGNS3VM(self._controller)
            return self._engines["hyper-v"]
        elif engine == "virtualbox":
            self._engines["virtualbox"] = VirtualBoxGNS3VM(self._controller)
            return self._engines["virtualbox"]
        elif engine == "remote":
            self._engines["remote"] = RemoteGNS3VM(self._controller)
            return self._engines["remote"]
        raise NotImplementedError("The engine {} for the GNS3 VM is not supported".format(engine))

    def __json__(self):
        return self._settings

    @locking
    async def list(self, engine):
        """
        List VMS for an engine
        """

        engine = self._get_engine(engine)
        vms = []
        try:
            for vm in (await engine.list()):
                vms.append({"vmname": vm["vmname"]})
        except GNS3VMError as e:
            # We raise error only if user activated the GNS3 VM
            # otherwise you have noise when VMware is not installed
            if self.enable:
                raise e
        return vms

    async def auto_start_vm(self):
        """
        Auto start the GNS3 VM if require
        """

        if self.enable:
            try:
                await self.start()
            except GNS3VMError as e:
                # User will receive the error later when they will try to use the node
                try:
                    compute = await self._controller.add_compute(compute_id="vm",
                                                                 name="GNS3 VM ({})".format(self.current_engine().vmname),
                                                                 host=None,
                                                                 force=True)
                    compute.set_last_error(str(e))

                except aiohttp.web.HTTPConflict:
                    pass
                log.error("Cannot start the GNS3 VM: {}".format(e))

    async def exit_vm(self):

        if self.enable:
            try:
                if self._settings["when_exit"] == "stop":
                    await self._stop()
                elif self._settings["when_exit"] == "suspend":
                    await self._suspend()
            except GNS3VMError as e:
                log.warning(str(e))

    @locking
    async def start(self):
        """
        Start the GNS3 VM
        """

        engine = self.current_engine()
        if not engine.running:
            if self._settings["vmname"] is None:
                return
            log.info("Start the GNS3 VM")
            engine.allocate_vcpus_ram = self._settings["allocate_vcpus_ram"]
            engine.vmname = self._settings["vmname"]
            engine.ram = self._settings["ram"]
            engine.vcpus = self._settings["vcpus"]
            engine.headless = self._settings["headless"]
            engine.port = self._settings["port"]
            compute = await self._controller.add_compute(compute_id="vm",
                                                         name="GNS3 VM is starting ({})".format(engine.vmname),
                                                         host=None,
                                                         force=True,
                                                         connect=False)

            try:
                await engine.start()
            except Exception as e:
                await self._controller.delete_compute("vm")
                log.error("Cannot start the GNS3 VM: {}".format(str(e)))
                await compute.update(name="GNS3 VM ({})".format(engine.vmname))
                compute.set_last_error(str(e))
                raise e
            await compute.connect()  # we can connect now that the VM has started
            await compute.update(name="GNS3 VM ({})".format(engine.vmname),
                                 protocol=self.protocol,
                                 host=self.ip_address,
                                 port=self.port,
                                 user=self.user,
                                 password=self.password)

            # check if the VM is in the same subnet as the local server, start 10 seconds later to give
            # some time for the compute in the VM to be ready for requests
            asyncio.get_event_loop().call_later(10, lambda: asyncio.ensure_future(self._check_network(compute)))

    async def _check_network(self, compute):
        """
        Check that the VM is in the same subnet as the local server
        """

        try:
            vm_interfaces = await compute.interfaces()
            vm_interface_netmask = None
            for interface in vm_interfaces:
                if interface["ip_address"] == self.ip_address:
                    vm_interface_netmask = interface["netmask"]
                    break
            if vm_interface_netmask:
                vm_network = ipaddress.ip_interface("{}/{}".format(compute.host_ip, vm_interface_netmask)).network
                for compute_id in self._controller.computes:
                    if compute_id == "local":
                        compute = self._controller.get_compute(compute_id)
                        interfaces = await compute.interfaces()
                        netmask = None
                        for interface in interfaces:
                            if interface["ip_address"] == compute.host_ip:
                                netmask = interface["netmask"]
                                break
                        if netmask:
                            compute_network = ipaddress.ip_interface("{}/{}".format(compute.host_ip, netmask)).network
                            if vm_network.compare_networks(compute_network) != 0:
                                msg = "The GNS3 VM (IP={}, NETWORK={}) is not on the same network as the {} server (IP={}, NETWORK={}), please make sure the local server binding is in the same network as the GNS3 VM".format(self.ip_address,
                                                                                                                                                                                                                                vm_network,
                                                                                                                                                                                                                                compute_id,
                                                                                                                                                                                                                                compute.host_ip,
                                                                                                                                                                                                                                compute_network)
                                self._controller.notification.controller_emit("log.warning", {"message": msg})
        except ComputeError as e:
            log.warning("Could not check the VM is in the same subnet as the local server: {}".format(e))
        except aiohttp.web.HTTPConflict as e:
            log.warning("Could not check the VM is in the same subnet as the local server: {}".format(e.text))

    @locking
    async def _suspend(self):
        """
        Suspend the GNS3 VM
        """
        engine = self.current_engine()
        if "vm" in self._controller.computes:
            await self._controller.delete_compute("vm")
        if engine.running:
            log.info("Suspend the GNS3 VM")
            await engine.suspend()

    @locking
    async def _stop(self):
        """
        Stop the GNS3 VM
        """
        engine = self.current_engine()
        if "vm" in self._controller.computes:
            await self._controller.delete_compute("vm")
        if engine.running:
            log.info("Stop the GNS3 VM")
            await engine.stop()
