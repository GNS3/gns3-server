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

    @property
    def vmrun_path(self):
        """
        Returns the path vmrun utility.

        :returns: path
        """

        return self._vmrun_path

    def find_vmrun(self):
        """
        Searches for vmrun.

        :returns: path to vmrun
        """

        # look for vmrun
        vmrun_path = self.config.get_section_config("VMware").get("vmrun_path")
        if not vmrun_path:
            if sys.platform.startswith("win"):
                pass  # TODO: use registry to find vmrun or search for default location
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
            if sys.platform.startswith("darwin"):
                host_type = "fusion"
            else:
                host_type = self.config.get_section_config("VMware").get("host_type", "ws")
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

    @staticmethod
    def _parse_vmware_file(path):
        """
        Parses a VMware file (VMX, preferences or inventory).

        :param path: path to the VMware file

        :returns: dict
        """

        pairs = {}
        with open(path, encoding="utf-8") as f:
            for line in f.read().splitlines():
                try:
                    key, value = line.split('=', 1)
                    pairs[key.strip()] = value.strip('" ')
                except ValueError:
                    continue
        return pairs

    def _get_vms_from_inventory(self, inventory_path):
        """
        Searches for VMs by parsing a VMware inventory file.

        :param inventory_path: path to the inventory file

        :returns: list of VMs
        """

        vm_entries = {}
        vms = []
        try:
            log.debug('Reading VMware inventory file "{}"'.format(inventory_path))
            pairs = self._parse_vmware_file(inventory_path)
            for key, value in pairs.items():
                if key.startswith("vmlist"):
                    try:
                        vm_entry, variable_name = key.split('.', 1)
                    except ValueError:
                        continue
                    if not vm_entry in vm_entries:
                        vm_entries[vm_entry] = {}
                    vm_entries[vm_entry][variable_name.strip()] = value
        except OSError as e:
            log.warning("Could not read VMware inventory file {}: {}".format(inventory_path, e))

        for vm_settings in vm_entries.values():
            if "DisplayName" in vm_settings and "config" in vm_settings:
                log.debug('Found VM named "{}" with VMX file "{}"'.format(vm_settings["displayName"], vm_settings["config"]))
                vms.append({"vmname": vm_settings["DisplayName"], "vmx_path": vm_settings["config"]})
        return vms

    def _get_vms_from_directory(self, directory):
        """
        Searches for VMs in a given directory.

        :param directory: path to the directory

        :returns: list of VMs
        """

        vms = []
        for path, _, filenames in os.walk(directory):
            for filename in filenames:
                if os.path.splitext(filename)[1] == ".vmx":
                    vmx_path = os.path.join(path, filename)
                    log.debug('Reading VMware VMX file "{}"'.format(vmx_path))
                    try:
                        pairs = self._parse_vmware_file(vmx_path)
                        if "displayName" in pairs:
                            log.debug('Found VM named "{}"'.format(pairs["displayName"]))
                            vms.append({"vmname": pairs["displayName"], "vmx_path": vmx_path})
                    except OSError as e:
                        log.warning('Could not read VMware VMX file "{}": {}'.format(vmx_path, e))
                        continue
        return vms

    def list_vms(self):
        """
        Gets VMware VM list.
        """

        if sys.platform.startswith("win"):
            inventory_path = os.path.expandvars(r"%APPDATA%\Vmware\Inventory.vmls")
        elif sys.platform.startswith("darwin"):
            inventory_path = os.path.expanduser("~/Library/Application\ Support/VMware Fusion/vmInventory")
        else:
            inventory_path = os.path.expanduser("~/.vmware/inventory.vmls")

        if os.path.exists(inventory_path):
            return self._get_vms_from_inventory(inventory_path)
        else:
            # VMware player has no inventory file, let's search the default location for VMs.
            if sys.platform.startswith("win"):
                vmware_preferences_path = os.path.expandvars(r"%APPDATA%\VMware\preferences.ini")
                default_vm_path = os.path.expandvars(r"%USERPROFILE%\Documents\Virtual Machines")
            elif sys.platform.startswith("darwin"):
                vmware_preferences_path = os.path.expanduser("~/Library/Preferences/VMware Fusion/preferences")
                default_vm_path = os.path.expanduser("~/Documents/Virtual Machines.localized")
            else:
                vmware_preferences_path = os.path.expanduser("~/.vmware/preferences")
                default_vm_path = os.path.expanduser("~/vmware")

            if os.path.exists(vmware_preferences_path):
                # the default vm path may be present in VMware preferences file.
                try:
                    pairs = self._parse_vmware_file(vmware_preferences_path)
                    if "prefvmx.defaultvmpath" in pairs:
                        default_vm_path = pairs["prefvmx.defaultvmpath"]
                except OSError as e:
                    log.warning('Could not read VMware preferences file "{}": {}'.format(vmware_preferences_path, e))

            if not os.path.isdir(default_vm_path):
                raise VMwareError('Could not find the default VM directory: "{}"'.format(default_vm_path))
            return self._get_vms_from_directory(default_vm_path)
