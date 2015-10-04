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
Qemu server module.
"""

import asyncio
import os
import sys
import re
import subprocess

from ...utils.asyncio import subprocess_check_output
from ..base_manager import BaseManager
from .qemu_error import QemuError
from .qemu_vm import QemuVM

import logging
log = logging.getLogger(__name__)


class Qemu(BaseManager):

    _VM_CLASS = QemuVM

    @staticmethod
    def binary_list():
        """
        Gets QEMU binaries list available on the host.

        :returns: Array of dictionary {"path": Qemu binary path, "version": version of Qemu}
        """

        qemus = []
        paths = set()
        try:
            paths.add(os.getcwd())
        except FileNotFoundError:
            log.warning("The current working directory doesn't exist")
        if "PATH" in os.environ:
            paths.update(os.environ["PATH"].split(os.pathsep))
        else:
            log.warning("The PATH environment variable doesn't exist")
        # look for Qemu binaries in the current working directory and $PATH
        if sys.platform.startswith("win"):
            # add specific Windows paths
            if hasattr(sys, "frozen"):
                # add any qemu dir in the same location as gns3server.exe to the list of paths
                exec_dir = os.path.dirname(os.path.abspath(sys.executable))
                for f in os.listdir(exec_dir):
                    if f.lower().startswith("qemu"):
                        paths.add(os.path.join(exec_dir, f))

            if "PROGRAMFILES(X86)" in os.environ and os.path.exists(os.environ["PROGRAMFILES(X86)"]):
                paths.add(os.path.join(os.environ["PROGRAMFILES(X86)"], "qemu"))
            if "PROGRAMFILES" in os.environ and os.path.exists(os.environ["PROGRAMFILES"]):
                paths.add(os.path.join(os.environ["PROGRAMFILES"], "qemu"))
        elif sys.platform.startswith("darwin"):
            # add specific locations on Mac OS X regardless of what's in $PATH
            paths.update(["/usr/local/bin", "/opt/local/bin"])
            if hasattr(sys, "frozen"):
                try:
                    paths.add(os.path.abspath(os.path.join(os.getcwd(), "../../../qemu/bin/")))
                # If the user run the server by hand from outside
                except FileNotFoundError:
                    paths.add("/Applications/GNS3.app/Contents/Resources/qemu/bin")
        for path in paths:
            try:
                for f in os.listdir(path):
                    if (f.startswith("qemu-system") or f.startswith("qemu-kvm") or f == "qemu" or f == "qemu.exe") and \
                            os.access(os.path.join(path, f), os.X_OK) and \
                            os.path.isfile(os.path.join(path, f)):
                        qemu_path = os.path.join(path, f)
                        version = yield from Qemu.get_qemu_version(qemu_path)
                        qemus.append({"path": qemu_path, "version": version})
            except OSError:
                continue

        return qemus

    @staticmethod
    @asyncio.coroutine
    def get_qemu_version(qemu_path):
        """
        Gets the Qemu version.

        :param qemu_path: path to Qemu executable.
        """

        if sys.platform.startswith("win"):
            # Qemu on Windows doesn't return anything with parameter -version
            # look for a version number in version.txt file in the same directory instead
            version_file = os.path.join(os.path.dirname(qemu_path), "version.txt")
            if os.path.isfile(version_file):
                try:
                    with open(version_file, "rb") as file:
                        version = file.read().decode("utf-8").strip()
                        match = re.search("[0-9\.]+", version)
                        if match:
                            return version
                except (UnicodeDecodeError, OSError) as e:
                    log.warn("could not read {}: {}".format(version_file, e))
            return ""
        else:
            try:
                output = yield from subprocess_check_output(qemu_path, "-version")
                match = re.search("version\s+([0-9a-z\-\.]+)", output)
                if match:
                    version = match.group(1)
                    return version
                else:
                    raise QemuError("Could not determine the Qemu version for {}".format(qemu_path))
            except subprocess.SubprocessError as e:
                raise QemuError("Error while looking for the Qemu version: {}".format(e))

    @staticmethod
    def get_legacy_vm_workdir(legacy_vm_id, name):
        """
        Returns the name of the legacy working directory name for a VM.

        :param legacy_vm_id: legacy VM identifier (integer)
        :param: VM name (not used)

        :returns: working directory name
        """

        return os.path.join("qemu", "vm-{}".format(legacy_vm_id))

    def get_images_directory(self):
        """
        Return the full path of the images directory on disk
        """
        return os.path.join(os.path.expanduser(self.config.get_section_config("Server").get("images_path", "~/GNS3/images")), "QEMU")
