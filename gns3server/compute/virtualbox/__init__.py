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
VirtualBox server module.
"""

import os
import re
import sys
import shutil
import asyncio
import subprocess
import logging

log = logging.getLogger(__name__)

from ..base_manager import BaseManager
from .virtualbox_vm import VirtualBoxVM
from .virtualbox_error import VirtualBoxError


class VirtualBox(BaseManager):

    _NODE_CLASS = VirtualBoxVM

    def __init__(self):

        super().__init__()
        self._vboxmanage_path = None
        self._execute_lock = asyncio.Lock()

    @property
    def vboxmanage_path(self):
        """
        Returns the path to VBoxManage.

        :returns: path
        """

        return self._vboxmanage_path

    def find_vboxmanage(self):

        # look for VBoxManage
        vboxmanage_path = self.config.settings.VirtualBox.vboxmanage_path
        if vboxmanage_path:
            if not os.path.isabs(vboxmanage_path):
                vboxmanage_path = shutil.which(vboxmanage_path)
        else:
            log.info("A path to VBoxManage has not been configured, trying to find it...")
            if sys.platform.startswith("darwin"):
                vboxmanage_path_osx = "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
                if os.path.exists(vboxmanage_path_osx):
                    vboxmanage_path = vboxmanage_path_osx
            if not vboxmanage_path:
                vboxmanage_path = shutil.which("vboxmanage")

        if vboxmanage_path and not os.path.exists(vboxmanage_path):
            log.error(f"VBoxManage path '{vboxmanage_path}' doesn't exist")

        if not vboxmanage_path:
            raise VirtualBoxError("Could not find VBoxManage, please reboot if VirtualBox has just been installed")
        if not os.path.isfile(vboxmanage_path):
            raise VirtualBoxError(f"VBoxManage '{vboxmanage_path}' is not accessible")
        if not os.access(vboxmanage_path, os.X_OK):
            raise VirtualBoxError("VBoxManage is not executable")
        if os.path.basename(vboxmanage_path) not in ["VBoxManage", "VBoxManage.exe", "vboxmanage"]:
            raise VirtualBoxError(f"Invalid VBoxManage executable name {os.path.basename(vboxmanage_path)}")

        self._vboxmanage_path = vboxmanage_path
        return vboxmanage_path

    async def execute(self, subcommand, args, timeout=60):

        # We use a lock prevent parallel execution due to strange errors
        # reported by a user and reproduced by us.
        # https://github.com/GNS3/gns3-gui/issues/261
        async with self._execute_lock:
            vboxmanage_path = self.vboxmanage_path
            if not vboxmanage_path:
                vboxmanage_path = self.find_vboxmanage()
            if not vboxmanage_path:
                raise VirtualBoxError("Could not find VBoxManage")

            command = [vboxmanage_path, "--nologo", subcommand]
            command.extend(args)
            command_string = " ".join(command)
            log.info(f"Executing VBoxManage with command: {command_string}")
            env = os.environ.copy()
            env["LANG"] = "en"  # force english output because we rely on it to parse the output
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
                )
            except (OSError, subprocess.SubprocessError) as e:
                raise VirtualBoxError(f"Could not execute VBoxManage: {e}")

            try:
                stdout_data, stderr_data = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                raise VirtualBoxError(f"VBoxManage has timed out after {timeout} seconds!")

            if process.returncode:
                vboxmanage_error = stderr_data.decode("utf-8", errors="ignore")
                raise VirtualBoxError(f"VirtualBox has returned an error: {vboxmanage_error}")

            return stdout_data.decode("utf-8", errors="ignore").splitlines()

    async def _find_inaccessible_hdd_files(self):
        """
        Finds inaccessible disk files (to clean up the VirtualBox media manager)
        """

        hdds = []
        try:
            properties = await self.execute("list", ["hdds"])
        # If VirtualBox is not available we have no inaccessible hdd
        except VirtualBoxError:
            return hdds

        flag_inaccessible = False
        for prop in properties:
            try:
                name, value = prop.split(":", 1)
            except ValueError:
                continue
            if name.strip() == "State" and value.strip() == "inaccessible":
                flag_inaccessible = True
            if flag_inaccessible and name.strip() == "Location":
                hdds.append(value.strip())
                flag_inaccessible = False
        return reversed(hdds)

    async def project_closed(self, project):
        """
        Called when a project is closed.

        :param project: Project instance
        """

        await super().project_closed(project)
        hdd_files_to_close = await self._find_inaccessible_hdd_files()
        for hdd_file in hdd_files_to_close:
            log.info(f"Closing VirtualBox VM disk file {os.path.basename(hdd_file)}")
            try:
                await self.execute("closemedium", ["disk", hdd_file])
            except VirtualBoxError as e:
                log.warning(f"Could not close VirtualBox VM disk file {os.path.basename(hdd_file)}: {e}")
                continue

    async def list_vms(self, allow_clone=False):
        """
        Gets VirtualBox VM list.
        """

        vbox_vms = []
        result = await self.execute("list", ["vms"])
        for line in result:
            if len(line) == 0 or line[0] != '"' or line[-1:] != "}":
                continue  # Broken output (perhaps a carriage return in VM name)
            match = re.search(r"\"(.*)\"\ {(.*)}", line)
            if not match:
                continue
            vmname = match.group(1)
            uuid = match.group(2)
            if vmname == "<inaccessible>":
                continue  # ignore inaccessible VMs
            extra_data = await self.execute("getextradata", [uuid, "GNS3/Clone"])
            if allow_clone or len(extra_data) == 0 or not extra_data[0].strip() == "Value: yes":
                # get the amount of RAM
                info_results = await self.execute("showvminfo", [uuid, "--machinereadable"])
                ram = 0
                for info in info_results:
                    try:
                        name, value = info.split("=", 1)
                        if name.strip() == "memory":
                            ram = int(value.strip())
                            break
                    except ValueError:
                        continue
                vbox_vms.append({"vmname": vmname, "ram": ram})
        return vbox_vms

    @staticmethod
    def get_legacy_vm_workdir(legacy_vm_id, name):
        """
        Returns the name of the legacy working directory name for a node.

        :param legacy_vm_id: legacy node identifier (not used)
        :param name: node name

        :returns: working directory name
        """

        return os.path.join("vbox", f"{name}")
