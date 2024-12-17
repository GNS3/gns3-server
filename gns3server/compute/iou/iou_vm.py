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
IOU VM management (creates command line, processes, files etc.) in
order to run an IOU VM.
"""

import os
import socket
import re
import asyncio
import subprocess
import shutil
import configparser
import struct
import hashlib
import glob
import binascii
import functools

from .iou_error import IOUError
from ..adapters.ethernet_adapter import EthernetAdapter
from ..adapters.serial_adapter import SerialAdapter
from ..nios.nio_udp import NIOUDP
from ..base_node import BaseNode
from .utils.iou_import import nvram_import
from .utils.iou_export import nvram_export
from gns3server.ubridge.ubridge_error import UbridgeError
from gns3server.utils.file_watcher import FileWatcher
from gns3server.utils.asyncio.telnet_server import AsyncioTelnetServer
from gns3server.utils.asyncio import locking
import gns3server.utils.asyncio
import gns3server.utils.images

import logging
import sys
log = logging.getLogger(__name__)


class IOUVM(BaseNode):
    module_name = 'iou'

    """
    IOU VM implementation.

    :param name: IOU VM name
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Manager instance
    :param console: TCP console port
    :param console_type: console type
    """

    def __init__(self, name, node_id, project, manager, application_id=None, path=None, console=None, console_type="telnet"):

        super().__init__(name, node_id, project, manager, console=console, console_type=console_type)

        log.info('IOU "{name}" [{id}]: assigned with application ID {application_id}'.format(name=self._name,
                                                                                             id=self._id,
                                                                                             application_id=application_id))

        self._iou_process = None
        self._telnet_server = None
        self._iou_stdout_file = ""
        self._started = False
        self._nvram_watcher = None
        self._path = self.manager.get_abs_image_path(path, project.path)
        self._license_check = True

        # IOU settings
        self._ethernet_adapters = []
        self._serial_adapters = []
        self.ethernet_adapters = 2  # one adapter = 4 interfaces
        self.serial_adapters = 2  # one adapter = 4 interfaces
        self._use_default_iou_values = True  # for RAM & NVRAM values
        self._nvram = 128  # Kilobytes
        self._startup_config = ""
        self._private_config = ""
        self._ram = 256  # Megabytes
        self._application_id = application_id
        self._l1_keepalives = False  # used to overcome the always-up Ethernet interfaces (not supported by all IOSes).

    def _config(self):
        return self._manager.config.get_section_config("IOU")

    def _nvram_changed(self, path):
        """
        Called when the NVRAM file has changed
        """
        log.debug("NVRAM changed: {}".format(path))
        self.save_configs()
        self.updated()

    async def close(self):
        """
        Closes this IOU VM.
        """

        if not (await super().close()):
            return False

        adapters = self._ethernet_adapters + self._serial_adapters
        for adapter in adapters:
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(nio.lport, self._project)

        await self.stop()

    @property
    def path(self):
        """
        Path of the IOU executable.

        :returns: path to the IOU image executable
        """

        return self._path

    @path.setter
    def path(self, path):
        """
        Path of the IOU executable.

        :param path: path to the IOU image executable
        """

        self._path = self.manager.get_abs_image_path(path, self.project.path)
        log.info('IOU "{name}" [{id}]: IOU image updated to "{path}"'.format(name=self._name, id=self._id, path=self._path))

    @property
    def use_default_iou_values(self):
        """
        Returns if this device uses the default IOU image values.

        :returns: boolean
        """

        return self._use_default_iou_values

    @use_default_iou_values.setter
    def use_default_iou_values(self, state):
        """
        Sets if this device uses the default IOU image values.

        :param state: boolean
        """

        self._use_default_iou_values = state
        if state:
            log.info('IOU "{name}" [{id}]: uses the default IOU image values'.format(name=self._name, id=self._id))
        else:
            log.info('IOU "{name}" [{id}]: does not use the default IOU image values'.format(name=self._name, id=self._id))

    async def update_default_iou_values(self):
        """
        Finds the default RAM and NVRAM values for the IOU image.
        """

        try:
            output = await gns3server.utils.asyncio.subprocess_check_output(self._path, "-h", cwd=self.working_dir, stderr=True)
            match = re.search(r"-n <n>\s+Size of nvram in Kb \(default ([0-9]+)KB\)", output)
            if match:
                self.nvram = int(match.group(1))
            match = re.search(r"-m <n>\s+Megabytes of router memory \(default ([0-9]+)MB\)", output)
            if match:
                self.ram = int(match.group(1))
        except (ValueError, OSError, subprocess.SubprocessError) as e:
            log.warning("could not find default RAM and NVRAM values for {}: {}".format(os.path.basename(self._path), e))

    async def create(self):

        await self.update_default_iou_values()

    def _check_requirements(self):
        """
        Checks the IOU image.
        """

        if not self._path:
            raise IOUError("IOU image is not configured")
        if not os.path.isfile(self._path) or not os.path.exists(self._path):
            if os.path.islink(self._path):
                raise IOUError("IOU image '{}' linked to '{}' is not accessible".format(self._path, os.path.realpath(self._path)))
            else:
                raise IOUError("IOU image '{}' is not accessible".format(self._path))

        try:
            with open(self._path, "rb") as f:
                # read the first 7 bytes of the file.
                elf_header_start = f.read(7)
        except OSError as e:
            raise IOUError("Cannot read ELF header for IOU image '{}': {}".format(self._path, e))

        # IOU images must start with the ELF magic number, be 32-bit or 64-bit, little endian
        # and have an ELF version of 1 normal IOS image are big endian!
        if elf_header_start != b'\x7fELF\x01\x01\x01' and elf_header_start != b'\x7fELF\x02\x01\x01':
            raise IOUError("'{}' is not a valid IOU image".format(self._path))

        if not os.access(self._path, os.X_OK):
            raise IOUError("IOU image '{}' is not executable".format(self._path))

    def __json__(self):

        iou_vm_info = {"name": self.name,
                       "usage": self.usage,
                       "node_id": self.id,
                       "node_directory": self.working_path,
                       "console": self._console,
                       "console_type": self._console_type,
                       "status": self.status,
                       "project_id": self.project.id,
                       "path": self.path,
                       "md5sum": gns3server.utils.images.md5sum(self.path),
                       "ethernet_adapters": len(self._ethernet_adapters),
                       "serial_adapters": len(self._serial_adapters),
                       "ram": self._ram,
                       "nvram": self._nvram,
                       "l1_keepalives": self._l1_keepalives,
                       "use_default_iou_values": self._use_default_iou_values,
                       "command_line": self.command_line,
                       "application_id": self.application_id}

        iou_vm_info["path"] = self.manager.get_relative_image_path(self.path, self.project.path)
        return iou_vm_info

    @property
    def iourc_path(self):
        """
        Returns the IOURC file path.

        :returns: path to IOURC
        """

        iourc_path = self._config().get("iourc_path")
        if not iourc_path:
            # look for the iourc file in the temporary  dir.
            path = os.path.join(self.temporary_directory, "iourc")
            if os.path.exists(path):
                return path
            # look for the iourc file in the user home dir.
            path = os.path.join(os.path.expanduser("~/"), ".iourc")
            if os.path.exists(path):
                return path
            # look for the iourc file in the current working dir.
            path = os.path.join(self.working_dir, "iourc")
            if os.path.exists(path):
                return path
        return iourc_path

    @property
    def ram(self):
        """
        Returns the amount of RAM allocated to this IOU VM.

        :returns: amount of RAM in MBytes (integer)
        """

        return self._ram

    @ram.setter
    def ram(self, ram):
        """
        Sets amount of RAM allocated to this IOU instance.

        :param ram: amount of RAM in MBytes (integer)
        """

        if self._ram == ram:
            return

        log.info('IOU "{name}" [{id}]: RAM updated from {old_ram}MB to {new_ram}MB'.format(name=self._name,
                                                                                           id=self._id,
                                                                                           old_ram=self._ram,
                                                                                           new_ram=ram))

        self._ram = ram

    @property
    def nvram(self):
        """
        Returns the mount of NVRAM allocated to this IOU instance.

        :returns: amount of NVRAM in KBytes (integer)
        """

        return self._nvram

    @nvram.setter
    def nvram(self, nvram):
        """
        Sets amount of NVRAM allocated to this IOU instance.

        :param nvram: amount of NVRAM in KBytes (integer)
        """

        if self._nvram == nvram:
            return

        log.info('IOU "{name}" [{id}]: NVRAM updated from {old_nvram}KB to {new_nvram}KB'.format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 old_nvram=self._nvram,
                                                                                                 new_nvram=nvram))
        self._nvram = nvram

    @BaseNode.name.setter
    def name(self, new_name):
        """
        Sets the name of this IOU VM.

        :param new_name: name
        """

        if self.startup_config_file:
            content = self.startup_config_content
            content = re.sub(r"hostname .+$", "hostname " + new_name, content, flags=re.MULTILINE)
            self.startup_config_content = content

        super(IOUVM, IOUVM).name.__set__(self, new_name)

    @property
    def iourc_content(self):

        try:
            with open(os.path.join(self.temporary_directory, "iourc"), "rb") as f:
                return f.read().decode("utf-8")
        except OSError:
            return None

    @iourc_content.setter
    def iourc_content(self, value):

        if value:
            # If we don't save the value in the ~/ the licence is lost at project
            # reload
            path = os.path.join(os.path.expanduser("~/"), ".iourc")
            try:
                with open(path, "wb") as f:
                    f.write(value.encode("utf-8"))
            except OSError as e:
                raise IOUError("Could not write the iourc file {}: {}".format(path, e))

            path = os.path.join(self.temporary_directory, "iourc")
            try:
                with open(path, "wb") as f:
                    f.write(value.encode("utf-8"))
            except OSError as e:
                raise IOUError("Could not write the iourc file {}: {}".format(path, e))

    @property
    def license_check(self):

        return self._license_check

    @license_check.setter
    def license_check(self, value):

        self._license_check = value

    async def _library_check(self):
        """
        Checks for missing shared library dependencies in the IOU image.
        """

        try:
            output = await gns3server.utils.asyncio.subprocess_check_output("ldd", self._path)
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("Could not determine the shared library dependencies for {}: {}".format(self._path, e))
            return

        p = re.compile(r"([\.\w]+)\s=>\s+not found")
        missing_libs = p.findall(output)
        if missing_libs:
            raise IOUError("The following shared library dependencies cannot be found for IOU image {}: {}".format(self._path,
                                                                                                                   ", ".join(missing_libs)))

    def _is_iou_license_check_enabled(self):
        """
        Returns if IOU license check is enabled.

        :return: boolean
        """

        # license check is sent by the controller
        if self.license_check is False:
            return False

        try:
            # we allow license check to be disabled server wide
            server_wide_license_check = self._config().getboolean("license_check", True)
        except ValueError:
            raise IOUError("Invalid licence check setting")

        if server_wide_license_check is False:
            log.warning("License check is explicitly disabled on this server")
            return False

        return True

    async def _check_iou_license(self):
        """
        Checks for a valid IOU key in the iourc file (paranoid mode).
        """

        config = configparser.ConfigParser()
        try:
            log.info("Checking IOU license in '{}'".format(self.iourc_path))
            with open(self.iourc_path, encoding="utf-8") as f:
                config.read_file(f)
        except OSError as e:
            raise IOUError("Could not open iourc file {}: {}".format(self.iourc_path, e))
        except configparser.Error as e:
            raise IOUError("Could not parse iourc file {}: {}".format(self.iourc_path, e))
        except UnicodeDecodeError as e:
            raise IOUError("Non ascii characters in iourc file {}, please remove them: {}".format(self.iourc_path, e))
        if "license" not in config:
            raise IOUError("License section not found in iourc file {}".format(self.iourc_path))
        hostname = socket.gethostname()
        if len(hostname) > 15:
            log.warning("Older IOU images may not boot because hostname '{}' length is above 15 characters".format(hostname))
        if hostname not in config["license"]:
            raise IOUError("Hostname \"{}\" not found in iourc file {}".format(hostname, self.iourc_path))
        user_ioukey = config["license"][hostname]
        if user_ioukey[-1:] != ';':
            raise IOUError("IOU key not ending with ; in iourc file {}".format(self.iourc_path))
        if len(user_ioukey) != 17:
            raise IOUError("IOU key length is not 16 characters in iourc file {}".format(self.iourc_path))
        user_ioukey = user_ioukey[:16]

        # We can't test this because it's mean distributing a valid licence key
        # in tests or generating one
        if not hasattr(sys, "_called_from_test"):
            try:
                hostid = (await gns3server.utils.asyncio.subprocess_check_output("hostid")).strip()
            except FileNotFoundError as e:
                raise IOUError("Could not find hostid: {}".format(e))
            except (OSError, subprocess.SubprocessError) as e:
                raise IOUError("Could not execute hostid: {}".format(e))

            try:
                ioukey = int(hostid, 16)
            except ValueError:
                raise IOUError("Invalid hostid detected: {}".format(hostid))
            for x in hostname:
                ioukey += ord(x)
            pad1 = b'\x4B\x58\x21\x81\x56\x7B\x0D\xF3\x21\x43\x9B\x7E\xAC\x1D\xE6\x8A'
            pad2 = b'\x80' + 39 * b'\0'
            ioukey = hashlib.md5(pad1 + pad2 + struct.pack('!I', ioukey) + pad1).hexdigest()[:16]
            if ioukey != user_ioukey:
                raise IOUError("Invalid IOU license key {} detected in iourc file {} for host {}".format(user_ioukey,
                                                                                                         self.iourc_path,
                                                                                                         hostname))

    def _nvram_file(self):
        """
        Path to the nvram file
        """
        return os.path.join(self.working_dir, "nvram_{:05d}".format(self.application_id))

    def _push_configs_to_nvram(self):
        """
        Push the startup-config and private-config content to the NVRAM.
        """

        startup_config_content = self.startup_config_content
        if startup_config_content:
            nvram_file = self._nvram_file()
            try:
                if not os.path.exists(nvram_file):
                    open(nvram_file, "a").close()
                    nvram_content = None
                else:
                    with open(nvram_file, "rb") as file:
                        nvram_content = file.read()
            except OSError as e:
                raise IOUError("Cannot read nvram file {}: {}".format(nvram_file, e))

            startup_config_content = startup_config_content.encode("utf-8")
            private_config_content = self.private_config_content
            if private_config_content is not None:
                private_config_content = private_config_content.encode("utf-8")
            try:
                nvram_content = nvram_import(nvram_content, startup_config_content, private_config_content, self.nvram)
            except ValueError as e:
                raise IOUError("Cannot push configs to nvram {}: {}".format(nvram_file, e))
            try:
                with open(nvram_file, "wb") as file:
                    file.write(nvram_content)
            except OSError as e:
                raise IOUError("Cannot write nvram file {}: {}".format(nvram_file, e))

    async def start(self):
        """
        Starts the IOU process.
        """

        self._check_requirements()
        if not self.is_running():

            await self._library_check()

            try:
                self._rename_nvram_file()
            except OSError as e:
                raise IOUError("Could not rename nvram files: {}".format(e))

            iourc_path = None
            if self._is_iou_license_check_enabled():
                iourc_path = self.iourc_path
                if not iourc_path:
                    raise IOUError("Could not find an iourc file (IOU license), please configure an IOU license")
                if not os.path.isfile(iourc_path):
                    raise IOUError("The iourc path '{}' is not a regular file".format(iourc_path))
                await self._check_iou_license()

            await self._start_ubridge()
            self._create_netmap_config()
            if self.use_default_iou_values:
                # make sure we have the default nvram amount to correctly push the configs
                await self.update_default_iou_values()
            self._push_configs_to_nvram()

            # check if there is enough RAM to run
            self.check_available_ram(self.ram)

            self._nvram_watcher = FileWatcher(self._nvram_file(), self._nvram_changed, delay=2)

            # created an environment variable pointing to the iourc file.
            env = os.environ.copy()
            if "IOURC" not in os.environ and iourc_path:
                env["IOURC"] = iourc_path

            # create a symbolic link to the image to avoid IOU error "failed code signing checks"
            # on newer images, see https://github.com/GNS3/gns3-server/issues/1484
            try:
                iou_image_path = os.path.basename(self.path)
                if len(iou_image_path) > 63:
                    # IOU file basename length must be <= 63 chars
                    iou_file_name, iou_file_ext = os.path.splitext(iou_image_path)
                    iou_image_path = iou_file_name[:63 - len(iou_file_ext)] + iou_file_ext
                symlink = os.path.join(self.working_dir, iou_image_path)
                if os.path.islink(symlink):
                    os.unlink(symlink)
                os.symlink(self.path, symlink)
            except OSError as e:
                raise IOUError("Could not create symbolic link: {}".format(e))

            command = await self._build_command()
            try:
                log.info("Starting IOU: {}".format(command))
                self.command_line = ' '.join(command)
                self._iou_process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=self.working_dir,
                    env=env)
                log.info("IOU instance {} started PID={}".format(self._id, self._iou_process.pid))
                self._started = True
                self.status = "started"
                callback = functools.partial(self._termination_callback, "IOU")
                gns3server.utils.asyncio.monitor_process(self._iou_process, callback)
            except FileNotFoundError as e:
                raise IOUError("Could not start IOU: {}: 32-bit binary support is probably not installed".format(e))
            except (OSError, subprocess.SubprocessError) as e:
                iou_stdout = self.read_iou_stdout()
                log.error("Could not start IOU {}: {}\n{}".format(self._path, e, iou_stdout))
                raise IOUError("Could not start IOU {}: {}\n{}".format(self._path, e, iou_stdout))

            await self.start_console()

            # configure networking support
            await self._networking()

    async def start_console(self):
        """
        Start the Telnet server to provide console access.
        """

        if self.console and self.console_type == "telnet":
            server = AsyncioTelnetServer(reader=self._iou_process.stdout, writer=self._iou_process.stdin, binary=True,
                                         echo=True)
            try:
                self._telnet_server = await asyncio.start_server(server.run, self._manager.port_manager.console_host,
                                                                 self.console)
            except OSError as e:
                await self.stop()
                raise IOUError(
                    "Could not start Telnet server on socket {}:{}: {}".format(self._manager.port_manager.console_host,
                                                                               self.console, e))

    async def reset_console(self):
        """
        Reset the console.
        """

        if self._telnet_server:
            self._telnet_server.close()
            await self._telnet_server.wait_closed()
            self._telnet_server = None
        await self.start_console()

    @locking
    async def _networking(self):
        """
        Configures the IOL bridge in uBridge.
        """

        bridge_name = "IOL-BRIDGE-{}".format(self.application_id + 512)
        try:
            # delete any previous bridge if it exists
            await self._ubridge_send("iol_bridge delete {name}".format(name=bridge_name))
        except UbridgeError:
            pass
        await self._ubridge_send("iol_bridge create {name} {bridge_id}".format(name=bridge_name, bridge_id=self.application_id + 512))

        bay_id = 0
        for adapter in self._adapters:
            unit_id = 0
            for unit in adapter.ports.keys():
                nio = adapter.get_nio(unit)
                if nio and isinstance(nio, NIOUDP):
                    await self._ubridge_send("iol_bridge add_nio_udp {name} {iol_id} {bay} {unit} {lport} {rhost} {rport}".format(name=bridge_name,
                                                                                                                                       iol_id=self.application_id,
                                                                                                                                       bay=bay_id,
                                                                                                                                       unit=unit_id,
                                                                                                                                       lport=nio.lport,
                                                                                                                                       rhost=nio.rhost,
                                                                                                                                       rport=nio.rport))
                    if nio.capturing:
                        await self._ubridge_send('iol_bridge start_capture {name} "{output_file}" {data_link_type}'.format(name=bridge_name,
                                                                                                                                output_file=nio.pcap_output_file,
                                                                                                                                data_link_type=re.sub(r"^DLT_", "", nio.pcap_data_link_type)))

                    await self._ubridge_apply_filters(bay_id, unit_id, nio.filters)
                unit_id += 1
            bay_id += 1

        await self._ubridge_send("iol_bridge start {name}".format(name=bridge_name))

    def _termination_callback(self, process_name, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        self._terminate_process_iou()
        if returncode != 0:
            if returncode == -11:
                message = 'IOU VM "{}" process has stopped with return code: {} (segfault). This could be an issue with the IOU image, using a different image may fix this.\n{}'.format(self.name,
                                                                                                                                                                                         returncode,
                                                                                                                                                                                         self.read_iou_stdout())
            else:
                message = 'IOU VM "{}" process has stopped with return code: {}\n{}'.format(self.name, returncode, self.read_iou_stdout())
            log.warning(message)
            self.project.emit("log.error", {"message": message})
        if self._telnet_server:
            self._telnet_server.close()
            self._telnet_server = None

    def _rename_nvram_file(self):
        """
        Before starting the VM, rename the nvram and vlan.dat files with the correct IOU application identifier.
        """

        destination = self._nvram_file()
        for file_path in glob.glob(os.path.join(glob.escape(self.working_dir), "nvram_*")):
            shutil.move(file_path, destination)
        destination = os.path.join(self.working_dir, "vlan.dat-{:05d}".format(self.application_id))
        for file_path in glob.glob(os.path.join(glob.escape(self.working_dir), "vlan.dat-*")):
            shutil.move(file_path, destination)

    async def stop(self):
        """
        Stops the IOU process.
        """

        await self._stop_ubridge()
        if self._nvram_watcher:
            self._nvram_watcher.close()
            self._nvram_watcher = None

        if self._telnet_server:
            self._telnet_server.close()
            self._telnet_server = None

        if self.is_running():
            self._terminate_process_iou()
            if self._iou_process.returncode is None:
                try:
                    await gns3server.utils.asyncio.wait_for_process_termination(self._iou_process, timeout=3)
                except asyncio.TimeoutError:
                    if self._iou_process.returncode is None:
                        log.warning("IOU process {} is still running... killing it".format(self._iou_process.pid))
                        try:
                            self._iou_process.kill()
                        except ProcessLookupError:
                            pass
            self._iou_process = None

        try:
            symlink = os.path.join(self.working_dir, os.path.basename(self.path))
            if os.path.islink(symlink):
                os.unlink(symlink)
        except OSError as e:
            log.warning("Could not delete symbolic link: {}".format(e))

        self._started = False
        self.save_configs()

    def _terminate_process_iou(self):
        """
        Terminate the IOU process if running
        """

        if self._iou_process:
            log.info('Stopping IOU process for IOU VM "{}" PID={}'.format(self.name, self._iou_process.pid))
            try:
                self._iou_process.terminate()
            # Sometime the process can already be dead when we garbage collect
            except ProcessLookupError:
                pass
        self._started = False
        self.status = "stopped"

    async def reload(self):
        """
        Reloads the IOU process (stop & start).
        """

        await self.stop()
        await self.start()

    def is_running(self):
        """
        Checks if the IOU process is running

        :returns: True or False
        """

        if self._iou_process and self._iou_process.returncode is None:
            return True
        return False

    @BaseNode.console_type.setter
    def console_type(self, new_console_type):
        """
        Sets the console type for this IOU VM.

        :param new_console_type: console type (string)
        """

        if self.is_running() and self.console_type != new_console_type:
            raise IOUError('"{name}" must be stopped to change the console type to {new_console_type}'.format(name=self._name, new_console_type=new_console_type))

        super(IOUVM, IOUVM).console_type.__set__(self, new_console_type)

    def _create_netmap_config(self):
        """
        Creates the NETMAP file.
        """

        netmap_path = os.path.join(self.working_dir, "NETMAP")
        try:
            with open(netmap_path, "w", encoding="utf-8") as f:
                for bay in range(0, 16):
                    for unit in range(0, 4):
                        f.write("{ubridge_id}:{bay}/{unit}{iou_id:>5d}:{bay}/{unit}\n".format(ubridge_id=str(self.application_id + 512),
                                                                                              bay=bay,
                                                                                              unit=unit,
                                                                                              iou_id=self.application_id))
            log.info("IOU {name} [id={id}]: NETMAP file created".format(name=self._name,
                                                                        id=self._id))
        except OSError as e:
            raise IOUError("Could not create {}: {}".format(netmap_path, e))

    async def _build_command(self):
        """
        Command to start the IOU process.
        (to be passed to subprocess.Popen())

        IOU command line:
        Usage: <image> [options] <application id>
        <image>: unix-js-m | unix-is-m | unix-i-m | ...
        <application id>: instance identifier (0 < id <= 1024)
        Options:
        -e <n>        Number of Ethernet interfaces (default 2)
        -s <n>        Number of Serial interfaces (default 2)
        -n <n>        Size of nvram in Kb (default 64KB)
        -b <string>   IOS debug string
        -c <name>     Configuration file name
        -d            Generate debug information
        -t            Netio message trace
        -q            Suppress informational messages
        -h            Display this help
        -C            Turn off use of host clock
        -m <n>        Megabytes of router memory (default 256MB)
        -L            Disable local console, use remote console
        -l            Enable Layer 1 keepalive messages
        -u <n>        UDP port base for distributed networks
        -R            Ignore options from the IOURC file
        -U            Disable unix: file system location
        -W            Disable watchdog timer
        -N            Ignore the NETMAP file
        """

        command = [self._path]
        if len(self._ethernet_adapters) != 2:
            command.extend(["-e", str(len(self._ethernet_adapters))])
        if len(self._serial_adapters) != 2:
            command.extend(["-s", str(len(self._serial_adapters))])
        if not self.use_default_iou_values:
            command.extend(["-n", str(self._nvram)])
            command.extend(["-m", str(self._ram)])

        # do not let IOU create the NVRAM anymore
        #startup_config_file = self.startup_config_file
        # if startup_config_file:
        #    command.extend(["-c", os.path.basename(startup_config_file)])

        if self._l1_keepalives:
            await self._enable_l1_keepalives(command)
        command.extend([str(self.application_id)])
        return command

    def read_iou_stdout(self):
        """
        Reads the standard output of the IOU process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._iou_stdout_file:
            try:
                with open(self._iou_stdout_file, "rb") as file:
                    output = file.read().decode("utf-8", errors="replace")
            except OSError as e:
                log.warning("could not read {}: {}".format(self._iou_stdout_file, e))
        return output

    @property
    def adapters(self):
        return self._adapters

    @property
    def ethernet_adapters(self):
        """
        Returns the number of Ethernet adapters for this IOU VM.

        :returns: number of adapters
        """

        return len(self._ethernet_adapters)

    @ethernet_adapters.setter
    def ethernet_adapters(self, ethernet_adapters):
        """
        Sets the number of Ethernet adapters for this IOU VM.

        :param ethernet_adapters: number of adapters
        """

        self._ethernet_adapters.clear()
        for _ in range(0, ethernet_adapters):
            self._ethernet_adapters.append(EthernetAdapter(interfaces=4))

        log.info('IOU "{name}" [{id}]: number of Ethernet adapters changed to {adapters}'.format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 adapters=len(self._ethernet_adapters)))

        self._adapters = self._ethernet_adapters + self._serial_adapters

    @property
    def serial_adapters(self):
        """
        Returns the number of Serial adapters for this IOU VM.

        :returns: number of adapters
        """

        return len(self._serial_adapters)

    @serial_adapters.setter
    def serial_adapters(self, serial_adapters):
        """
        Sets the number of Serial adapters for this IOU VM.

        :param serial_adapters: number of adapters
        """

        self._serial_adapters.clear()
        for _ in range(0, serial_adapters):
            self._serial_adapters.append(SerialAdapter(interfaces=4))

        log.info('IOU "{name}" [{id}]: number of Serial adapters changed to {adapters}'.format(name=self._name,
                                                                                               id=self._id,
                                                                                               adapters=len(self._serial_adapters)))

        self._adapters = self._ethernet_adapters + self._serial_adapters

    async def adapter_add_nio_binding(self, adapter_number, port_number, nio):
        """
        Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param port_number: port number
        :param nio: NIO instance to add to the adapter/port
        """

        try:
            adapter = self._adapters[adapter_number]
        except IndexError:
            raise IOUError('Adapter {adapter_number} does not exist for IOU "{name}"'.format(name=self._name,
                                                                                             adapter_number=adapter_number))

        if not adapter.port_exists(port_number):
            raise IOUError("Port {port_number} does not exist on adapter {adapter}".format(adapter=adapter,
                                                                                           port_number=port_number))

        adapter.add_nio(port_number, nio)
        log.info('IOU "{name}" [{id}]: {nio} added to {adapter_number}/{port_number}'.format(name=self._name,
                                                                                             id=self._id,
                                                                                             nio=nio,
                                                                                             adapter_number=adapter_number,
                                                                                             port_number=port_number))

        if self.ubridge:
            bridge_name = "IOL-BRIDGE-{}".format(self.application_id + 512)
            await self._ubridge_send("iol_bridge add_nio_udp {name} {iol_id} {bay} {unit} {lport} {rhost} {rport}".format(name=bridge_name,
                                                                                                                               iol_id=self.application_id,
                                                                                                                               bay=adapter_number,
                                                                                                                               unit=port_number,
                                                                                                                               lport=nio.lport,
                                                                                                                               rhost=nio.rhost,
                                                                                                                               rport=nio.rport))
            await self._ubridge_apply_filters(adapter_number, port_number, nio.filters)

    async def adapter_update_nio_binding(self, adapter_number, port_number, nio):
        """
        Updates an adapter NIO binding.

        :param adapter_number: adapter number
        :param port_number: port number
        :param nio: NIO instance to add to the adapter
        """

        if self.ubridge:
            await self._ubridge_apply_filters(adapter_number, port_number, nio.filters)

    async def _ubridge_apply_filters(self, adapter_number, port_number, filters):
        """
        Apply filter like rate limiting

        :param adapter_number: adapter number
        :param port_number: port number
        :param filters: Array of filter dictionnary
        """
        bridge_name = "IOL-BRIDGE-{}".format(self.application_id + 512)
        location = '{bridge_name} {bay} {unit}'.format(
            bridge_name=bridge_name,
            bay=adapter_number,
            unit=port_number)
        await self._ubridge_send('iol_bridge reset_packet_filters ' + location)
        for filter in self._build_filter_list(filters):
            cmd = 'iol_bridge add_packet_filter {} {}'.format(
                location,
                filter)
            await self._ubridge_send(cmd)

    async def adapter_remove_nio_binding(self, adapter_number, port_number):
        """
        Removes an adapter NIO binding.

        :param adapter_number: adapter number
        :param port_number: port number

        :returns: NIO instance
        """

        try:
            adapter = self._adapters[adapter_number]
        except IndexError:
            raise IOUError('Adapter {adapter_number} does not exist on IOU "{name}"'.format(name=self._name,
                                                                                            adapter_number=adapter_number))

        if not adapter.port_exists(port_number):
            raise IOUError("Port {port_number} does not exist on adapter {adapter}".format(adapter=adapter,
                                                                                           port_number=port_number))

        nio = adapter.get_nio(port_number)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        adapter.remove_nio(port_number)
        log.info('IOU "{name}" [{id}]: {nio} removed from {adapter_number}/{port_number}'.format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 nio=nio,
                                                                                                 adapter_number=adapter_number,
                                                                                                 port_number=port_number))

        if self.ubridge:
            bridge_name = "IOL-BRIDGE-{}".format(self.application_id + 512)
            await self._ubridge_send("iol_bridge delete_nio_udp {name} {bay} {unit}".format(name=bridge_name,
                                                                                                 bay=adapter_number,
                                                                                                 unit=port_number))

        return nio

    def get_nio(self, adapter_number, port_number):
        """
        Gets an adapter NIO binding.

        :param adapter_number: adapter number
        :param port_number: port number

        :returns: NIO instance
        """

        try:
            adapter = self._adapters[adapter_number]
        except IndexError:
            raise IOUError('Adapter {adapter_number} does not exist on IOU "{name}"'.format(name=self._name,
                                                                                            adapter_number=adapter_number))

        if not adapter.port_exists(port_number):
            raise IOUError("Port {port_number} does not exist on adapter {adapter}".format(adapter=adapter,
                                                                                           port_number=port_number))

        nio = adapter.get_nio(port_number)

        if not nio:
            raise IOUError("NIO {port_number} does not exist on adapter {adapter}".format(adapter=adapter,
                                                                                          port_number=port_number))
        return nio

    @property
    def l1_keepalives(self):
        """
        Returns either layer 1 keepalive messages option is enabled or disabled.

        :returns: boolean
        """

        return self._l1_keepalives

    @l1_keepalives.setter
    def l1_keepalives(self, state):
        """
        Enables or disables layer 1 keepalive messages.

        :param state: boolean
        """

        self._l1_keepalives = state
        if state:
            log.info('IOU "{name}" [{id}]: has activated layer 1 keepalive messages'.format(name=self._name, id=self._id))
        else:
            log.info('IOU "{name}" [{id}]: has deactivated layer 1 keepalive messages'.format(name=self._name, id=self._id))

    async def _enable_l1_keepalives(self, command):
        """
        Enables L1 keepalive messages if supported.

        :param command: command line
        """

        env = os.environ.copy()
        if "IOURC" not in os.environ:
            env["IOURC"] = self.iourc_path
        try:
            output = await gns3server.utils.asyncio.subprocess_check_output(self._path, "-h", cwd=self.working_dir, env=env, stderr=True)
            if re.search(r"-l\s+Enable Layer 1 keepalive messages", output):
                command.extend(["-l"])
            else:
                raise IOUError("layer 1 keepalive messages are not supported by {}".format(os.path.basename(self._path)))
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("could not determine if layer 1 keepalive messages are supported by {}: {}".format(os.path.basename(self._path), e))

    @property
    def startup_config_content(self):
        """
        Returns the content of the current startup-config file.
        """

        config_file = self.startup_config_file
        if config_file is None:
            return None

        try:
            with open(config_file, "rb") as f:
                return f.read().decode("utf-8", errors="replace")
        except OSError as e:
            raise IOUError("Can't read startup-config file '{}': {}".format(config_file, e))

    @startup_config_content.setter
    def startup_config_content(self, startup_config):
        """
        Update the startup config

        :param startup_config: content of the startup configuration file
        """

        try:
            startup_config_path = os.path.join(self.working_dir, "startup-config.cfg")

            if startup_config is None:
                startup_config = ''

            # We disallow erasing the startup config file
            if len(startup_config) == 0 and os.path.exists(startup_config_path):
                return

            with open(startup_config_path, 'w+', encoding='utf-8') as f:
                if len(startup_config) == 0:
                    f.write('')
                else:
                    startup_config = startup_config.replace("%h", self._name)
                    f.write(startup_config)

            vlan_file = os.path.join(self.working_dir, "vlan.dat-{:05d}".format(self.application_id))
            if os.path.exists(vlan_file):
                try:
                    os.remove(vlan_file)
                except OSError as e:
                    log.error("Could not delete VLAN file '{}': {}".format(vlan_file, e))

        except OSError as e:
            raise IOUError("Can't write startup-config file '{}': {}".format(startup_config_path, e))

    @property
    def private_config_content(self):
        """
        Returns the content of the current private-config file.
        """

        config_file = self.private_config_file
        if config_file is None:
            return None

        try:
            with open(config_file, "rb") as f:
                return f.read().decode("utf-8", errors="replace")
        except OSError as e:
            raise IOUError("Can't read private-config file '{}': {}".format(config_file, e))

    @private_config_content.setter
    def private_config_content(self, private_config):
        """
        Update the private config

        :param private_config: content of the private configuration file
        """

        try:
            private_config_path = os.path.join(self.working_dir, "private-config.cfg")

            if private_config is None:
                private_config = ''

            # We disallow erasing the private config file
            if len(private_config) == 0 and os.path.exists(private_config_path):
                return

            with open(private_config_path, 'w+', encoding='utf-8') as f:
                if len(private_config) == 0:
                    f.write('')
                else:
                    private_config = private_config.replace("%h", self._name)
                    f.write(private_config)
        except OSError as e:
            raise IOUError("Can't write private-config file '{}': {}".format(private_config_path, e))

    @property
    def startup_config_file(self):
        """
        Returns the startup-config file for this IOU VM.

        :returns: path to config file. None if the file doesn't exist
        """

        path = os.path.join(self.working_dir, 'startup-config.cfg')
        if os.path.exists(path):
            return path
        else:
            return None

    @property
    def private_config_file(self):
        """
        Returns the private-config file for this IOU VM.

        :returns: path to config file. None if the file doesn't exist
        """

        path = os.path.join(self.working_dir, 'private-config.cfg')
        if os.path.exists(path):
            return path
        else:
            return None

    @property
    def relative_startup_config_file(self):
        """
        Returns the startup-config file relative to the project directory.
        It's compatible with pre 1.3 projects.

        :returns: path to startup-config file. None if the file doesn't exist
        """

        path = os.path.join(self.working_dir, 'startup-config.cfg')
        if os.path.exists(path):
            return 'startup-config.cfg'
        else:
            return None

    @property
    def relative_private_config_file(self):
        """
        Returns the private-config file relative to the project directory.

        :returns: path to private-config file. None if the file doesn't exist
        """

        path = os.path.join(self.working_dir, 'private-config.cfg')
        if os.path.exists(path):
            return 'private-config.cfg'
        else:
            return None

    @property
    def application_id(self):
        """
        Returns application_id which unique identifier for IOU running script. Value is between 1 and 512.
        When it's not set returns value from the local manager.

        :returns: integer between 1 and 512
        """

        return self._application_id

    @application_id.setter
    def application_id(self, application_id):
        """
        Sets application_id for IOU.

        :param: integer between 1 and 512
        """
        self._application_id = application_id

    def extract_configs(self):
        """
        Gets the contents of the config files
        startup-config and private-config from NVRAM.

        :returns: tuple (startup-config, private-config)
        """

        nvram_file = os.path.join(self.working_dir, "nvram_{:05d}".format(self.application_id))
        if not os.path.exists(nvram_file):
            return None, None
        try:
            with open(nvram_file, "rb") as file:
                nvram_content = file.read()
        except OSError as e:
            log.warning("Cannot read nvram file {}: {}".format(nvram_file, e))
            return None, None

        try:
            startup_config_content, private_config_content = nvram_export(nvram_content)
        except ValueError as e:
            log.warning("Could not export configs from nvram file {}: {}".format(nvram_file, e))
            return None, None

        return startup_config_content, private_config_content

    def save_configs(self):
        """
        Saves the startup-config and private-config to files.
        """

        if self.startup_config_content or self.private_config_content:
            startup_config_content, private_config_content = self.extract_configs()
            if startup_config_content:
                config_path = os.path.join(self.working_dir, "startup-config.cfg")
                try:
                    config = startup_config_content.decode("utf-8", errors="replace")
                    with open(config_path, "wb") as f:
                        log.info("saving startup-config to {}".format(config_path))
                        f.write(config.encode("utf-8"))
                except (binascii.Error, OSError) as e:
                    raise IOUError("Could not save the startup configuration {}: {}".format(config_path, e))

            if private_config_content and private_config_content != b'\nend\n':
                config_path = os.path.join(self.working_dir, "private-config.cfg")
                try:
                    config = private_config_content.decode("utf-8", errors="replace")
                    with open(config_path, "wb") as f:
                        log.info("saving private-config to {}".format(config_path))
                        f.write(config.encode("utf-8"))
                except (binascii.Error, OSError) as e:
                    raise IOUError("Could not save the private configuration {}: {}".format(config_path, e))

    async def start_capture(self, adapter_number, port_number, output_file, data_link_type="DLT_EN10MB"):
        """
        Starts a packet capture.

        :param adapter_number: adapter number
        :param port_number: port number
        :param output_file: PCAP destination file for the capture
        :param data_link_type: PCAP data link type (DLT_*), default is DLT_EN10MB
        """

        nio = self.get_nio(adapter_number, port_number)
        if nio.capturing:
            raise IOUError("Packet capture is already activated on {adapter_number}/{port_number}".format(adapter_number=adapter_number,
                                                                                                          port_number=port_number))

        nio.start_packet_capture(output_file, data_link_type)
        log.info('IOU "{name}" [{id}]: starting packet capture on {adapter_number}/{port_number} to {output_file}'.format(name=self._name,
                                                                                                                          id=self._id,
                                                                                                                          adapter_number=adapter_number,
                                                                                                                          port_number=port_number,
                                                                                                                          output_file=output_file))

        if self.ubridge:
            bridge_name = "IOL-BRIDGE-{}".format(self.application_id + 512)
            await self._ubridge_send('iol_bridge start_capture {name} {bay} {unit} "{output_file}" {data_link_type}'.format(name=bridge_name,
                                                                                                                                 bay=adapter_number,
                                                                                                                                 unit=port_number,
                                                                                                                                 output_file=output_file,
                                                                                                                                 data_link_type=re.sub(r"^DLT_", "", data_link_type)))

    async def stop_capture(self, adapter_number, port_number):
        """
        Stops a packet capture.

        :param adapter_number: adapter number
        :param port_number: port number
        """

        nio = self.get_nio(adapter_number, port_number)
        if not nio.capturing:
            return
        nio.stop_packet_capture()
        log.info('IOU "{name}" [{id}]: stopping packet capture on {adapter_number}/{port_number}'.format(name=self._name,
                                                                                                         id=self._id,
                                                                                                         adapter_number=adapter_number,
                                                                                                         port_number=port_number))
        if self.ubridge:
            bridge_name = "IOL-BRIDGE-{}".format(self.application_id + 512)
            await self._ubridge_send('iol_bridge stop_capture {name} {bay} {unit}'.format(name=bridge_name,
                                                                                               bay=adapter_number,
                                                                                               unit=port_number))
