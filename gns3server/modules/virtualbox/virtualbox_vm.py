# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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
VirtualBox VM instance.
"""

import sys
import shlex
import re
import os
import subprocess
import tempfile
import json
import socket
import time

from .virtualbox_error import VirtualBoxError
from .adapters.ethernet_adapter import EthernetAdapter
from ..attic import find_unused_port
from .telnet_server import TelnetServer

if sys.platform.startswith('win'):
    import msvcrt
    import win32file

import logging
log = logging.getLogger(__name__)


class VirtualBoxVM(object):
    """
    VirtualBox VM implementation.

    :param vboxmanage_path: path to the VBoxManage tool
    :param name: name of this VirtualBox VM
    :param vmname: name of this VirtualBox VM in VirtualBox itself
    :param linked_clone: flag if a linked clone must be created
    :param working_dir: path to a working directory
    :param vbox_id: VirtalBox VM instance ID
    :param console: TCP console port
    :param console_host: IP address to bind for console connections
    :param console_start_port_range: TCP console port range start
    :param console_end_port_range: TCP console port range end
    """

    _instances = []
    _allocated_console_ports = []

    def __init__(self,
                 vboxmanage_path,
                 vbox_user,
                 name,
                 vmname,
                 linked_clone,
                 working_dir,
                 vbox_id=None,
                 console=None,
                 console_host="0.0.0.0",
                 console_start_port_range=4512,
                 console_end_port_range=5000):

        if not vbox_id:
            self._id = 0
            for identifier in range(1, 1024):
                if identifier not in self._instances:
                    self._id = identifier
                    self._instances.append(self._id)
                    break

            if self._id == 0:
                raise VirtualBoxError("Maximum number of VirtualBox VM instances reached")
        else:
            if vbox_id in self._instances:
                raise VirtualBoxError("VirtualBox identifier {} is already used by another VirtualBox VM instance".format(vbox_id))
            self._id = vbox_id
            self._instances.append(self._id)

        self._name = name
        self._linked_clone = linked_clone
        self._working_dir = None
        self._command = []
        self._vboxmanage_path = vboxmanage_path
        self._vbox_user = vbox_user
        self._started = False
        self._console_host = console_host
        self._console_start_port_range = console_start_port_range
        self._console_end_port_range = console_end_port_range

        self._telnet_server_thread = None
        self._serial_pipe = None

        # VirtualBox settings
        self._console = console
        self._ethernet_adapters = []
        self._headless = False
        self._enable_remote_console = True
        self._vmname = vmname
        self._adapter_start_index = 0
        self._adapter_type = "Intel PRO/1000 MT Desktop (82540EM)"

        working_dir_path = os.path.join(working_dir, "vbox")

        if vbox_id and not os.path.isdir(working_dir_path):
            raise VirtualBoxError("Working directory {} doesn't exist".format(working_dir_path))

        # create the device own working directory
        self.working_dir = working_dir_path

        if not self._console:
            # allocate a console port
            try:
                self._console = find_unused_port(self._console_start_port_range,
                                                 self._console_end_port_range,
                                                 self._console_host,
                                                 ignore_ports=self._allocated_console_ports)
            except Exception as e:
                raise VirtualBoxError(e)

        if self._console in self._allocated_console_ports:
            raise VirtualBoxError("Console port {} is already used by another VirtualBox VM".format(console))
        self._allocated_console_ports.append(self._console)

        self._system_properties = {}
        properties = self._execute("list", ["systemproperties"])
        for prop in properties:
            try:
                name, value = prop.split(':', 1)
            except ValueError:
                continue
            self._system_properties[name.strip()] = value.strip()

        if linked_clone:
            if vbox_id and os.path.isdir(os.path.join(self.working_dir, self._vmname)):
                vbox_file = os.path.join(self.working_dir, self._vmname, self._vmname + ".vbox")
                self._execute("registervm", [vbox_file])
                self._reattach_hdds()
            else:
                self._create_linked_clone()

        self._maximum_adapters = 8
        self.adapters = 2  # creates 2 adapters by default

        log.info("VirtualBox VM {name} [id={id}] has been created".format(name=self._name,
                                                                          id=self._id))

    def defaults(self):
        """
        Returns all the default attribute values for this VirtualBox VM.

        :returns: default values (dictionary)
        """

        vbox_defaults = {"name": self._name,
                         "vmname": self._vmname,
                         "adapters": self.adapters,
                         "adapter_start_index": self._adapter_start_index,
                         "adapter_type": "Intel PRO/1000 MT Desktop (82540EM)",
                         "console": self._console,
                         "enable_remote_console": self._enable_remote_console,
                         "headless": self._headless}

        return vbox_defaults

    @property
    def id(self):
        """
        Returns the unique ID for this VirtualBox VM.

        :returns: id (integer)
        """

        return self._id

    @classmethod
    def reset(cls):
        """
        Resets allocated instance list.
        """

        cls._instances.clear()
        cls._allocated_console_ports.clear()

    @property
    def name(self):
        """
        Returns the name of this VirtualBox VM.

        :returns: name
        """

        return self._name

    @name.setter
    def name(self, new_name):
        """
        Sets the name of this VirtualBox VM.

        :param new_name: name
        """

        log.info("VirtualBox VM {name} [id={id}]: renamed to {new_name}".format(name=self._name,
                                                                                id=self._id,
                                                                                new_name=new_name))

        self._name = new_name

    @property
    def working_dir(self):
        """
        Returns current working directory

        :returns: path to the working directory
        """

        return self._working_dir

    @working_dir.setter
    def working_dir(self, working_dir):
        """
        Sets the working directory this VirtualBox VM.

        :param working_dir: path to the working directory
        """

        try:
            os.makedirs(working_dir)
        except FileExistsError:
            pass
        except OSError as e:
            raise VirtualBoxError("Could not create working directory {}: {}".format(working_dir, e))

        self._working_dir = working_dir
        log.info("VirtualBox VM {name} [id={id}]: working directory changed to {wd}".format(name=self._name,
                                                                                            id=self._id,
                                                                                            wd=self._working_dir))

    @property
    def console(self):
        """
        Returns the TCP console port.

        :returns: console port (integer)
        """

        return self._console

    @console.setter
    def console(self, console):
        """
        Sets the TCP console port.

        :param console: console port (integer)
        """

        if console in self._allocated_console_ports:
            raise VirtualBoxError("Console port {} is already used by another VirtualBox VM".format(console))

        self._allocated_console_ports.remove(self._console)
        self._console = console
        self._allocated_console_ports.append(self._console)

        log.info("VirtualBox VM {name} [id={id}]: console port set to {port}".format(name=self._name,
                                                                                     id=self._id,
                                                                                     port=console))

    def _get_all_hdd_files(self):

        hdds = []
        properties = self._execute("list", ["hdds"])
        for prop in properties:
            try:
                name, value = prop.split(':', 1)
            except ValueError:
                continue
            if name.strip() == "Location":
                hdds.append(value.strip())
        return hdds

    def _reattach_hdds(self):

        hdd_info_file = os.path.join(self._working_dir, self._vmname, "hdd_info.json")
        try:
            with open(hdd_info_file, "r") as f:
                #log.info("loading project: {}".format(path))
                hdd_table = json.load(f)
        except OSError as e:
            raise VirtualBoxError("Could not read HDD info file: {}".format(e))

        for hdd_info in hdd_table:
            hdd_file = os.path.join(self._working_dir, self._vmname, "Snapshots", hdd_info["hdd"])
            if os.path.exists(hdd_file):
                log.debug("reattaching hdd {}".format(hdd_file))
                self._storage_attach('--storagectl "{}" --port {} --device {} --type hdd --medium "{}"'.format(hdd_info["controller"],
                                                                                                               hdd_info["port"],
                                                                                                               hdd_info["device"],
                                                                                                               hdd_file))

    def delete(self):
        """
        Deletes this VirtualBox VM.
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self.console and self.console in self._allocated_console_ports:
            self._allocated_console_ports.remove(self.console)

        if self._linked_clone:
            hdd_table = []
            if os.path.exists(self._working_dir):
                hdd_files = self._get_all_hdd_files()
                vm_info = self._get_vm_info()
                for entry, value in vm_info.items():
                    match = re.search("^([\s\w]+)\-(\d)\-(\d)$", entry)
                    if match:
                        controller = match.group(1)
                        port = match.group(2)
                        device = match.group(3)
                        if value in hdd_files:
                            self._storage_attach('--storagectl "{}" --port {} --device {} --type hdd --medium none'.format(controller, port, device))
                            hdd_table.append(
                                {
                                    "hdd": os.path.basename(value),
                                    "controller": controller,
                                    "port": port,
                                    "device": device,
                                }
                            )

            self._execute("unregistervm", [self._vmname])

            if hdd_table:
                try:
                    hdd_info_file = os.path.join(self._working_dir, self._vmname, "hdd_info.json")
                    with open(hdd_info_file, "w") as f:
                        #log.info("saving project: {}".format(path))
                        json.dump(hdd_table, f, indent=4)
                except OSError as e:
                    raise VirtualBoxError("Could not write HDD info file: {}".format(e))


        log.info("VirtualBox VM {name} [id={id}] has been deleted".format(name=self._name,
                                                                          id=self._id))

    def clean_delete(self):
        """
        Deletes this VirtualBox VM & all files.
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self.console:
            self._allocated_console_ports.remove(self.console)

        if self._linked_clone:
            self._execute("unregistervm", [self._vmname, "--delete"])

        #try:
        #    shutil.rmtree(self._working_dir)
        #except OSError as e:
        #    log.error("could not delete VirtualBox VM {name} [id={id}]: {error}".format(name=self._name,
        #                                                                                id=self._id,
        #                                                                                error=e))
        #    return

        log.info("VirtualBox VM {name} [id={id}] has been deleted (including associated files)".format(name=self._name,
                                                                                                       id=self._id))

    @property
    def headless(self):
        """
        Returns either the VM will start in headless mode

        :returns: boolean
        """

        return self._headless

    @headless.setter
    def headless(self, headless):
        """
        Sets either the VM will start in headless mode

        :param headless: boolean
        """

        if headless:
            log.info("VirtualBox VM {name} [id={id}] has enabled the headless mode".format(name=self._name, id=self._id))
        else:
            log.info("VirtualBox VM {name} [id={id}] has disabled the headless mode".format(name=self._name, id=self._id))
        self._headless = headless

    @property
    def enable_remote_console(self):
        """
        Returns either the remote console is enabled or not

        :returns: boolean
        """

        return self._enable_remote_console

    @enable_remote_console.setter
    def enable_remote_console(self, enable_remote_console):
        """
        Sets either the console is enabled or not

        :param enable_remote_console: boolean
        """

        if enable_remote_console:
            log.info("VirtualBox VM {name} [id={id}] has enabled the console".format(name=self._name, id=self._id))
            self._start_remote_console()
        else:
            log.info("VirtualBox VM {name} [id={id}] has disabled the console".format(name=self._name, id=self._id))
            self._stop_remote_console()
        self._enable_remote_console = enable_remote_console

    @property
    def vmname(self):
        """
        Returns the VM name associated with this VirtualBox VM.

        :returns: VirtualBox VM name
        """

        return self._vmname

    @vmname.setter
    def vmname(self, vmname):
        """
        Sets the VM name associated with this VirtualBox VM.

        :param vmname: VirtualBox VM name
        """

        log.info("VirtualBox VM {name} [id={id}] has set the VM name to {vmname}".format(name=self._name, id=self._id, vmname=vmname))
        if self._linked_clone:
            self._modify_vm('--name "{}"'.format(vmname))
        self._vmname = vmname

    @property
    def adapters(self):
        """
        Returns the number of Ethernet adapters for this VirtualBox VM instance.

        :returns: number of adapters
        """

        return len(self._ethernet_adapters)

    @adapters.setter
    def adapters(self, adapters):
        """
        Sets the number of Ethernet adapters for this VirtualBox VM instance.

        :param adapters: number of adapters
        """

        # check for the maximum adapters supported by the VM
        self._maximum_adapters = self._get_maximum_supported_adapters()
        if len(self._ethernet_adapters) > self._maximum_adapters:
            raise VirtualBoxError("Number of adapters above the maximum supported of {}".format(self._maximum_adapters))

        self._ethernet_adapters.clear()
        for adapter_id in range(0, self._adapter_start_index + adapters):
            if adapter_id < self._adapter_start_index:
                self._ethernet_adapters.append(None)
                continue
            self._ethernet_adapters.append(EthernetAdapter())

        log.info("VirtualBox VM {name} [id={id}]: number of Ethernet adapters changed to {adapters}".format(name=self._name,
                                                                                                            id=self._id,
                                                                                                            adapters=adapters))

    @property
    def adapter_start_index(self):
        """
        Returns the adapter start index for this VirtualBox VM instance.

        :returns: index
        """

        return self._adapter_start_index

    @adapter_start_index.setter
    def adapter_start_index(self, adapter_start_index):
        """
        Sets the adapter start index for this VirtualBox VM instance.

        :param adapter_start_index: index
        """

        self._adapter_start_index = adapter_start_index
        self.adapters = self.adapters  # this forces to recreate the adapter list with the correct index
        log.info("VirtualBox VM {name} [id={id}]: adapter start index changed to {index}".format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 index=adapter_start_index))

    @property
    def adapter_type(self):
        """
        Returns the adapter type for this VirtualBox VM instance.

        :returns: adapter type (string)
        """

        return self._adapter_type

    @adapter_type.setter
    def adapter_type(self, adapter_type):
        """
        Sets the adapter type for this VirtualBox VM instance.

        :param adapter_type: adapter type (string)
        """

        self._adapter_type = adapter_type

        log.info("VirtualBox VM {name} [id={id}]: adapter type changed to {adapter_type}".format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 adapter_type=adapter_type))

    def _execute(self, subcommand, args, timeout=60):
        """
        Executes a command with VBoxManage.

        :param subcommand: vboxmanage subcommand (e.g. modifyvm, controlvm etc.)
        :param args: arguments for the subcommand.
        :param timeout: how long to wait for vboxmanage

        :returns: result (list)
        """

        command = [self._vboxmanage_path, "--nologo", subcommand]
        command.extend(args)
        log.debug("Execute vboxmanage command: {}".format(command))
        user = self._vbox_user
        try:
            if not user.strip() or sys.platform.startswith("win") or sys.platform.startswith("darwin"):
                result = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=timeout)
            else:
                sudo_command = "sudo -i -u " + user.strip() + " " + " ".join(command)
                result = subprocess.check_output(sudo_command, stderr=subprocess.STDOUT, shell=True, timeout=timeout)
        except subprocess.CalledProcessError as e:
            if e.output:
                # only the first line of the output is useful
                virtualbox_error = e.output.decode("utf-8").splitlines()[0]
                raise VirtualBoxError("{}".format(virtualbox_error))
            else:
                raise VirtualBoxError("{}".format(e))
        except (OSError, subprocess.SubprocessError) as e:
            raise VirtualBoxError("Could not execute VBoxManage: {}".format(e))
        return result.decode("utf-8", errors="ignore").splitlines()

    def _get_vm_info(self):
        """
        Returns this VM info.

        :returns: dict of info
        """

        vm_info = {}
        results = self._execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in results:
            try:
                name, value = info.split('=', 1)
            except ValueError:
                continue
            vm_info[name.strip('"')] = value.strip('"')
        return vm_info

    def _get_vm_state(self):
        """
        Returns this VM state (e.g. running, paused etc.)

        :returns: state (string)
        """

        results = self._execute("showvminfo", [self._vmname, "--machinereadable"])
        for info in results:
            name, value = info.split('=', 1)
            if name == "VMState":
                return value.strip('"')
        raise VirtualBoxError("Could not get VM state for {}".format(self._vmname))

    def _get_maximum_supported_adapters(self):
        """
        Returns the maximum adapters supported by this VM.

        :returns: maximum number of supported adapters (int)
        """

        # check the maximum number of adapters supported by the VM
        vm_info = self._get_vm_info()
        chipset = vm_info["chipset"]
        maximum_adapters = 8
        if chipset == "ich9":
            maximum_adapters = int(self._system_properties["Maximum ICH9 Network Adapter count"])
        return maximum_adapters

    def _get_pipe_name(self):
        """
        Returns the pipe name to create a serial connection.

        :returns: pipe path (string)
        """

        p = re.compile('\s+', re.UNICODE)
        pipe_name = p.sub("_", self._vmname)
        if sys.platform.startswith('win'):
            pipe_name = r"\\.\pipe\VBOX\{}".format(pipe_name)
        else:
            pipe_name = os.path.join(tempfile.gettempdir(), "pipe_{}".format(pipe_name))
        return pipe_name

    def _set_serial_console(self):
        """
        Configures the first serial port to allow a serial console connection.
        """

        # activate the first serial port
        self._modify_vm("--uart1 0x3F8 4")

        # set server mode with a pipe on the first serial port
        pipe_name = self._get_pipe_name()
        args = [self._vmname, "--uartmode1", "server", pipe_name]
        self._execute("modifyvm", args)

    def _modify_vm(self, params):
        """
        Change setting in this VM when not running.

        :param params: params to use with sub-command modifyvm
        """

        args = shlex.split(params)
        self._execute("modifyvm", [self._vmname] + args)

    def _control_vm(self, params):
        """
        Change setting in this VM when running.

        :param params: params to use with sub-command controlvm

        :returns: result of the command.
        """

        args = shlex.split(params)
        return self._execute("controlvm", [self._vmname] + args)

    def _storage_attach(self, params):
        """
        Change storage medium in this VM.

        :param params: params to use with sub-command storageattach
        """

        args = shlex.split(params)
        self._execute("storageattach", [self._vmname] + args)

    def _get_nic_attachements(self, maximum_adapters):
        """
        Returns NIC attachements.

        :param maximum_adapters: maximum number of supported adapters
        :returns: list of adapters with their Attachment setting (NAT, bridged etc.)
        """

        nics = []
        vm_info = self._get_vm_info()
        for adapter_id in range(0, maximum_adapters):
            entry = "nic{}".format(adapter_id + 1)
            if entry in vm_info:
                value = vm_info[entry]
                nics.append(value)
            else:
                nics.append(None)
        return nics

    def _set_network_options(self):
        """
        Configures network options.
        """

        nic_attachements = self._get_nic_attachements(self._maximum_adapters)
        for adapter_id in range(0, len(self._ethernet_adapters)):
            if self._ethernet_adapters[adapter_id] is None:
                # force enable to avoid any discrepancy in the interface numbering inside the VM
                # e.g. Ethernet2 in GNS3 becoming eth0 inside the VM when using a start index of 2.
                attachement = nic_attachements[adapter_id]
                if attachement:
                    # attachement can be none, null, nat, bridged, intnet, hostonly or generic
                    self._modify_vm("--nic{} {}".format(adapter_id + 1, attachement))
                continue

            vbox_adapter_type = "82540EM"
            if self._adapter_type == "PCnet-PCI II (Am79C970A)":
                vbox_adapter_type = "Am79C970A"
            if self._adapter_type == "PCNet-FAST III (Am79C973)":
                vbox_adapter_type = "Am79C973"
            if self._adapter_type == "Intel PRO/1000 MT Desktop (82540EM)":
                vbox_adapter_type = "82540EM"
            if self._adapter_type == "Intel PRO/1000 T Server (82543GC)":
                vbox_adapter_type = "82543GC"
            if self._adapter_type == "Intel PRO/1000 MT Server (82545EM)":
                vbox_adapter_type = "82545EM"
            if self._adapter_type == "Paravirtualized Network (virtio-net)":
                vbox_adapter_type = "virtio"

            args = [self._vmname, "--nictype{}".format(adapter_id + 1), vbox_adapter_type]
            self._execute("modifyvm", args)

            self._modify_vm("--nictrace{} off".format(adapter_id + 1))
            nio = self._ethernet_adapters[adapter_id].get_nio(0)
            if nio:
                log.debug("setting UDP params on adapter {}".format(adapter_id))
                self._modify_vm("--nic{} generic".format(adapter_id + 1))
                self._modify_vm("--nicgenericdrv{} UDPTunnel".format(adapter_id + 1))
                self._modify_vm("--nicproperty{} sport={}".format(adapter_id + 1, nio.lport))
                self._modify_vm("--nicproperty{} dest={}".format(adapter_id + 1, nio.rhost))
                self._modify_vm("--nicproperty{} dport={}".format(adapter_id + 1, nio.rport))
                self._modify_vm("--cableconnected{} on".format(adapter_id + 1))

                if nio.capturing:
                    self._modify_vm("--nictrace{} on".format(adapter_id + 1))
                    self._modify_vm("--nictracefile{} {}".format(adapter_id + 1, nio.pcap_output_file))
            else:
                # shutting down unused adapters...
                self._modify_vm("--cableconnected{} off".format(adapter_id + 1))
                self._modify_vm("--nic{} null".format(adapter_id + 1))

        for adapter_id in range(len(self._ethernet_adapters), self._maximum_adapters):
            log.debug("disabling remaining adapter {}".format(adapter_id))
            self._modify_vm("--nic{} none".format(adapter_id + 1))

    def _create_linked_clone(self):
        """
        Creates a new linked clone.
        """

        gns3_snapshot_exists = False
        vm_info = self._get_vm_info()
        for entry, value in vm_info.items():
            if entry.startswith("SnapshotName") and value == "GNS3 Linked Base for clones":
                gns3_snapshot_exists = True

        if not gns3_snapshot_exists:
            result = self._execute("snapshot", [self._vmname, "take", "GNS3 Linked Base for clones"])
            log.debug("GNS3 snapshot created: {}".format(result))

        args = [self._vmname,
                "--snapshot",
                "GNS3 Linked Base for clones",
                "--options",
                "link",
                "--name",
                self._name,
                "--basefolder",
                self._working_dir,
                "--register"]

        result = self._execute("clonevm", args)
        log.debug("cloned VirtualBox VM: {}".format(result))

        self._vmname = self._name
        self._execute("setextradata", [self._vmname, "GNS3/Clone", "yes"])

        args = [self._name, "take", "reset"]
        result = self._execute("snapshot", args)
        log.debug("snapshot reset created: {}".format(result))

    def _start_remote_console(self):
        """
        Starts remote console support for this VM.
        """

        # starts the Telnet to pipe thread
        pipe_name = self._get_pipe_name()
        if sys.platform.startswith('win'):
            try:
                self._serial_pipe = open(pipe_name, "a+b")
            except OSError as e:
                raise VirtualBoxError("Could not open the pipe {}: {}".format(pipe_name, e))
            self._telnet_server_thread = TelnetServer(self._vmname, msvcrt.get_osfhandle(self._serial_pipe.fileno()), self._console_host, self._console)
            self._telnet_server_thread.start()
        else:
            try:
                self._serial_pipe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._serial_pipe.connect(pipe_name)
            except OSError as e:
                raise VirtualBoxError("Could not connect to the pipe {}: {}".format(pipe_name, e))
            self._telnet_server_thread = TelnetServer(self._vmname, self._serial_pipe, self._console_host, self._console)
            self._telnet_server_thread.start()

    def _stop_remote_console(self):
        """
        Stops remote console support for this VM.
        """

        if self._telnet_server_thread:
            self._telnet_server_thread.stop()
            self._telnet_server_thread.join(timeout=3)
            if self._telnet_server_thread.isAlive():
                log.warn("Serial pire thread is still alive!")
            self._telnet_server_thread = None

        if self._serial_pipe:
            if sys.platform.startswith('win'):
                win32file.CloseHandle(msvcrt.get_osfhandle(self._serial_pipe.fileno()))
            else:
                self._serial_pipe.close()
            self._serial_pipe = None

    def start(self):
        """
        Starts this VirtualBox VM.
        """

        # resume the VM if it is paused
        vm_state = self._get_vm_state()
        if vm_state == "paused":
            self.resume()
            return

        # VM must be powered off and in saved state to start it
        if vm_state != "poweroff" and vm_state != "saved":
            raise VirtualBoxError("VirtualBox VM not powered off or saved")

        self._set_network_options()
        self._set_serial_console()

        args = [self._vmname]
        if self._headless:
            args.extend(["--type", "headless"])
        result = self._execute("startvm", args)
        log.debug("started VirtualBox VM: {}".format(result))

        # add a guest property to let the VM know about the GNS3 name
        self._execute("guestproperty", ["set", self._vmname, "NameInGNS3", self._name])

        # add a guest property to let the VM know about the GNS3 project directory
        self._execute("guestproperty", ["set", self._vmname, "ProjectDirInGNS3", self._working_dir])

        if self._enable_remote_console:
            self._start_remote_console()

    def stop(self):
        """
        Stops this VirtualBox VM.
        """

        self._stop_remote_console()
        vm_state = self._get_vm_state()
        if vm_state == "running" or vm_state == "paused" or vm_state == "stuck":
            # power off the VM
            result = self._control_vm("poweroff")
            log.debug("VirtualBox VM has been stopped: {}".format(result))

            time.sleep(0.5)  # give some time for VirtualBox to unlock the VM
            # deactivate the first serial port
            try:
                self._modify_vm("--uart1 off")
            except VirtualBoxError as e:
                log.warn("Could not deactivate the first serial port: {}".format(e))

            for adapter_id in range(0, len(self._ethernet_adapters)):
                if self._ethernet_adapters[adapter_id] is None:
                    continue
                self._modify_vm("--nictrace{} off".format(adapter_id + 1))
                self._modify_vm("--cableconnected{} off".format(adapter_id + 1))
                self._modify_vm("--nic{} null".format(adapter_id + 1))

    def suspend(self):
        """
        Suspends this VirtualBox VM.
        """

        vm_state = self._get_vm_state()
        if vm_state == "running":
            result = self._control_vm("pause")
            log.debug("VirtualBox VM has been suspended: {}".format(result))
        else:
            log.info("VirtualBox VM is not running to be suspended, current state is {}".format(vm_state))

    def resume(self):
        """
        Resumes this VirtualBox VM.
        """

        result = self._control_vm("resume")
        log.debug("VirtualBox VM has been resumed: {}".format(result))

    def reload(self):
        """
        Reloads this VirtualBox VM.
        """

        result = self._control_vm("reset")
        log.debug("VirtualBox VM has been reset: {}".format(result))

    def port_add_nio_binding(self, adapter_id, nio):
        """
        Adds a port NIO binding.

        :param adapter_id: adapter ID
        :param nio: NIO instance to add to the slot/port
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise VirtualBoxError("Adapter {adapter_id} doesn't exist on VirtualBox VM {name}".format(name=self._name,
                                                                                                      adapter_id=adapter_id))

        vm_state = self._get_vm_state()
        if vm_state == "running":
            # dynamically configure an UDP tunnel on the VirtualBox adapter
            self._control_vm("nic{} generic UDPTunnel".format(adapter_id + 1))
            self._control_vm("nicproperty{} sport={}".format(adapter_id + 1, nio.lport))
            self._control_vm("nicproperty{} dest={}".format(adapter_id + 1, nio.rhost))
            self._control_vm("nicproperty{} dport={}".format(adapter_id + 1, nio.rport))
            self._control_vm("setlinkstate{} on".format(adapter_id + 1))

        adapter.add_nio(0, nio)
        log.info("VirtualBox VM {name} [id={id}]: {nio} added to adapter {adapter_id}".format(name=self._name,
                                                                                              id=self._id,
                                                                                              nio=nio,
                                                                                              adapter_id=adapter_id))

    def port_remove_nio_binding(self, adapter_id):
        """
        Removes a port NIO binding.

        :param adapter_id: adapter ID

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise VirtualBoxError("Adapter {adapter_id} doesn't exist on VirtualBox VM {name}".format(name=self._name,
                                                                                                      adapter_id=adapter_id))

        vm_state = self._get_vm_state()
        if vm_state == "running":
            # dynamically disable the VirtualBox adapter
            self._control_vm("setlinkstate{} off".format(adapter_id + 1))
            self._control_vm("nic{} null".format(adapter_id + 1))

        nio = adapter.get_nio(0)
        adapter.remove_nio(0)
        log.info("VirtualBox VM {name} [id={id}]: {nio} removed from adapter {adapter_id}".format(name=self._name,
                                                                                                  id=self._id,
                                                                                                  nio=nio,
                                                                                                  adapter_id=adapter_id))
        return nio

    def start_capture(self, adapter_id, output_file):
        """
        Starts a packet capture.

        :param adapter_id: adapter ID
        :param output_file: PCAP destination file for the capture
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise VirtualBoxError("Adapter {adapter_id} doesn't exist on VirtualBox VM {name}".format(name=self._name,
                                                                                                      adapter_id=adapter_id))

        nio = adapter.get_nio(0)
        if nio.capturing:
            raise VirtualBoxError("Packet capture is already activated on adapter {adapter_id}".format(adapter_id=adapter_id))

        try:
            os.makedirs(os.path.dirname(output_file))
        except FileExistsError:
            pass
        except OSError as e:
            raise VirtualBoxError("Could not create captures directory {}".format(e))

        nio.startPacketCapture(output_file)

        log.info("VirtualBox VM {name} [id={id}]: starting packet capture on adapter {adapter_id}".format(name=self._name,
                                                                                                          id=self._id,
                                                                                                          adapter_id=adapter_id))

    def stop_capture(self, adapter_id):
        """
        Stops a packet capture.

        :param adapter_id: adapter ID
        """

        try:
            adapter = self._ethernet_adapters[adapter_id]
        except IndexError:
            raise VirtualBoxError("Adapter {adapter_id} doesn't exist on VirtualBox VM {name}".format(name=self._name,
                                                                                                      adapter_id=adapter_id))

        nio = adapter.get_nio(0)
        nio.stopPacketCapture()

        log.info("VirtualBox VM {name} [id={id}]: stopping packet capture on adapter {adapter_id}".format(name=self._name,
                                                                                                          id=self._id,
                                                                                                          adapter_id=adapter_id))
