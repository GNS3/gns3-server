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
import re
import shutil
import asyncio
import subprocess
import logging
import codecs

from collections import OrderedDict
from gns3server.utils.interfaces import interfaces
from gns3server.utils.asyncio import subprocess_check_output
from gns3server.utils import parse_version

log = logging.getLogger(__name__)

from gns3server.modules.base_manager import BaseManager
from gns3server.modules.vmware.vmware_vm import VMwareVM
from gns3server.modules.vmware.vmware_error import VMwareError
from gns3server.modules.vmware.nio_vmnet import NIOVMNET


class VMware(BaseManager):

    _VM_CLASS = VMwareVM

    def __init__(self):

        super().__init__()
        self._execute_lock = asyncio.Lock()
        self._vmware_inventory_lock = asyncio.Lock()
        self._vmrun_path = None
        self._vmnets = []
        self._vmnet_start_range = 2
        if sys.platform.startswith("win"):
            self._vmnet_end_range = 19
        else:
            self._vmnet_end_range = 255

    @property
    def vmrun_path(self):
        """
        Returns the path vmrun utility.

        :returns: path
        """

        return self._vmrun_path

    @staticmethod
    def _find_vmrun_registry(regkey):

        import winreg
        try:
            # default path not used, let's look in the registry
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, regkey)
            install_path, _ = winreg.QueryValueEx(hkey, "InstallPath")
            vmrun_path = os.path.join(install_path, "vmrun.exe")
            winreg.CloseKey(hkey)
            if os.path.exists(vmrun_path):
                return vmrun_path
        except OSError:
            pass
        return None

    def find_vmrun(self):
        """
        Searches for vmrun.

        :returns: path to vmrun
        """

        # look for vmrun
        vmrun_path = self.config.get_section_config("VMware").get("vmrun_path")
        if not vmrun_path:
            if sys.platform.startswith("win"):
                vmrun_path = shutil.which("vmrun")
                if vmrun_path is None:
                    # look for vmrun.exe using the VMware Workstation directory listed in the registry
                    vmrun_path = self._find_vmrun_registry(r"SOFTWARE\Wow6432Node\VMware, Inc.\VMware Workstation")
                    if vmrun_path is None:
                        # look for vmrun.exe using the VIX directory listed in the registry
                        vmrun_path = self._find_vmrun_registry(r"SOFTWARE\Wow6432Node\VMware, Inc.\VMware VIX")
            elif sys.platform.startswith("darwin"):
                vmrun_path = "/Applications/VMware Fusion.app/Contents/Library/vmrun"
            else:
                vmrun_path = shutil.which("vmrun")

        if not vmrun_path:
            raise VMwareError("Could not find VMware vmrun, please make sure it is installed")
        if not os.path.isfile(vmrun_path):
            raise VMwareError("vmrun {} is not accessible".format(vmrun_path))
        if not os.access(vmrun_path, os.X_OK):
            raise VMwareError("vmrun is not executable")
        if os.path.basename(vmrun_path).lower() not in ["vmrun", "vmrun.exe"]:
            raise VMwareError("Invalid vmrun executable name {}".format(os.path.basename(vmrun_path)))

        self._vmrun_path = vmrun_path
        return vmrun_path

    @staticmethod
    def _find_vmware_version_registry(regkey):

        import winreg
        version = None
        try:
            # default path not used, let's look in the registry
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, regkey)
            version, _ = winreg.QueryValueEx(hkey, "ProductVersion")
            winreg.CloseKey(hkey)
        except OSError:
            pass
        if version is not None:
            match = re.search("([0-9]+)\.", version)
            if match:
                version = match.group(1)
        return version

    @asyncio.coroutine
    def _check_vmware_player_requirements(self, player_version):
        """
        Check minimum requirements to use VMware Player.

        VIX 1.13 was the release for Player 6.
        VIX 1.14 was the release for Player 7.
        VIX 1.15 was the release for Workstation Player 12.

        :param player_version: VMware Player major version.
        """

        player_version = int(player_version)
        if player_version < 6:
            raise VMwareError("Using VMware Player requires version 6 or above")
        elif player_version == 6:
            yield from self.check_vmrun_version(minimum_required_version="1.13.0")
        elif player_version == 7:
            yield from self.check_vmrun_version(minimum_required_version="1.14.0")
        elif player_version >= 12:
            yield from self.check_vmrun_version(minimum_required_version="1.15.0")

    @asyncio.coroutine
    def _check_vmware_workstation_requirements(self, ws_version):
        """
        Check minimum requirements to use VMware Workstation.

        VIX 1.13 was the release for Workstation 10.
        VIX 1.14 was the release for Workstation 11.
        VIX 1.15 was the release for Workstation Pro 12.

        :param ws_version: VMware Workstation major version.
        """

        ws_version = int(ws_version)
        if ws_version < 10:
            raise VMwareError("Using VMware Workstation requires version 10 or above")
        elif ws_version == 10:
            yield from self.check_vmrun_version(minimum_required_version="1.13.0")
        elif ws_version == 11:
            yield from self.check_vmrun_version(minimum_required_version="1.14.0")
        elif ws_version >= 12:
            yield from self.check_vmrun_version(minimum_required_version="1.15.0")

    @asyncio.coroutine
    def check_vmware_version(self):
        """
        Check VMware version
        """

        if sys.platform.startswith("win"):
            # look for vmrun.exe using the directory listed in the registry
            ws_version = self._find_vmware_version_registry(r"SOFTWARE\Wow6432Node\VMware, Inc.\VMware Workstation")
            if ws_version is None:
                player_version = self._find_vmware_version_registry(r"SOFTWARE\Wow6432Node\VMware, Inc.\VMware Player")
                if player_version:
                    log.debug("VMware Player version {} detected".format(player_version))
                    yield from self._check_vmware_player_requirements(player_version)
                else:
                    log.warning("Could not find VMware version")
            else:
                log.debug("VMware Workstation version {} detected".format(ws_version))
                yield from self._check_vmware_workstation_requirements(ws_version)
        else:
            if sys.platform.startswith("darwin"):
                if not os.path.isdir("/Applications/VMware Fusion.app"):
                    raise VMwareError("VMware Fusion is not installed in the standard location /Applications/VMware Fusion.app")
                return  # FIXME: no version checking on Mac OS X but we support all versions of fusion

            vmware_path = VMware._get_linux_vmware_binary()
            if vmware_path is None:
                raise VMwareError("VMware is not installed (vmware or vmplayer executable could not be found in $PATH)")

            try:
                output = yield from subprocess_check_output(vmware_path, "-v")
                match = re.search("VMware Workstation ([0-9]+)\.", output)
                version = None
                if match:
                    # VMware Workstation has been detected
                    version = match.group(1)
                    log.debug("VMware Workstation version {} detected".format(version))
                    yield from self._check_vmware_workstation_requirements(version)
                match = re.search("VMware Player ([0-9]+)\.", output)
                if match:
                    # VMware Player has been detected
                    version = match.group(1)
                    log.debug("VMware Player version {} detected".format(version))
                    yield from self._check_vmware_player_requirements(version)
                if version is None:
                    log.warning("Could not find VMware version. Output of VMware: {}".format(output))
                    raise VMwareError("Could not find VMware version. Output of VMware: {}".format(output))
            except (OSError, subprocess.SubprocessError) as e:
                log.error("Error while looking for the VMware version: {}".format(e))
                raise VMwareError("Error while looking for the VMware version: {}".format(e))

    @staticmethod
    def _get_vmnet_interfaces_registry():

        import winreg
        vmnet_interfaces = []
        regkey = r"SOFTWARE\Wow6432Node\VMware, Inc.\VMnetLib\VMnetConfig"
        try:
            hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, regkey)
            for index in range(winreg.QueryInfoKey(hkey)[0]):
                vmnet = winreg.EnumKey(hkey, index)
                hkeyvmnet = winreg.OpenKey(hkey, vmnet)
                if winreg.QueryInfoKey(hkeyvmnet)[1]:
                    # the vmnet has not been configure if the key has no values
                    vmnet = vmnet.replace("vm", "VM")
                    if vmnet not in ("VMnet1", "VMnet8"):
                        vmnet_interfaces.append(vmnet)
                winreg.CloseKey(hkeyvmnet)
            winreg.CloseKey(hkey)
        except OSError as e:
            raise VMwareError("Could not read registry key {}: {}".format(regkey, e))
        return vmnet_interfaces

    @staticmethod
    def _get_vmnet_interfaces():

        if sys.platform.startswith("win"):
            return VMware._get_vmnet_interfaces_registry()
        elif sys.platform.startswith("darwin"):
            vmware_networking_file = "/Library/Preferences/VMware Fusion/networking"
        else:
            # location on Linux
            vmware_networking_file = "/etc/vmware/networking"
        vmnet_interfaces = []
        try:
            with open(vmware_networking_file, "r", encoding="utf-8") as f:
                for line in f.read().splitlines():
                    match = re.search("VNET_([0-9]+)_VIRTUAL_ADAPTER", line)
                    if match:
                        vmnet = "vmnet{}".format(match.group(1))
                        if vmnet not in ("vmnet1", "vmnet8"):
                            vmnet_interfaces.append(vmnet)
        except OSError as e:
            raise VMwareError("Cannot open {}: {}".format(vmware_networking_file, e))
        return vmnet_interfaces

    @staticmethod
    def _get_vmnet_interfaces_ubridge():

        vmnet_interfaces = []
        for interface in interfaces():
            if sys.platform.startswith("win"):
                if "netcard" in interface:
                    windows_name = interface["netcard"]
                else:
                    windows_name = interface["name"]
                match = re.search("(VMnet[0-9]+)", windows_name)
                if match:
                    vmnet = match.group(1)
                    if vmnet not in ("VMnet1", "VMnet8"):
                        vmnet_interfaces.append(vmnet)
            elif interface["name"].startswith("vmnet"):
                vmnet = interface["name"]
                if vmnet not in ("vmnet1", "vmnet8"):
                    vmnet_interfaces.append(interface["name"])
        return vmnet_interfaces

    def is_managed_vmnet(self, vmnet):

        self._vmnet_start_range = self.config.get_section_config("VMware").getint("vmnet_start_range", self._vmnet_start_range)
        self._vmnet_end_range = self.config.get_section_config("VMware").getint("vmnet_end_range", self._vmnet_end_range)
        match = re.search("vmnet([0-9]+)$", vmnet, re.IGNORECASE)
        if match:
            vmnet_number = match.group(1)
            if self._vmnet_start_range <= int(vmnet_number) <= self._vmnet_end_range:
                return True
        return False

    def allocate_vmnet(self):

        if not self._vmnets:
            raise VMwareError("No VMnet interface available between vmnet{} and vmnet{}. Go to preferences VMware / Network / Configure to add more interfaces.".format(self._vmnet_start_range, self._vmnet_end_range))
        return self._vmnets.pop(0)

    def refresh_vmnet_list(self, ubridge=True):

        if ubridge:
            # VMnet host adapters must be present when uBridge is used
            vmnet_interfaces = self._get_vmnet_interfaces_ubridge()
        else:
            vmnet_interfaces = self._get_vmnet_interfaces()

        # remove vmnets already in use
        for vm in self._vms.values():
            for used_vmnet in vm.vmnets:
                if used_vmnet in vmnet_interfaces:
                    log.debug("{} is already in use".format(used_vmnet))
                    vmnet_interfaces.remove(used_vmnet)

        # remove vmnets that are not managed
        for vmnet in vmnet_interfaces.copy():
            if vmnet in vmnet_interfaces and self.is_managed_vmnet(vmnet) is False:
                vmnet_interfaces.remove(vmnet)

        self._vmnets = vmnet_interfaces

    def create_nio(self, executable, nio_settings):

        if nio_settings["type"] == "nio_vmnet":
            return NIOVMNET(nio_settings["vmnet"])
        else:
            return super().create_nio(None, nio_settings)

    @property
    def host_type(self):
        """
        Returns the VMware host type.
        player = VMware player
        ws = VMware Workstation
        fusion = VMware Fusion

        :returns: host type (string)
        """

        if sys.platform.startswith("darwin"):
            host_type = "fusion"
        else:
            host_type = self.config.get_section_config("VMware").get("host_type", "ws")
        return host_type

    @asyncio.coroutine
    def execute(self, subcommand, args, timeout=120, host_type=None):

        with (yield from self._execute_lock):
            vmrun_path = self.vmrun_path
            if not vmrun_path:
                vmrun_path = self.find_vmrun()
            if host_type is None:
                host_type = self.host_type

            command = [vmrun_path, "-T", host_type, subcommand]
            command.extend(args)
            command_string = " ".join(command)
            log.info("Executing vmrun with command: {}".format(command_string))
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

    @asyncio.coroutine
    def check_vmrun_version(self, minimum_required_version="1.13.0"):
        """
        Checks the vmrun version.

        VMware VIX library version must be at least >= 1.13 by default
        VIX 1.13 was the release for VMware Fusion 6, Workstation 10, and Player 6.
        VIX 1.14 was the release for VMware Fusion 7, Workstation 11 and Player 7.
        VIX 1.15 was the release for VMware Fusion 8, Workstation Pro 12 and Workstation Player 12.

        :param required_version: required vmrun version number
        """

        with (yield from self._execute_lock):
            vmrun_path = self.vmrun_path
            if not vmrun_path:
                vmrun_path = self.find_vmrun()

            try:
                output = yield from subprocess_check_output(vmrun_path)
                match = re.search("vmrun version ([0-9\.]+)", output)
                version = None
                if match:
                    version = match.group(1)
                    log.debug("VMware vmrun version {} detected, minimum required: {}".format(version, minimum_required_version))
                    if parse_version(version) < parse_version(minimum_required_version):
                        raise VMwareError("VMware vmrun executable version must be >= version {}".format(minimum_required_version))
                if version is None:
                    log.warning("Could not find VMware vmrun version. Output: {}".format(output))
                    raise VMwareError("Could not find VMware vmrun version. Output: {}".format(output))
            except (OSError, subprocess.SubprocessError) as e:
                log.error("Error while looking for the VMware vmrun version: {}".format(e))
                raise VMwareError("Error while looking for the VMware vmrun version: {}".format(e))

    @asyncio.coroutine
    def remove_from_vmware_inventory(self, vmx_path):
        """
        Removes a linked clone from the VMware inventory file.

        :param vmx_path: path of the linked clone VMX file
        """

        with (yield from self._vmware_inventory_lock):
            inventory_path = self.get_vmware_inventory_path()
            if os.path.exists(inventory_path):
                try:
                    inventory_pairs = self.parse_vmware_file(inventory_path)
                except OSError as e:
                    log.warning('Could not read VMware inventory file "{}": {}'.format(inventory_path, e))
                    return

                vmlist_entry = None
                for name, value in inventory_pairs.items():
                    if value == vmx_path:
                        vmlist_entry = name.split(".", 1)[0]
                        break

                if vmlist_entry is not None:
                    for name in inventory_pairs.copy().keys():
                        if name.startswith(vmlist_entry):
                            del inventory_pairs[name]

                try:
                    self.write_vmware_file(inventory_path, inventory_pairs)
                except OSError as e:
                    raise VMwareError('Could not write VMware inventory file "{}": {}'.format(inventory_path, e))

    @staticmethod
    def parse_vmware_file(path):
        """
        Parses a VMware file (VMX, preferences or inventory).

        :param path: path to the VMware file

        :returns: dict
        """

        pairs = OrderedDict()
        encoding = "utf-8"
        # get the first line to read the .encoding value
        with open(path, "rb") as f:
            line = f.readline().decode(encoding, errors="ignore")
            if line.startswith("#!"):
                # skip the shebang
                line = f.readline().decode(encoding, errors="ignore")
            try:
                key, value = line.split('=', 1)
                if key.strip().lower() == ".encoding":
                    file_encoding = value.strip('" ')
                    try:
                        codecs.lookup(file_encoding)
                        encoding = file_encoding
                    except LookupError:
                        log.warning("Invalid file encoding detected in '{}': {}".format(path, file_encoding))
            except ValueError:
                log.warning("Couldn't find file encoding in {}, using {}...".format(path, encoding))

        # read the file with the correct encoding
        with open(path, encoding=encoding, errors="ignore") as f:
            for line in f.read().splitlines():
                try:
                    key, value = line.split('=', 1)
                    pairs[key.strip().lower()] = value.strip('" ')
                except ValueError:
                    continue
        return pairs

    @staticmethod
    def write_vmware_file(path, pairs):
        """
        Write a VMware file (excepting VMX file).

        :param path: path to the VMware file
        :param pairs: settings to write
        """

        encoding = "utf-8"
        if ".encoding" in pairs:
            file_encoding = pairs[".encoding"]
            try:
                codecs.lookup(file_encoding)
                encoding = file_encoding
            except LookupError:
                log.warning("Invalid file encoding detected in '{}': {}".format(path, file_encoding))
        with open(path, "w", encoding=encoding, errors="ignore") as f:
            for key, value in pairs.items():
                entry = '{} = "{}"\n'.format(key, value)
                f.write(entry)

    @staticmethod
    def write_vmx_file(path, pairs):
        """
        Write a VMware VMX file.

        :param path: path to the VMX file
        :param pairs: settings to write
        """

        encoding = "utf-8"
        if ".encoding" in pairs:
            file_encoding = pairs[".encoding"]
            try:
                codecs.lookup(file_encoding)
                encoding = file_encoding
            except LookupError:
                log.warning("Invalid file encoding detected in '{}': {}".format(path, file_encoding))
        with open(path, "w", encoding=encoding, errors="ignore") as f:
            if sys.platform.startswith("linux"):
                # write the shebang on the first line on Linux
                vmware_path = VMware._get_linux_vmware_binary()
                if vmware_path:
                    f.write("#!{}\n".format(vmware_path))
            for key, value in pairs.items():
                entry = '{} = "{}"\n'.format(key, value)
                f.write(entry)

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
            pairs = self.parse_vmware_file(inventory_path)
            for key, value in pairs.items():
                if key.startswith("vmlist"):
                    try:
                        vm_entry, variable_name = key.split('.', 1)
                    except ValueError:
                        continue
                    if vm_entry not in vm_entries:
                        vm_entries[vm_entry] = {}
                    vm_entries[vm_entry][variable_name.strip()] = value
        except OSError as e:
            log.warning("Could not read VMware inventory file {}: {}".format(inventory_path, e))

        for vm_settings in vm_entries.values():
            if "displayname" in vm_settings and "config" in vm_settings:
                log.debug('Found VM named "{}" with VMX file "{}"'.format(vm_settings["displayname"], vm_settings["config"]))
                vms.append({"vmname": vm_settings["displayname"], "vmx_path": vm_settings["config"]})
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
                        pairs = self.parse_vmware_file(vmx_path)
                        if "displayname" in pairs:
                            log.debug('Found VM named "{}"'.format(pairs["displayname"]))
                            vms.append({"vmname": pairs["displayname"], "vmx_path": vmx_path})
                    except OSError as e:
                        log.warning('Could not read VMware VMX file "{}": {}'.format(vmx_path, e))
                        continue
        return vms

    @staticmethod
    def get_vmware_inventory_path():
        """
        Returns VMware inventory file path.

        :returns: path to the inventory file
        """

        if sys.platform.startswith("win"):
            return os.path.expandvars(r"%APPDATA%\Vmware\Inventory.vmls")
        elif sys.platform.startswith("darwin"):
            return os.path.expanduser("~/Library/Application Support/VMware Fusion/vmInventory")
        else:
            return os.path.expanduser("~/.vmware/inventory.vmls")

    @staticmethod
    def get_vmware_preferences_path():
        """
        Returns VMware preferences file path.

        :returns: path to the preferences file
        """

        if sys.platform.startswith("win"):
            return os.path.expandvars(r"%APPDATA%\VMware\preferences.ini")
        elif sys.platform.startswith("darwin"):
            return os.path.expanduser("~/Library/Preferences/VMware Fusion/preferences")
        else:
            return os.path.expanduser("~/.vmware/preferences")

    @staticmethod
    def get_vmware_default_vm_path():
        """
        Returns VMware default VM directory path.

        :returns: path to the default VM directory
        """

        if sys.platform.startswith("win"):
            import ctypes
            import ctypes.wintypes
            path = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, path)
            documents_folder = path.value
            windows_type = sys.getwindowsversion().product_type
            if windows_type == 2 or windows_type == 3:
                return '{}\My Virtual Machines'.format(documents_folder)
            else:
                return '{}\Virtual Machines'.format(documents_folder)
        elif sys.platform.startswith("darwin"):
            return os.path.expanduser("~/Documents/Virtual Machines.localized")
        else:
            return os.path.expanduser("~/vmware")

    @asyncio.coroutine
    def list_vms(self):
        """
        Gets VMware VM list.
        """

        # check for the right VMware version
        yield from self.check_vmware_version()

        inventory_path = self.get_vmware_inventory_path()
        if os.path.exists(inventory_path) and self.host_type != "player":
            # inventory may exist for VMware player if VMware workstation has been previously installed
            return self._get_vms_from_inventory(inventory_path)
        else:
            # VMware player has no inventory file, let's search the default location for VMs
            vmware_preferences_path = self.get_vmware_preferences_path()
            default_vm_path = self.get_vmware_default_vm_path()
            pairs = {}
            if os.path.exists(vmware_preferences_path):
                # the default vm path may be present in VMware preferences file.
                try:
                    pairs = self.parse_vmware_file(vmware_preferences_path)
                except OSError as e:
                    log.warning('Could not read VMware preferences file "{}": {}'.format(vmware_preferences_path, e))
                if "prefvmx.defaultvmpath" in pairs:
                    default_vm_path = pairs["prefvmx.defaultvmpath"]
            if not os.path.isdir(default_vm_path):
                raise VMwareError('Could not find the default VM directory: "{}"'.format(default_vm_path))
            vms = self._get_vms_from_directory(default_vm_path)

            # looks for VMX paths in the preferences file in case not all VMs are in the default directory
            for key, value in pairs.items():
                m = re.match(r'pref.mruVM(\d+)\.filename', key)
                if m:
                    display_name = "pref.mruVM{}.displayName".format(m.group(1))
                    if display_name in pairs:
                        found = False
                        for vm in vms:
                            if vm["vmname"] == display_name:
                                found = True
                        if found is False:
                            vms.append({"vmname": pairs[display_name], "vmx_path": value})
            return vms

    @staticmethod
    def _get_linux_vmware_binary():
        """
        Return the path of the vmware binary on Linux or None
        """
        path = shutil.which("vmware")
        if path is None:
            path = shutil.which("vmplayer")
        return path


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    vmware = VMware.instance()
    print("=> Check version")
    loop.run_until_complete(asyncio.async(vmware.check_vmware_version()))
