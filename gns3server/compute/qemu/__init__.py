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
import platform
import shutil
import shlex
import sys
import re
import subprocess

from ...utils.asyncio import subprocess_check_output
from ...utils.get_resource import get_resource
from ..base_manager import BaseManager
from ..error import NodeError, ImageMissingError
from .qemu_error import QemuError
from .qemu_vm import QemuVM
from .utils.guest_cid import get_next_guest_cid
from .utils.ziputils import unpack_zip

import logging

log = logging.getLogger(__name__)


class Qemu(BaseManager):

    _NODE_CLASS = QemuVM
    _NODE_TYPE = "qemu"

    def __init__(self):

        super().__init__()
        self._guest_cid_lock = asyncio.Lock()
        self.config_disk = "config.img"
        self._init_config_disk()

    async def create_node(self, *args, **kwargs):
        """
        Creates a new Qemu VM.

        :returns: QemuVM instance
        """

        node = await super().create_node(*args, **kwargs)

        # allocate a guest console ID (CID)
        if node.console_type != "none" and node.console:
            # by default, the guest CID is equal to the console port
            node.guest_cid = node.console
        else:
            # otherwise pick a guest CID if no console port is configured
            async with self._guest_cid_lock:
                # wait for a node to be completely created before adding a new one
                # this is important otherwise we allocate the same guest ID
                # when creating multiple Qemu VMs at the same time
                node.guest_cid = get_next_guest_cid(self.nodes)
        return node

    @staticmethod
    async def get_kvm_archs():
        """
        Gets a list of architectures for which KVM is available on this server.

        :returns: List of architectures for which KVM is available on this server.
        """

        kvm = []

        if not os.path.exists("/dev/kvm"):
            return kvm

        arch = platform.machine()
        if arch == "x86_64":
            kvm.append("x86_64")
            kvm.append("i386")
        elif arch == "i386":
            kvm.append("i386")
        else:
            kvm.append(platform.machine())
        return kvm

    @staticmethod
    def paths_list():
        """
        Gets a folder list of possibly available QEMU binaries on the host.

        :returns: List of folders where Qemu binaries MAY reside.
        """

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
        if sys.platform.startswith("darwin") and hasattr(sys, "frozen"):
            # add specific locations on Mac OS X regardless of what's in $PATH
            paths.update(["/usr/bin", "/usr/local/bin", "/opt/local/bin"])
            try:
                exec_dir = os.path.dirname(os.path.abspath(sys.executable))
                paths.add(os.path.abspath(os.path.join(exec_dir, "qemu/bin")))
            # If the user run the server by hand from outside
            except FileNotFoundError:
                paths.add("/Applications/GNS3.app/Contents/MacOS/qemu/bin")
        return paths

    @staticmethod
    async def binary_list(archs=None):
        """
        Gets QEMU binaries list available on the host.

        :returns: Array of dictionary {"path": Qemu binary path, "version": version of Qemu}
        """

        qemus = []
        for path in Qemu.paths_list():
            log.debug(f"Searching for Qemu binaries in '{path}'")
            try:
                for f in os.listdir(path):
                    if (
                        (f.startswith("qemu-system") or f.startswith("qemu-kvm") or f == "qemu" or f == "qemu.exe")
                        and os.access(os.path.join(path, f), os.X_OK)
                        and os.path.isfile(os.path.join(path, f))
                    ):
                        if archs is not None:
                            for arch in archs:
                                if f.endswith(arch) or f.endswith(f"{arch}.exe") or f.endswith(f"{arch}w.exe"):
                                    qemu_path = os.path.join(path, f)
                                    try:
                                        version = await Qemu.get_qemu_version(qemu_path)
                                    except QemuError as e:
                                        log.warning(str(e))
                                        continue
                                    qemus.append({"path": qemu_path, "version": version})
                        else:
                            qemu_path = os.path.join(path, f)
                            try:
                                version = await Qemu.get_qemu_version(qemu_path)
                            except QemuError as e:
                                log.warning(str(e))
                                continue
                            qemus.append({"path": qemu_path, "version": version})
            except OSError:
                continue

        return qemus

    @staticmethod
    async def create_disk_image(disk_image_path, options):
        """
        Create a Qemu disk (used by the controller to create empty disk images)

        :param disk_image_path: disk image path
        :param options: disk creation options
        """

        qemu_img_path = shutil.which("qemu-img")
        if not qemu_img_path:
            raise QemuError(f"Could not find qemu-img binary")

        try:
            if os.path.exists(disk_image_path):
                raise QemuError(f"Could not create disk image '{disk_image_path}', file already exists")
        except UnicodeEncodeError:
            raise QemuError(
                f"Could not create disk image '{disk_image_path}', "
                "Disk image name contains characters not supported by the filesystem"
            )

        img_format = options.pop("format")
        img_size = options.pop("size")
        command = [qemu_img_path, "create", "-f", img_format]
        for option in sorted(options.keys()):
            command.extend(["-o", f"{option}={options[option]}"])
        command.append(disk_image_path)
        command.append(f"{img_size}M")
        command_string = " ".join(shlex.quote(s) for s in command)
        output = ""
        try:
            log.info(f"Executing qemu-img with: {command_string}")
            output = await subprocess_check_output(*command, stderr=True)
            log.info(f"Qemu disk image'{disk_image_path}' created")
        except (OSError, subprocess.SubprocessError) as e:
            raise QemuError(f"Could not create '{disk_image_path}' disk image: {e}\n{output}")

    @staticmethod
    async def get_qemu_version(qemu_path):
        """
        Gets the Qemu version.

        :param qemu_path: path to Qemu executable.
        """

        try:
            output = await subprocess_check_output(qemu_path, "-version", "-nographic")
            match = re.search(r"version\s+([0-9a-z\-\.]+)", output)
            if match:
                version = match.group(1)
                return version
            else:
                raise QemuError(f"Could not determine the Qemu version for {qemu_path}")
        except (OSError, subprocess.SubprocessError) as e:
            raise QemuError(f"Error while looking for the Qemu version: {e}")

    @staticmethod
    async def get_swtpm_version(swtpm_path):
        """
        Gets the swtpm version.

        :param swtpm_path: path to swtpm executable.
        """

        try:
            output = await subprocess_check_output(swtpm_path, "--version")
            match = re.search(r"version\s+([\d.]+)", output)
            if match:
                version = match.group(1)
                return version
            else:
                raise QemuError("Could not determine the swtpm version for '{}'".format(swtpm_path))
        except (OSError, subprocess.SubprocessError) as e:
            raise QemuError("Error while looking for the swtpm version: {}".format(e))

    @staticmethod
    def get_haxm_windows_version():
        """
        Gets the HAXM version number (Windows).

        :returns: HAXM version number. Returns None if HAXM is not installed.
        """

        assert(sys.platform.startswith("win"))
        import winreg

        hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UserData\S-1-5-18\Products")
        version = None
        for index in range(winreg.QueryInfoKey(hkey)[0]):
            product_id = winreg.EnumKey(hkey, index)
            try:
                product_key = winreg.OpenKey(hkey, r"{}\InstallProperties".format(product_id))
                try:
                    if winreg.QueryValueEx(product_key, "DisplayName")[0].endswith("Hardware Accelerated Execution Manager"):
                        version = winreg.QueryValueEx(product_key, "DisplayVersion")[0]
                        break
                finally:
                    winreg.CloseKey(product_key)
            except OSError:
                continue
        winreg.CloseKey(hkey)
        return version

    @staticmethod
    def get_legacy_vm_workdir(legacy_vm_id, name):
        """
        Returns the name of the legacy working directory name for a node.

        :param legacy_vm_id: legacy VM identifier (integer)
        :param: node name (not used)

        :returns: working directory name
        """

        return os.path.join("qemu", f"vm-{legacy_vm_id}")

    def _init_config_disk(self):
        """
        Initialize the default config disk
        """

        try:
            self.get_abs_image_path(self.config_disk)
        except (NodeError, ImageMissingError):
            config_disk_zip = get_resource(f"compute/qemu/resources/{self.config_disk}.zip")
            if config_disk_zip and os.path.exists(config_disk_zip):
                directory = self.get_images_directory()
                try:
                    unpack_zip(config_disk_zip, directory)
                except OSError as e:
                    log.warning(f"Config disk creation: {e}")
            else:
                log.warning(f"Config disk: image '{self.config_disk}' missing")
