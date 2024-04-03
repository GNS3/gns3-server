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
QEMU VM management (creates command line, processes, files etc.) in
order to run a QEMU VM.
"""

import sys
import os
import re
import math
import shutil
import struct
import asyncio
import socket
import gns3server
import subprocess
import time
import json
import shlex

from gns3server.utils import parse_version
from gns3server.utils.asyncio import subprocess_check_output, cancellable_wait_run_in_executor
from .qemu_error import QemuError
from .utils.qcow2 import Qcow2, Qcow2Error
from .utils.ziputils import pack_zip, unpack_zip
from ..adapters.ethernet_adapter import EthernetAdapter
from ..error import NodeError, ImageMissingError
from ..nios.nio_udp import NIOUDP
from ..nios.nio_tap import NIOTAP
from ..base_node import BaseNode
from ...utils.asyncio import monitor_process
from ...utils.images import md5sum
from ...utils import macaddress_to_int, int_to_macaddress
from ...utils.hostname import is_rfc1123_hostname_valid

from gns3server.schemas.compute.qemu_nodes import Qemu, QemuPlatform

import logging

log = logging.getLogger(__name__)


class QemuVM(BaseNode):
    module_name = "qemu"

    """
    QEMU VM implementation.

    :param name: Qemu VM name
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Manager instance
    :param console: TCP console port
    :param console_type: Console type
    :param qemu_path: path to the QEMU binary
    :param platform: Platform to emulate
    """

    def __init__(
        self,
        name,
        node_id,
        project,
        manager,
        linked_clone=True,
        qemu_path=None,
        console=None,
        console_type="telnet",
        aux=None,
        aux_type="none",
        platform=None,
    ):

        if not is_rfc1123_hostname_valid(name):
            raise QemuError(f"'{name}' is an invalid name to create a Qemu node")

        super().__init__(
            name,
            node_id,
            project,
            manager,
            console=console,
            console_type=console_type,
            linked_clone=linked_clone,
            aux=aux,
            aux_type=aux_type,
            wrap_console=True,
            wrap_aux=True,
        )

        self._host = manager.config.settings.Server.host
        self._monitor_host = manager.config.settings.Qemu.monitor_host
        self._process = None
        self._cpulimit_process = None
        self._swtpm_process = None
        self._monitor = None
        self._stdout_file = ""
        self._qemu_img_stdout_file = ""
        self._execute_lock = asyncio.Lock()
        self._local_udp_tunnels = {}
        self._guest_cid = None
        self._command_line_changed = False
        self._qemu_version = None

        # QEMU VM settings
        if qemu_path:
            try:
                self.qemu_path = qemu_path
            except QemuError:
                # If the binary is not found for topologies 1.4 and later
                # search via the platform otherwise use the binary name
                log.warning(f"Could not find the QEMU binary {qemu_path} on this system, "
                            f"trying to find one using platform {platform}")
                if platform:
                    self.platform = platform
                else:
                    self.qemu_path = os.path.basename(qemu_path)
        else:
            self.platform = platform

        self._hda_disk_image = ""
        self._hdb_disk_image = ""
        self._hdc_disk_image = ""
        self._hdd_disk_image = ""
        self._hda_disk_interface = "none"
        self._hdb_disk_interface = "none"
        self._hdc_disk_interface = "none"
        self._hdd_disk_interface = "none"
        self._cdrom_image = ""
        self._bios_image = ""
        self._boot_priority = "c"
        self._mac_address = ""
        self._options = ""
        self._ram = 256
        self._cpus = 1
        self._maxcpus = 1
        self._ethernet_adapters = []
        self._adapter_type = "e1000"
        self._initrd = ""
        self._kernel_image = ""
        self._kernel_command_line = ""
        self._replicate_network_connection_state = True
        self._tpm = False
        self._uefi = False
        self._create_config_disk = False
        self._on_close = "power_off"
        self._cpu_throttling = 0  # means no CPU throttling
        self._process_priority = "low"

        self.mac_address = ""  # this will generate a MAC address
        self.adapters = 1  # creates 1 adapter by default

        # config disk
        self.config_disk_name = self.manager.config_disk
        self.config_disk_image = ""
        if self.config_disk_name:
            if not shutil.which("mcopy"):
                log.warning("Config disk: 'mtools' are not installed.")
                self.config_disk_name = ""
            else:
                try:
                    self.config_disk_image = self.manager.get_abs_image_path(self.config_disk_name)
                except (NodeError, ImageMissingError):
                    log.warning(f"Config disk: image '{self.config_disk_name}' missing")
                    self.config_disk_name = ""

        log.info(f'QEMU VM "{self._name}" [{self._id}] has been created')

    @BaseNode.name.setter
    def name(self, new_name):
        """
        Sets the name of this Qemu VM.

        :param new_name: name
        """

        if not is_rfc1123_hostname_valid(new_name):
            raise QemuError(f"'{new_name}' is an invalid name to rename Qemu node '{self._name}'")
        super(QemuVM, QemuVM).name.__set__(self, new_name)

    @property
    def guest_cid(self):
        """
        Returns the CID (console ID) which is an unique identifier between 3 and 65535

        :returns: integer between 3 and 65535
        """

        return self._guest_cid

    @guest_cid.setter
    def guest_cid(self, guest_cid):
        """
        Set the CID (console ID) which is an unique identifier between 3 and 65535

        :returns: integer between 3 and 65535
        """

        self._guest_cid = guest_cid

    @property
    def monitor(self):
        """
        Returns the TCP monitor port.

        :returns: monitor port (integer)
        """

        return self._monitor

    @property
    def qemu_path(self):
        """
        Returns the QEMU binary path for this QEMU VM.

        :returns: QEMU path
        """

        return self._qemu_path

    @qemu_path.setter
    def qemu_path(self, qemu_path):
        """
        Sets the QEMU binary path this QEMU VM.

        :param qemu_path: QEMU path
        """

        if qemu_path and os.pathsep not in qemu_path:
            new_qemu_path = shutil.which(qemu_path, path=os.pathsep.join(self._manager.paths_list()))
            if new_qemu_path is None:
                raise QemuError(f"QEMU binary '{qemu_path}' cannot be found on the system")
            qemu_path = new_qemu_path

        self._check_qemu_path(qemu_path)
        self._qemu_path = qemu_path
        self._platform = os.path.basename(qemu_path)
        if self._platform == "qemu-kvm":
            self._platform = "x86_64"
        else:
            qemu_bin = os.path.basename(qemu_path)
            qemu_bin = re.sub(r"(w)?\.(exe|EXE)$", "", qemu_bin)
            # Old version of GNS3 provide a binary named qemu.exe
            if qemu_bin == "qemu":
                self._platform = "i386"
            else:
                self._platform = re.sub(r'^qemu-system-(\w+).*$', r'\1', qemu_bin, re.IGNORECASE)

        try:
            QemuPlatform(self._platform.split(".")[0])
        except ValueError:
            raise QemuError(f"Platform {self._platform} is unknown")
        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU path to {qemu_path}'.format(
                name=self._name, id=self._id, qemu_path=qemu_path
            )
        )

    def _check_qemu_path(self, qemu_path):

        if qemu_path is None:
            raise QemuError("QEMU binary path is not set")
        if not os.path.exists(qemu_path):
            raise QemuError(f"QEMU binary '{qemu_path}' is not accessible")
        if not os.access(qemu_path, os.X_OK):
            raise QemuError(f"QEMU binary '{qemu_path}' is not executable")

    @property
    def platform(self):
        """
        Return the current platform
        """
        return self._platform

    @platform.setter
    def platform(self, platform):

        self._platform = platform
        log.info(f"QEMU VM '{self._name}' [{self._id}] has set the platform {platform}")
        self.qemu_path = f"qemu-system-{platform}"

    def _disk_setter(self, variable, value):
        """
        Use by disk image setter for checking and apply modifications

        :param variable: Variable name in the class
        :param value: New disk value
        """

        value = self.manager.get_abs_image_path(value, self.working_dir)
        if not self.linked_clone:
            for node in self.manager.nodes:
                if node != self and getattr(node, variable) == value:
                    raise QemuError(
                        f"Sorry a node without the linked base setting enabled can only be used once on your server. {value} is already used by {node.name} in project {node.project.name}"
                    )
        setattr(self, "_" + variable, value)
        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU {variable} path to {disk_image}'.format(
                name=self._name, variable=variable, id=self._id, disk_image=value
            )
        )

    @property
    def hda_disk_image(self):
        """
        Returns the hda disk image path for this QEMU VM.

        :returns: QEMU hda disk image path
        """

        return self._hda_disk_image

    @hda_disk_image.setter
    def hda_disk_image(self, hda_disk_image):
        """
        Sets the hda disk image for this QEMU VM.

        :param hda_disk_image: QEMU hda disk image path
        """

        self._disk_setter("hda_disk_image", hda_disk_image)

    @property
    def hdb_disk_image(self):
        """
        Returns the hdb disk image path for this QEMU VM.

        :returns: QEMU hdb disk image path
        """

        return self._hdb_disk_image

    @hdb_disk_image.setter
    def hdb_disk_image(self, hdb_disk_image):
        """
        Sets the hdb disk image for this QEMU VM.

        :param hdb_disk_image: QEMU hdb disk image path
        """

        self._disk_setter("hdb_disk_image", hdb_disk_image)

    @property
    def hdc_disk_image(self):
        """
        Returns the hdc disk image path for this QEMU VM.

        :returns: QEMU hdc disk image path
        """

        return self._hdc_disk_image

    @hdc_disk_image.setter
    def hdc_disk_image(self, hdc_disk_image):
        """
        Sets the hdc disk image for this QEMU VM.

        :param hdc_disk_image: QEMU hdc disk image path
        """

        self._disk_setter("hdc_disk_image", hdc_disk_image)

    @property
    def hdd_disk_image(self):
        """
        Returns the hdd disk image path for this QEMU VM.

        :returns: QEMU hdd disk image path
        """

        return self._hdd_disk_image

    @hdd_disk_image.setter
    def hdd_disk_image(self, hdd_disk_image):
        """
        Sets the hdd disk image for this QEMU VM.

        :param hdd_disk_image: QEMU hdd disk image path
        """

        self._disk_setter("hdd_disk_image", hdd_disk_image)

    @property
    def hda_disk_interface(self):
        """
        Returns the hda disk interface this QEMU VM.

        :returns: QEMU hda disk interface
        """

        return self._hda_disk_interface

    @hda_disk_interface.setter
    def hda_disk_interface(self, hda_disk_interface):
        """
        Sets the hda disk interface for this QEMU VM.

        :param hda_disk_interface: QEMU hda disk interface
        """

        self._hda_disk_interface = hda_disk_interface
        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU hda disk interface to {interface}'.format(
                name=self._name, id=self._id, interface=self._hda_disk_interface
            )
        )

    @property
    def hdb_disk_interface(self):
        """
        Returns the hdb disk interface this QEMU VM.

        :returns: QEMU hdb disk interface
        """

        return self._hdb_disk_interface

    @hdb_disk_interface.setter
    def hdb_disk_interface(self, hdb_disk_interface):
        """
        Sets the hda disk interface for this QEMU VM.

        :param hdb_disk_interface: QEMU hdb disk interface
        """

        self._hdb_disk_interface = hdb_disk_interface
        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU hdb disk interface to {interface}'.format(
                name=self._name, id=self._id, interface=self._hdb_disk_interface
            )
        )

    @property
    def hdc_disk_interface(self):
        """
        Returns the hdc disk interface this QEMU VM.

        :returns: QEMU hdc disk interface
        """

        return self._hdc_disk_interface

    @hdc_disk_interface.setter
    def hdc_disk_interface(self, hdc_disk_interface):
        """
        Sets the hdc disk interface for this QEMU VM.

        :param hdc_disk_interface: QEMU hdc disk interface
        """

        self._hdc_disk_interface = hdc_disk_interface
        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU hdc disk interface to {interface}'.format(
                name=self._name, id=self._id, interface=self._hdc_disk_interface
            )
        )

    @property
    def hdd_disk_interface(self):
        """
        Returns the hda disk interface this QEMU VM.

        :returns: QEMU hda disk interface
        """

        return self._hdd_disk_interface

    @hdd_disk_interface.setter
    def hdd_disk_interface(self, hdd_disk_interface):
        """
        Sets the hdd disk interface for this QEMU VM.

        :param hdd_disk_interface: QEMU hdd disk interface
        """

        self._hdd_disk_interface = hdd_disk_interface
        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU hdd disk interface to {interface}'.format(
                name=self._name, id=self._id, interface=self._hdd_disk_interface
            )
        )

    @property
    def cdrom_image(self):
        """
        Returns the cdrom image path for this QEMU VM.

        :returns: QEMU cdrom image path
        """

        return self._cdrom_image

    @cdrom_image.setter
    def cdrom_image(self, cdrom_image):
        """
        Sets the cdrom image for this QEMU VM.

        :param cdrom_image: QEMU cdrom image path
        """

        if cdrom_image:
            self._cdrom_image = self.manager.get_abs_image_path(cdrom_image, self.working_dir)

            log.info(
                'QEMU VM "{name}" [{id}] has set the QEMU cdrom image path to {cdrom_image}'.format(
                    name=self._name, id=self._id, cdrom_image=self._cdrom_image
                )
            )
        else:
            self._cdrom_image = ""

    async def update_property(self, name, value):
        """
        Update Qemu VM properties.
        """

        setattr(self, name, value)
        if name == "cdrom_image":
            # let the guest know about the new cdrom image
            await self._update_cdrom_image()
        self._command_line_changed = True

    async def _update_cdrom_image(self):
        """
        Update the cdrom image path for the Qemu guest OS
        """

        if self.is_running():
            if self._cdrom_image:
                self._cdrom_option()  # this will check the cdrom image is accessible
                await self._control_vm("eject -f ide1-cd0")
                await self._control_vm(f"change ide1-cd0 {self._cdrom_image}")
                log.info(
                    'QEMU VM "{name}" [{id}] has changed the cdrom image path to {cdrom_image}'.format(
                        name=self._name, id=self._id, cdrom_image=self._cdrom_image
                    )
                )
            else:
                await self._control_vm("eject -f ide1-cd0")
                log.info(f'QEMU VM "{self._name}" [{self._id}] has ejected the cdrom image')

    @property
    def bios_image(self):
        """
        Returns the bios image path for this QEMU VM.

        :returns: QEMU bios image path
        """

        return self._bios_image

    @bios_image.setter
    def bios_image(self, bios_image):
        """
        Sets the bios image for this QEMU VM.

        :param bios_image: QEMU bios image path
        """

        self._bios_image = self.manager.get_abs_image_path(bios_image, self.working_dir)
        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU bios image path to {bios_image}'.format(
                name=self._name, id=self._id, bios_image=self._bios_image
            )
        )

    @property
    def boot_priority(self):
        """
        Returns the boot priority for this QEMU VM.

        :returns: QEMU boot priority
        """

        return self._boot_priority

    @boot_priority.setter
    def boot_priority(self, boot_priority):
        """
        Sets the boot priority for this QEMU VM.

        :param boot_priority: QEMU boot priority
        """

        self._boot_priority = boot_priority
        log.info(
            'QEMU VM "{name}" [{id}] has set the boot priority to {boot_priority}'.format(
                name=self._name, id=self._id, boot_priority=self._boot_priority
            )
        )

    @property
    def ethernet_adapters(self):
        """
        Return the list of ethernet adapters of the node
        """
        return self._ethernet_adapters

    @property
    def adapters(self):
        """
        Returns the number of Ethernet adapters for this QEMU VM.

        :returns: number of adapters
        """

        return len(self._ethernet_adapters)

    @adapters.setter
    def adapters(self, adapters):
        """
        Sets the number of Ethernet adapters for this QEMU VM.

        :param adapters: number of adapters
        """

        self._ethernet_adapters.clear()
        for adapter_number in range(0, adapters):
            self._ethernet_adapters.append(EthernetAdapter())

        log.info(
            'QEMU VM "{name}" [{id}]: number of Ethernet adapters changed to {adapters}'.format(
                name=self._name, id=self._id, adapters=adapters
            )
        )

    @property
    def adapter_type(self):
        """
        Returns the adapter type for this QEMU VM.

        :returns: adapter type (string)
        """

        return self._adapter_type

    @adapter_type.setter
    def adapter_type(self, adapter_type):
        """
        Sets the adapter type for this QEMU VM.

        :param adapter_type: adapter type (string)
        """

        self._adapter_type = adapter_type

        log.info(
            'QEMU VM "{name}" [{id}]: adapter type changed to {adapter_type}'.format(
                name=self._name, id=self._id, adapter_type=adapter_type
            )
        )

    @property
    def mac_address(self):
        """
        Returns the MAC address for this QEMU VM.

        :returns: adapter type (string)
        """

        return self._mac_address

    @mac_address.setter
    def mac_address(self, mac_address):
        """
        Sets the MAC address for this QEMU VM.

        :param mac_address: MAC address
        """

        if not mac_address:
            # use the node UUID to generate a random MAC address
            self._mac_address = f"0c:{self.id[2:4]}:{self.id[4:6]}:{self.id[6:8]}:00:00"
        else:
            self._mac_address = mac_address

        log.info(
            'QEMU VM "{name}" [{id}]: MAC address changed to {mac_addr}'.format(
                name=self._name, id=self._id, mac_addr=self._mac_address
            )
        )

    @property
    def replicate_network_connection_state(self):
        """
        Returns whether the network connection state for links is replicated in QEMU.

        :returns: boolean
        """

        return self._replicate_network_connection_state

    @replicate_network_connection_state.setter
    def replicate_network_connection_state(self, replicate_network_connection_state):
        """
        Sets whether the network connection state for links is replicated in QEMU

        :param replicate_network_connection_state: boolean
        """

        if replicate_network_connection_state:
            log.info(f'QEMU VM "{self._name}" [{self._id}] has enabled network connection state replication')
        else:
            log.info(f'QEMU VM "{self._name}" [{self._id}] has disabled network connection state replication')
        self._replicate_network_connection_state = replicate_network_connection_state

    @property
    def create_config_disk(self):
        """
        Returns whether a config disk is automatically created on HDD disk interface (secondary slave)

        :returns: boolean
        """

        return self._create_config_disk

    @create_config_disk.setter
    def create_config_disk(self, create_config_disk):
        """
        Sets whether a config disk is automatically created on HDD disk interface (secondary slave)

        :param create_config_disk: boolean
        """

        if create_config_disk:
            log.info(f'QEMU VM "{self._name}" [{self._id}] has enabled the config disk creation feature')
        else:
            log.info(f'QEMU VM "{self._name}" [{self._id}] has disabled the config disk creation feature')
        self._create_config_disk = create_config_disk

    @property
    def on_close(self):
        """
        Returns the action to execute when the VM is stopped/closed

        :returns: string
        """

        return self._on_close

    @on_close.setter
    def on_close(self, on_close):
        """
        Sets the action to execute when the VM is stopped/closed

        :param on_close: string
        """

        log.info(f'QEMU VM "{self._name}" [{self._id}] set the close action to "{on_close}"')
        self._on_close = on_close

    @property
    def cpu_throttling(self):
        """
        Returns the percentage of CPU allowed.

        :returns: integer
        """

        return self._cpu_throttling

    @cpu_throttling.setter
    def cpu_throttling(self, cpu_throttling):
        """
        Sets the percentage of CPU allowed.

        :param cpu_throttling: integer
        """

        log.info(
            'QEMU VM "{name}" [{id}] has set the percentage of CPU allowed to {cpu}'.format(
                name=self._name, id=self._id, cpu=cpu_throttling
            )
        )
        self._cpu_throttling = cpu_throttling
        self._stop_cpulimit()
        if cpu_throttling:
            self._set_cpu_throttling()

    @property
    def process_priority(self):
        """
        Returns the process priority.

        :returns: string
        """

        return self._process_priority

    @process_priority.setter
    def process_priority(self, process_priority):
        """
        Sets the process priority.

        :param process_priority: string
        """

        log.info(
            'QEMU VM "{name}" [{id}] has set the process priority to {priority}'.format(
                name=self._name, id=self._id, priority=process_priority
            )
        )
        self._process_priority = process_priority

    @property
    def ram(self):
        """
        Returns the RAM amount for this QEMU VM.

        :returns: RAM amount in MB
        """

        return self._ram

    @ram.setter
    def ram(self, ram):
        """
        Sets the amount of RAM for this QEMU VM.

        :param ram: RAM amount in MB
        """

        log.info(f'QEMU VM "{self._name}" [{self._id}] has set the RAM to {ram}')
        self._ram = ram

    @property
    def cpus(self):
        """
        Returns the number of vCPUs this QEMU VM.

        :returns: number of vCPUs.
        """

        return self._cpus

    @cpus.setter
    def cpus(self, cpus):
        """
        Sets the number of vCPUs this QEMU VM.

        :param cpus: number of vCPUs.
        """

        log.info(f'QEMU VM "{self._name}" [{self._id}] has set the number of vCPUs to {cpus}')
        self._cpus = cpus

    @property
    def maxcpus(self):
        """
        Returns the maximum number of hotpluggable vCPUs for this QEMU VM.

        :returns: maximum number of hotpluggable vCPUs.
        """

        return self._maxcpus

    @maxcpus.setter
    def maxcpus(self, maxcpus):
        """
        Sets the maximum number of hotpluggable vCPUs for this QEMU VM.

        :param maxcpus: maximum number of hotpluggable vCPUs
        """

        log.info(f'QEMU VM "{self._name}" [{self._id}] has set maximum number of hotpluggable vCPUs to {maxcpus}')
        self._maxcpus = maxcpus

    @property
    def tpm(self):
        """
        Returns whether TPM is activated for this QEMU VM.

        :returns: boolean
        """

        return self._tpm

    @tpm.setter
    def tpm(self, tpm):
        """
        Sets whether TPM is activated for this QEMU VM.

        :param tpm: boolean
        """

        if tpm:
            log.info(f'QEMU VM "{self._name}" [{self._id}] has enabled the Trusted Platform Module (TPM)')
        else:
            log.info(f'QEMU VM "{self._name}" [{self._id}] has disabled the Trusted Platform Module (TPM)')
        self._tpm = tpm

    @property
    def uefi(self):
        """
        Returns whether UEFI boot mode is activated for this QEMU VM.

        :returns: boolean
        """

        return self._uefi

    @uefi.setter
    def uefi(self, uefi):
        """
        Sets whether UEFI boot mode is activated for this QEMU VM.

        :param uefi: boolean
        """

        if uefi:
            log.info(f'QEMU VM "{self._name}" [{self._id}] has enabled the UEFI boot mode')
        else:
            log.info(f'QEMU VM "{self._name}" [{self._id}] has disabled the UEFI boot mode')
        self._uefi = uefi

    @property
    def options(self):
        """
        Returns the options for this QEMU VM.

        :returns: QEMU options
        """

        return self._options

    @options.setter
    def options(self, options):
        """
        Sets the options for this QEMU VM.

        :param options: QEMU options
        """

        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU options to {options}'.format(
                name=self._name, id=self._id, options=options
            )
        )

        # "-no-kvm" and "-no-hax' are deprecated since Qemu v5.2
        if "-no-kvm" in options:
            options = options.replace("-no-kvm", "-machine accel=tcg")
        if "-no-hax" in options:
            options = options.replace("-no-hax", "-machine accel=tcg")

        if "-enable-kvm" in options:
            if not sys.platform.startswith("linux"):
                # KVM can only be enabled on Linux
                options = options.replace("-enable-kvm", "")
            else:
                options = options.replace("-enable-kvm", "-machine accel=kvm")

        if "-enable-hax" in options:
            if not sys.platform.startswith("darwin"):
                # HAXM is only available on macOS
                options = options.replace("-enable-hax", "")
            else:
                options = options.replace("-enable-hax", "-machine accel=hax")

        self._options = options.strip()

    @property
    def initrd(self):
        """
        Returns the initrd path for this QEMU VM.

        :returns: QEMU initrd path
        """

        return self._initrd

    @initrd.setter
    def initrd(self, initrd):
        """
        Sets the initrd path for this QEMU VM.

        :param initrd: QEMU initrd path
        """

        initrd = self.manager.get_abs_image_path(initrd, self.working_dir)

        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU initrd path to {initrd}'.format(
                name=self._name, id=self._id, initrd=initrd
            )
        )
        if "asa" in initrd and self._initrd != initrd:
            self.project.emit(
                "log.warning",
                {
                    "message": "Warning ASA 8 is not supported by GNS3 and Cisco, please use ASAv instead. Depending of your hardware and OS this could not work or you could be limited to one instance. If ASA 8 is not booting their is no GNS3 solution, you must to upgrade to ASAv."
                },
            )
        self._initrd = initrd

    @property
    def kernel_image(self):
        """
        Returns the kernel image path for this QEMU VM.

        :returns: QEMU kernel image path
        """

        return self._kernel_image

    @kernel_image.setter
    def kernel_image(self, kernel_image):
        """
        Sets the kernel image path for this QEMU VM.

        :param kernel_image: QEMU kernel image path
        """

        kernel_image = self.manager.get_abs_image_path(kernel_image, self.working_dir)
        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU kernel image path to {kernel_image}'.format(
                name=self._name, id=self._id, kernel_image=kernel_image
            )
        )
        self._kernel_image = kernel_image

    @property
    def kernel_command_line(self):
        """
        Returns the kernel command line for this QEMU VM.

        :returns: QEMU kernel command line
        """

        return self._kernel_command_line

    @kernel_command_line.setter
    def kernel_command_line(self, kernel_command_line):
        """
        Sets the kernel command line for this QEMU VM.

        :param kernel_command_line: QEMU kernel command line
        """

        log.info(
            'QEMU VM "{name}" [{id}] has set the QEMU kernel command line to {kernel_command_line}'.format(
                name=self._name, id=self._id, kernel_command_line=kernel_command_line
            )
        )
        self._kernel_command_line = kernel_command_line

    async def _set_process_priority(self):
        """
        Changes the process priority
        """

        if self._process_priority == "normal":
            return

        if self._process_priority == "realtime":
            priority = -20
        elif self._process_priority == "very high":
            priority = -15
        elif self._process_priority == "high":
            priority = -5
        elif self._process_priority == "low":
            priority = 5
        elif self._process_priority == "very low":
            priority = 19
        else:
            priority = 0
        try:
            process = await asyncio.create_subprocess_exec(
                "renice", "-n", str(priority), "-p", str(self._process.pid)
            )
            await process.wait()
        except (OSError, subprocess.SubprocessError) as e:
            log.error(f'Could not change process priority for QEMU VM "{self._name}": {e}')

    def _stop_cpulimit(self):
        """
        Stops the cpulimit process.
        """

        if self._cpulimit_process and self._cpulimit_process.returncode is None:
            self._cpulimit_process.terminate()
            self._cpulimit_process = None

    def _set_cpu_throttling(self):
        """
        Limits the CPU usage for current QEMU process.
        """

        if not self.is_running():
            return

        try:
            if sys.platform.startswith("win") and hasattr(sys, "frozen"):
                cpulimit_exec = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "cpulimit", "cpulimit.exe")
            else:
                cpulimit_exec = "cpulimit"

            command = [cpulimit_exec, "--lazy", "--pid={}".format(self._process.pid), "--limit={}".format(self._cpu_throttling)]
            self._cpulimit_process = subprocess.Popen(command, cwd=self.working_dir)
            log.info(f"CPU throttled to {self._cpu_throttling}%")
        except FileNotFoundError:
            raise QemuError("cpulimit could not be found, please install it or deactivate CPU throttling")
        except (OSError, subprocess.SubprocessError) as e:
            raise QemuError(f"Could not throttle CPU: {e}")

    async def create(self):
        """
        Creates QEMU VM and sets proper MD5 hashes
        """

        # In case user upload image manually we don't have md5 sums.
        # We need generate hashes at this point, otherwise they will be generated
        # at asdict but not on separate thread.
        await cancellable_wait_run_in_executor(md5sum, self._hda_disk_image, self.working_dir)
        await cancellable_wait_run_in_executor(md5sum, self._hdb_disk_image, self.working_dir)
        await cancellable_wait_run_in_executor(md5sum, self._hdc_disk_image, self.working_dir)
        await cancellable_wait_run_in_executor(md5sum, self._hdd_disk_image, self.working_dir)

        super().create()

    async def start(self):
        """
        Starts this QEMU VM.
        """

        async with self._execute_lock:
            if self.is_running():
                # resume the VM if it is paused
                await self.resume()
                return

            if self._manager.config.settings.Qemu.enable_monitor:
                try:
                    info = socket.getaddrinfo(
                        self._monitor_host, 0, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE
                    )
                    if not info:
                        raise QemuError(f"getaddrinfo returns an empty list on {self._monitor_host}")
                    for res in info:
                        af, socktype, proto, _, sa = res
                        # let the OS find an unused port for the Qemu monitor
                        with socket.socket(af, socktype, proto) as sock:
                            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            sock.bind(sa)
                            self._monitor = sock.getsockname()[1]
                except OSError as e:
                    raise QemuError(f"Could not find free port for the Qemu monitor: {e}")

            # check if there is enough RAM to run
            self.check_available_ram(self.ram)

            # start swtpm (TPM emulator) first if TPM is enabled
            if self._tpm:
                await self._start_swtpm()

            command = await self._build_command()
            command_string = " ".join(shlex.quote(s) for s in command)
            try:
                log.info(f"Starting QEMU with: {command_string}")
                self._stdout_file = os.path.join(self.working_dir, "qemu.log")
                log.info(f"logging to {self._stdout_file}")
                with open(self._stdout_file, "w", encoding="utf-8") as fd:
                    fd.write(f"Start QEMU with {command_string}\n\nExecution log:\n")
                    self.command_line = " ".join(command)
                    self._process = await asyncio.create_subprocess_exec(
                        *command, stdout=fd, stderr=subprocess.STDOUT, cwd=self.working_dir
                    )
                log.info(f'QEMU VM "{self._name}" started PID={self._process.pid}')
                self._command_line_changed = False
                self.status = "started"
                monitor_process(self._process, self._termination_callback)
            except (OSError, subprocess.SubprocessError, UnicodeEncodeError) as e:
                stdout = self.read_stdout()
                log.error(f"Could not start QEMU {self.qemu_path}: {e}\n{stdout}")
                raise QemuError(f"Could not start QEMU {self.qemu_path}: {e}\n{stdout}")

            await self._set_process_priority()
            if self._cpu_throttling:
                self._set_cpu_throttling()
            if "-enable-kvm" in command_string or "-enable-hax" in command_string:
                self._hw_virtualization = True

            await self._start_ubridge()
            set_link_commands = []
            for adapter_number, adapter in enumerate(self._ethernet_adapters):
                nio = adapter.get_nio(0)
                if nio:
                    await self.add_ubridge_udp_connection(
                        f"QEMU-{self._id}-{adapter_number}", self._local_udp_tunnels[adapter_number][1], nio
                    )
                    if nio.suspend and self._replicate_network_connection_state:
                        set_link_commands.append(f"set_link gns3-{adapter_number} off")
                elif self._replicate_network_connection_state:
                    set_link_commands.append(f"set_link gns3-{adapter_number} off")

            if "-loadvm" not in command_string and self._replicate_network_connection_state:
                # only set the link statuses if not restoring a previous VM state
                await self._control_vm_commands(set_link_commands)

        try:
            if self.is_running():
                await self.start_wrap_console()
        except OSError as e:
            raise QemuError(f"Could not start Telnet QEMU console {e}\n")

    async def _termination_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        if self.started:
            log.info("QEMU process has stopped, return code: %d", returncode)
            await self.stop()
            if returncode != 0:
                self.project.emit(
                    "log.error",
                    {"message": f"QEMU process has stopped, return code: {returncode}\n{self.read_stdout()}"},
                )

    async def stop(self):
        """
        Stops this QEMU VM.
        """

        await self._stop_ubridge()
        async with self._execute_lock:
            # stop the QEMU process
            self._hw_virtualization = False
            if self.is_running():
                log.info(f'Stopping QEMU VM "{self._name}" PID={self._process.pid}')
                try:

                    if self.on_close == "save_vm_state":
                        await self._control_vm("stop")
                        await self._control_vm("savevm GNS3_SAVED_STATE")
                        wait_for_savevm = 120
                        while wait_for_savevm:
                            await asyncio.sleep(1)
                            status = await self._saved_state_option()
                            wait_for_savevm -= 1
                            if status != []:
                                break

                    if self.on_close == "shutdown_signal":
                        await self._control_vm("system_powerdown")
                        await gns3server.utils.asyncio.wait_for_process_termination(self._process, timeout=120)
                    else:
                        self._process.terminate()
                        await gns3server.utils.asyncio.wait_for_process_termination(self._process, timeout=3)
                except ProcessLookupError:
                    pass
                except asyncio.TimeoutError:
                    if self._process:
                        try:
                            self._process.kill()
                        except ProcessLookupError:
                            pass
                        if self._process.returncode is None:
                            log.warning(f'QEMU VM "{self._name}" PID={self._process.pid} is still running')
            self._process = None
            self._stop_cpulimit()
            self._stop_swtpm()
            if self.on_close != "save_vm_state":
                await self._clear_save_vm_stated()
            await self._export_config()
            await super().stop()

    async def _open_qemu_monitor_connection_vm(self, timeout=10):
        """
        Opens a connection to the QEMU monitor.

        :param timeout: timeout to connect to the monitor TCP server
        :returns: The reader returned is a StreamReader instance; the writer is a StreamWriter instance
        """

        begin = time.time()
        connection_success = False
        last_exception = None
        reader = writer = None
        while time.time() - begin < timeout:
            await asyncio.sleep(0.01)
            try:
                log.debug(f"Connecting to Qemu monitor on {self._monitor_host}:{self._monitor}")
                reader, writer = await asyncio.open_connection(self._monitor_host, self._monitor)
            except (asyncio.TimeoutError, OSError) as e:
                last_exception = e
                continue
            connection_success = True
            break

        if not connection_success:
            log.warning(
                "Could not connect to QEMU monitor on {}:{}: {}".format(
                    self._monitor_host, self._monitor, last_exception
                )
            )
        else:
            log.info(
                f"Connected to QEMU monitor on {self._monitor_host}:{self._monitor} after {time.time() - begin:.4f} seconds"
            )
        return reader, writer

    async def _control_vm(self, command, expected=None):
        """
        Executes a command with QEMU monitor when this VM is running.

        :param command: QEMU monitor command (e.g. info status, stop etc.)
        :param expected: An array of expected strings

        :returns: result of the command (matched object or None)
        """

        result = None
        if self.is_running() and self._monitor:
            log.info(f"Execute QEMU monitor command: {command}")
            reader, writer = await self._open_qemu_monitor_connection_vm()
            if reader is None and writer is None:
                return result

            try:
                cmd_byte = command.encode("ascii")
                writer.write(cmd_byte + b"\n")
                if not expected:
                    while True:
                        line = await asyncio.wait_for(reader.readline(), timeout=3)  # echo of the command
                        if not line or cmd_byte in line:
                            break
            except asyncio.TimeoutError:
                log.warning(f"Missing echo of command '{command}'")
            except OSError as e:
                log.warning(f"Could not write to QEMU monitor: {e}")
                writer.close()
                return result
            if expected:
                try:
                    while result is None:
                        line = await asyncio.wait_for(reader.readline(), timeout=3)
                        if not line:
                            break
                        for expect in expected:
                            if expect in line:
                                result = line.decode("utf-8").strip()
                                break
                except asyncio.TimeoutError:
                    log.warning(f"Timeout while waiting for result of command '{command}'")
                except (ConnectionError, EOFError) as e:
                    log.warning(f"Could not read from QEMU monitor: {e}")
            writer.close()
        return result

    async def _control_vm_commands(self, commands):
        """
        Executes commands with QEMU monitor when this VM is running.

        :param commands: a list of QEMU monitor commands (e.g. info status, stop etc.)
        """

        if self.is_running() and self._monitor:

            reader, writer = await self._open_qemu_monitor_connection_vm()
            if reader is None and writer is None:
                return

            for command in commands:
                log.info(f"Execute QEMU monitor command: {command}")
                try:
                    cmd_byte = command.encode("ascii")
                    writer.write(cmd_byte + b"\n")
                    while True:
                        line = await asyncio.wait_for(reader.readline(), timeout=3)  # echo of the command
                        if not line or cmd_byte in line:
                            break
                except asyncio.TimeoutError:
                    log.warning(f"Missing echo of command '{command}'")
                except OSError as e:
                    log.warning(f"Could not write to QEMU monitor: {e}")
            writer.close()

    async def close(self):
        """
        Closes this QEMU VM.
        """

        if not (await super().close()):
            return False

        # FIXME: Don't wait for ACPI shutdown when closing the project, should we?
        if self.on_close == "shutdown_signal":
            self.on_close = "power_off"
        await self.stop()

        for adapter in self._ethernet_adapters:
            if adapter is not None:
                for nio in adapter.ports.values():
                    if nio and isinstance(nio, NIOUDP):
                        self.manager.port_manager.release_udp_port(nio.lport, self._project)

        for udp_tunnel in self._local_udp_tunnels.values():
            self.manager.port_manager.release_udp_port(udp_tunnel[0].lport, self._project)
            self.manager.port_manager.release_udp_port(udp_tunnel[1].lport, self._project)
        self._local_udp_tunnels = {}

    async def _get_vm_status(self):
        """
        Returns this VM suspend status.

        Status are extracted from:
          https://github.com/qemu/qemu/blob/master/qapi-schema.json#L152

        :returns: status (string)
        """

        result = await self._control_vm(
            "info status",
            [
                b"debug",
                b"inmigrate",
                b"internal-error",
                b"io-error",
                b"paused",
                b"postmigrate",
                b"prelaunch",
                b"finish-migrate",
                b"restore-vm",
                b"running",
                b"save-vm",
                b"shutdown",
                b"suspended",
                b"watchdog",
                b"guest-panicked",
            ],
        )
        if result is None:
            return result
        status = result.rsplit(" ", 1)[1]
        if status == "running" or status == "prelaunch":
            self.status = "started"
        elif status == "suspended":
            self.status = "suspended"
        elif status == "shutdown":
            self.status = "stopped"
        return status

    async def suspend(self):
        """
        Suspends this QEMU VM.
        """

        if self.is_running():
            vm_status = await self._get_vm_status()
            if vm_status is None:
                raise QemuError("Suspending a QEMU VM is not supported")
            elif vm_status == "running" or vm_status == "prelaunch":
                await self._control_vm("stop")
                self.status = "suspended"
                log.debug("QEMU VM has been suspended")
            else:
                log.info(f"QEMU VM is not running to be suspended, current status is {vm_status}")

    async def reload(self):
        """
        Reloads this QEMU VM.
        """

        if self._command_line_changed:
            await self.stop()
            await self.start()
        else:
            await self._control_vm("system_reset")
        log.debug("QEMU VM has been reset")

    async def resume(self):
        """
        Resumes this QEMU VM.
        """

        vm_status = await self._get_vm_status()
        if vm_status is None:
            raise QemuError("Resuming a QEMU VM is not supported")
        elif vm_status == "paused":
            await self._control_vm("cont")
            self.status = "started"
            log.debug("QEMU VM has been resumed")
        else:
            log.info(f"QEMU VM is not paused to be resumed, current status is {vm_status}")

    async def adapter_add_nio_binding(self, adapter_number, nio):
        """
        Adds an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to add to the adapter
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise QemuError(
                'Adapter {adapter_number} does not exist on QEMU VM "{name}"'.format(
                    name=self._name, adapter_number=adapter_number
                )
            )

        if self.is_running():
            try:
                await self.add_ubridge_udp_connection(
                    f"QEMU-{self._id}-{adapter_number}", self._local_udp_tunnels[adapter_number][1], nio
                )
                if self._replicate_network_connection_state:
                    await self._control_vm(f"set_link gns3-{adapter_number} on")
            except (IndexError, KeyError):
                raise QemuError(
                    'Adapter {adapter_number} does not exist on QEMU VM "{name}"'.format(
                        name=self._name, adapter_number=adapter_number
                    )
                )

        adapter.add_nio(0, nio)
        log.info(
            'QEMU VM "{name}" [{id}]: {nio} added to adapter {adapter_number}'.format(
                name=self._name, id=self._id, nio=nio, adapter_number=adapter_number
            )
        )

    async def adapter_update_nio_binding(self, adapter_number, nio):
        """
        Update an adapter NIO binding.

        :param adapter_number: adapter number
        :param nio: NIO instance to update the adapter
        """

        if self.is_running():
            try:
                await self.update_ubridge_udp_connection(
                    f"QEMU-{self._id}-{adapter_number}", self._local_udp_tunnels[adapter_number][1], nio
                )
                if self._replicate_network_connection_state:
                    if nio.suspend:
                        await self._control_vm(f"set_link gns3-{adapter_number} off")
                    else:
                        await self._control_vm(f"set_link gns3-{adapter_number} on")
            except IndexError:
                raise QemuError(
                    'Adapter {adapter_number} does not exist on QEMU VM "{name}"'.format(
                        name=self._name, adapter_number=adapter_number
                    )
                )

    async def adapter_remove_nio_binding(self, adapter_number):
        """
        Removes an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise QemuError(
                'Adapter {adapter_number} does not exist on QEMU VM "{name}"'.format(
                    name=self._name, adapter_number=adapter_number
                )
            )

        await self.stop_capture(adapter_number)
        if self.is_running():
            if self._replicate_network_connection_state:
                await self._control_vm(f"set_link gns3-{adapter_number} off")
            await self._ubridge_send("bridge delete {name}".format(name=f"QEMU-{self._id}-{adapter_number}"))

        nio = adapter.get_nio(0)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        adapter.remove_nio(0)

        log.info(
            'QEMU VM "{name}" [{id}]: {nio} removed from adapter {adapter_number}'.format(
                name=self._name, id=self._id, nio=nio, adapter_number=adapter_number
            )
        )
        return nio

    def get_nio(self, adapter_number):
        """
        Gets an adapter NIO binding.

        :param adapter_number: adapter number

        :returns: NIO instance
        """

        try:
            adapter = self._ethernet_adapters[adapter_number]
        except IndexError:
            raise QemuError(
                'Adapter {adapter_number} does not exist on QEMU VM "{name}"'.format(
                    name=self._name, adapter_number=adapter_number
                )
            )

        nio = adapter.get_nio(0)

        if not nio:
            raise QemuError(f"Adapter {adapter_number} is not connected")

        return nio

    async def start_capture(self, adapter_number, output_file):
        """
        Starts a packet capture.

        :param adapter_number: adapter number
        :param output_file: PCAP destination file for the capture
        """

        nio = self.get_nio(adapter_number)
        if nio.capturing:
            raise QemuError(f"Packet capture is already activated on adapter {adapter_number}")

        nio.start_packet_capture(output_file)
        if self.ubridge:
            await self._ubridge_send(
                'bridge start_capture {name} "{output_file}"'.format(
                    name=f"QEMU-{self._id}-{adapter_number}", output_file=output_file
                )
            )

        log.info(
            "QEMU VM '{name}' [{id}]: starting packet capture on adapter {adapter_number}".format(
                name=self.name, id=self.id, adapter_number=adapter_number
            )
        )

    async def stop_capture(self, adapter_number):
        """
        Stops a packet capture.

        :param adapter_number: adapter number
        """

        nio = self.get_nio(adapter_number)
        if not nio.capturing:
            return

        nio.stop_packet_capture()
        if self.ubridge:
            await self._ubridge_send("bridge stop_capture {name}".format(name=f"QEMU-{self._id}-{adapter_number}"))

        log.info(
            "QEMU VM '{name}' [{id}]: stopping packet capture on adapter {adapter_number}".format(
                name=self.name, id=self.id, adapter_number=adapter_number
            )
        )

    async def create_disk_image(self, disk_name, options):
        """
        Create a Qemu disk

        :param disk_name: disk name
        :param options: disk creation options
        """

        try:
            qemu_img_path = self._get_qemu_img()
            img_format = options.pop("format")
            img_size = options.pop("size")
            disk_path = os.path.join(self.working_dir, disk_name)

            try:
                if os.path.exists(disk_path):
                    raise QemuError(f"Could not create disk image '{disk_name}', file already exists")
            except UnicodeEncodeError:
                raise QemuError(
                    f"Could not create disk image '{disk_name}', "
                    "Disk image name contains characters not supported by the filesystem"
                )

            command = [qemu_img_path, "create", "-f", img_format]
            for option in sorted(options.keys()):
                command.extend(["-o", f"{option}={options[option]}"])
            command.append(disk_path)
            command.append(f"{img_size}M")
            retcode = await self._qemu_img_exec(command)
            if retcode:
                stdout = self.read_qemu_img_stdout()
                raise QemuError(f"Could not create '{disk_name}' disk image: qemu-img returned with {retcode}\n{stdout}")
            else:
                log.info(f"QEMU VM '{self.name}' [{self.id}]: Qemu disk image'{disk_name}' created")
        except (OSError, subprocess.SubprocessError) as e:
            stdout = self.read_qemu_img_stdout()
            raise QemuError(f"Could not create '{disk_name}' disk image: {e}\n{stdout}")

    async def resize_disk_image(self, disk_name, extend):
        """
        Resize a Qemu disk

        :param disk_name: disk name
        :param extend: new size
        """

        try:
            qemu_img_path = self._get_qemu_img()
            disk_path = os.path.join(self.working_dir, disk_name)
            if not os.path.exists(disk_path):
                raise QemuError(f"Qemu disk image '{disk_name}' does not exist")

            command = [qemu_img_path, "resize", disk_path, f"+{extend}M"]
            retcode = await self._qemu_img_exec(command)
            if retcode:
                stdout = self.read_qemu_img_stdout()
                raise QemuError(f"Could not update '{disk_name}' disk image: qemu-img returned with {retcode}\n{stdout}")
            else:
                log.info(f"QEMU VM '{self.name}' [{self.id}]: Qemu disk image '{disk_name}' extended by {extend} MB")
        except (OSError, subprocess.SubprocessError) as e:
            stdout = self.read_qemu_img_stdout()
            raise QemuError(f"Could not update '{disk_name}' disk image: {e}\n{stdout}")

    def delete_disk_image(self, disk_name):
        """
        Delete a Qemu disk

        :param disk_name: disk name
        """

        disk_path = os.path.join(self.working_dir, disk_name)
        if not os.path.exists(disk_path):
            raise QemuError(f"Qemu disk image '{disk_name}' does not exist")

        try:
            os.remove(disk_path)
        except OSError as e:
            raise QemuError(f"Could not delete '{disk_name}' disk image: {e}")

    @property
    def started(self):
        """
        Returns either this QEMU VM has been started or not.

        :returns: boolean
        """

        return self.status == "started"

    def read_stdout(self):
        """
        Reads the standard output of the QEMU process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._stdout_file:
            try:
                with open(self._stdout_file, "rb") as file:
                    output = file.read().decode("utf-8", errors="replace")
            except OSError as e:
                log.warning(f"Could not read {self._stdout_file}: {e}")
        return output

    def read_qemu_img_stdout(self):
        """
        Reads the standard output of the QEMU-IMG process.
        """

        output = ""
        if self._qemu_img_stdout_file:
            try:
                with open(self._qemu_img_stdout_file, "rb") as file:
                    output = file.read().decode("utf-8", errors="replace")
            except OSError as e:
                log.warning(f"Could not read {self._qemu_img_stdout_file}: {e}")
        return output

    def is_running(self):
        """
        Checks if the QEMU process is running

        :returns: True or False
        """

        if self._process:
            if self._process.returncode is None:
                return True
            else:
                self._process = None
        return False

    async def reset_console(self):
        """
        Reset console
        """

        if self.is_running():
            await self.reset_wrap_console()

    def command(self):
        """
        Returns the QEMU command line.

        :returns: QEMU command line (string)
        """

        return " ".join(self._build_command())

    @BaseNode.console_type.setter
    def console_type(self, new_console_type):
        """
        Sets the console type for this QEMU VM.

        :param new_console_type: console type (string)
        """

        if self.is_running() and self.console_type != new_console_type:
            raise QemuError(f'"{self._name}" must be stopped to change the console type to {new_console_type}')

        super(QemuVM, QemuVM).console_type.__set__(self, new_console_type)

    def _serial_options(self, internal_console_port, external_console_port):

        if external_console_port:
            return ["-serial", f"telnet:127.0.0.1:{internal_console_port},server,nowait"]
        else:
            return []

    def _vnc_options(self, port):

        if port:
            vnc_port = port - 5900  # subtract by 5900 to get the display number
            return ["-vnc", f"{self._manager.port_manager.console_host}:{vnc_port}"]
        else:
            return []

    def _spice_options(self, port):

        if port:
            console_host = self._manager.port_manager.console_host
            if console_host == "0.0.0.0":
                if socket.has_ipv6:
                    # to fix an issue with Qemu when IPv4 is not enabled
                    # see https://github.com/GNS3/gns3-gui/issues/2352
                    # FIXME: consider making this more global (not just for Qemu + SPICE)
                    console_host = "::"
                else:
                    raise QemuError("IPv6 must be enabled in order to use the SPICE console")
            return ["-spice", f"addr={console_host},port={port},disable-ticketing", "-vga", "qxl"]
        else:
            return []

    def _spice_with_agent_options(self, port):

        spice_options = self._spice_options(port)
        if spice_options:
            # agent options (mouse/screen)
            agent_options = [
                "-device",
                "virtio-serial",
                "-chardev",
                "spicevmc,id=vdagent,debug=0,name=vdagent",
                "-device",
                "virtserialport,chardev=vdagent,name=com.redhat.spice.0",
            ]
            spice_options.extend(agent_options)
            # folder sharing options
            folder_sharing_options = [
                "-chardev",
                "spiceport,name=org.spice-space.webdav.0,id=charchannel0",
                "-device",
                "virtserialport,chardev=charchannel0,id=channel0,name=org.spice-space.webdav.0",
            ]
            spice_options.extend(folder_sharing_options)
        return spice_options

    def _console_options(self):

        if self._console_type == "telnet" and self._wrap_console:
            return self._serial_options(self._internal_console_port, self.console)
        elif self._console_type == "vnc":
            return self._vnc_options(self.console)
        elif self._console_type == "spice":
            return self._spice_options(self.console)
        elif self._console_type == "spice+agent":
            return self._spice_with_agent_options(self.console)
        elif self._console_type != "none":
            raise QemuError(f"Console type {self._console_type} is unknown")

    def _aux_options(self):

        if self._aux_type != "none" and self._aux_type == self._console_type:
            raise QemuError(f"Auxiliary console type {self._aux_type} cannot be the same as console type")

        if self._aux_type == "telnet" and self._wrap_aux:
            return self._serial_options(self._internal_aux_port, self.aux)
        elif self._aux_type == "vnc":
            return self._vnc_options(self.aux)
        elif self._aux_type == "spice":
            return self._spice_options(self.aux)
        elif self._aux_type == "spice+agent":
            return self._spice_with_agent_options(self.aux)
        elif self._aux_type != "none":
            raise QemuError(f"Auxiliary console type {self._aux_type} is unknown")
        return []

    def _monitor_options(self):

        if self._monitor:
            return ["-monitor", f"tcp:{self._monitor_host}:{self._monitor},server,nowait"]
        else:
            return []

    def _get_qemu_img(self):
        """
        Search the qemu-img binary in the same binary of the qemu binary
        to avoid version incompatibility.

        :returns: qemu-img path or raise an error
        """

        qemu_path_dir = os.path.dirname(self.qemu_path)
        qemu_image_path = shutil.which("qemu-img", path=qemu_path_dir)
        if qemu_image_path:
            return qemu_image_path
        raise QemuError(f"Could not find qemu-img in {qemu_path_dir}")

    async def _qemu_img_exec(self, command):

        self._qemu_img_stdout_file = os.path.join(self.working_dir, "qemu-img.log")
        log.info(f"logging to {self._qemu_img_stdout_file}")
        command_string = " ".join(shlex.quote(s) for s in command)
        log.info(f"Executing qemu-img with: {command_string}")
        with open(self._qemu_img_stdout_file, "w", encoding="utf-8") as fd:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=fd, stderr=subprocess.STDOUT, cwd=self.working_dir
            )
        retcode = await process.wait()
        if retcode != 0:
            log.info(f"{self._get_qemu_img()} returned with {retcode}")
        return retcode

    async def _find_disk_file_format(self, disk):

        qemu_img_path = self._get_qemu_img()
        try:
            output = await subprocess_check_output(qemu_img_path, "info", "--output=json", disk)
        except subprocess.SubprocessError as e:
            raise QemuError(f"Error received while checking Qemu disk format: {e}")
        if output:
            try:
                json_data = json.loads(output)
            except ValueError as e:
                raise QemuError(f"Invalid JSON data returned by qemu-img: {e}")
            return json_data.get("format")

    async def _create_linked_clone(self, disk_name, disk_image, disk):

        try:
            qemu_img_path = self._get_qemu_img()
            backing_file_format = await self._find_disk_file_format(disk_image)
            if not backing_file_format:
                raise QemuError(f"Could not detect format for disk image: {disk_image}")
            backing_options, base_qcow2 = Qcow2.backing_options(disk_image)
            if base_qcow2 and base_qcow2.crypt_method:
                # Workaround for https://gitlab.com/qemu-project/qemu/-/issues/441
                # (we have to pass -u and the size).  Also embed secret name.
                command = [qemu_img_path, "create", "-b", backing_options,
                           "-F", backing_file_format, "-f", "qcow2", "-u", disk, str(base_qcow2.size)]
            else:
                command = [qemu_img_path, "create", "-o", "backing_file={}".format(disk_image),
                           "-F", backing_file_format, "-f", "qcow2", disk]

            retcode = await self._qemu_img_exec(command)
            if retcode:
                stdout = self.read_qemu_img_stdout()
                raise QemuError(
                    "Could not create '{}' disk image: qemu-img returned with {}\n{}".format(disk_name, retcode, stdout)
                )
        except (OSError, subprocess.SubprocessError) as e:
            stdout = self.read_qemu_img_stdout()
            raise QemuError(f"Could not create '{disk_name}' disk image: {e}\n{stdout}")

    async def _mcopy(self, image, *args):
        try:
            # read offset of first partition from MBR
            with open(image, "rb") as img_file:
                mbr = img_file.read(512)
            part_type, offset, signature = struct.unpack("<450xB3xL52xH", mbr)
            if signature != 0xAA55:
                raise OSError(f"mcopy failure: {image}: invalid MBR")
            if part_type not in (1, 4, 6, 11, 12, 14):
                raise OSError("mcopy failure: {}: invalid partition type {:02X}".format(image, part_type))
            part_image = image + f"@@{offset}S"

            process = await asyncio.create_subprocess_exec(
                "mcopy",
                "-i",
                part_image,
                *args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.working_dir,
            )
            (stdout, _) = await process.communicate()
            retcode = process.returncode
        except (OSError, subprocess.SubprocessError) as e:
            raise OSError(f"mcopy failure: {e}")
        if retcode != 0:
            stdout = stdout.decode("utf-8").rstrip()
            if stdout:
                raise OSError(f"mcopy failure: {stdout}")
            else:
                raise OSError(f"mcopy failure: return code {retcode}")

    async def _export_config(self):
        disk_name = getattr(self, "config_disk_name")
        if not disk_name:
            return
        disk = os.path.join(self.working_dir, disk_name)
        if not os.path.exists(disk):
            return
        config_dir = os.path.join(self.working_dir, "configs")
        zip_file = os.path.join(self.working_dir, "config.zip")
        try:
            os.mkdir(config_dir)
            await self._mcopy(disk, "-s", "-m", "-n", "--", "::/", config_dir)
            if os.path.exists(zip_file):
                os.remove(zip_file)
            pack_zip(zip_file, config_dir)
        except OSError as e:
            log.warning(f"Can't export config: {e}")
            self.project.emit("log.warning", {"message": f"{self._name}: Can't export config: {e}"})
        shutil.rmtree(config_dir, ignore_errors=True)

    async def _import_config(self):
        disk_name = getattr(self, "config_disk_name")
        zip_file = os.path.join(self.working_dir, "config.zip")
        if not disk_name or not os.path.exists(zip_file):
            return
        config_dir = os.path.join(self.working_dir, "configs")
        disk = os.path.join(self.working_dir, disk_name)
        disk_tmp = disk + ".tmp"
        try:
            os.mkdir(config_dir)
            shutil.copyfile(getattr(self, "config_disk_image"), disk_tmp)
            unpack_zip(zip_file, config_dir)
            config_files = [os.path.join(config_dir, fname) for fname in os.listdir(config_dir)]
            if config_files:
                await self._mcopy(disk_tmp, "-s", "-m", "-o", "--", *config_files, "::/")
            os.replace(disk_tmp, disk)
        except OSError as e:
            log.warning(f"Can't import config: {e}")
            self.project.emit("log.warning", {"message": f"{self._name}: Can't import config: {e}"})
            if os.path.exists(disk_tmp):
                os.remove(disk_tmp)
                os.remove(zip_file)
        shutil.rmtree(config_dir, ignore_errors=True)

    async def _disk_interface_options(self, disk, disk_index, interface, format=None):
        options = []
        extra_drive_options = ""
        if format:
            extra_drive_options += f",format={format}"

        # From Qemu man page: if the filename contains comma, you must double it
        # (for instance, "file=my,,file" to use file "my,file").
        disk = disk.replace(",", ",,")

        if interface == "sata":
            # special case, sata controller doesn't exist in Qemu
            options.extend(["-device", f"ahci,id=ahci{disk_index}"])
            options.extend(
                [
                    "-drive",
                    f"file={disk},if=none,id=drive{disk_index},index={disk_index},media=disk{extra_drive_options}",
                ]
            )
            if self._qemu_version and parse_version(self._qemu_version) >= parse_version("4.2.0"):
                # The ‘ide-drive’ device is deprecated since version 4.2.0
                # https://qemu.readthedocs.io/en/latest/system/deprecated.html#ide-drive-since-4-2
                options.extend(
                    ["-device", f"ide-hd,drive=drive{disk_index},bus=ahci{disk_index}.0,id=drive{disk_index}"]
                )
            else:
                options.extend(
                    ["-device", f"ide-drive,drive=drive{disk_index},bus=ahci{disk_index}.0,id=drive{disk_index}"]
                )
        elif interface == "nvme":
            options.extend(
                [
                    "-drive",
                    f"file={disk},if=none,id=drive{disk_index},index={disk_index},media=disk{extra_drive_options}",
                ]
            )
            options.extend(["-device", f"nvme,drive=drive{disk_index},serial={disk_index}"])
        elif interface == "scsi":
            options.extend(["-device", f"virtio-scsi-pci,id=scsi{disk_index}"])
            options.extend(
                [
                    "-drive",
                    f"file={disk},if=none,id=drive{disk_index},index={disk_index},media=disk{extra_drive_options}",
                ]
            )
            options.extend(["-device", f"scsi-hd,drive=drive{disk_index}"])
        # elif interface == "sd":
        #    options.extend(["-drive", 'file={},id=drive{},index={}{}'.format(disk, disk_index, disk_index, extra_drive_options)])
        #    options.extend(["-device", 'sd-card,drive=drive{},id=drive{}'.format(disk_index, disk_index, disk_index)])
        else:
            options.extend(
                [
                    "-drive",
                    f"file={disk},if={interface},index={disk_index},media=disk,id=drive{disk_index}{extra_drive_options}",
                ]
            )
        return options

    async def _disk_options(self):
        options = []
        qemu_img_path = self._get_qemu_img()

        drives = ["a", "b", "c", "d"]

        for disk_index, drive in enumerate(drives):
            # prioritize config disk over normal disks
            if drive == "d" and self._create_config_disk:
                continue

            disk_image = getattr(self, f"_hd{drive}_disk_image")
            if not disk_image:
                continue

            interface = getattr(self, f"hd{drive}_disk_interface")
            # fail-safe: use "ide" if there is a disk image and no interface type has been explicitly configured
            if interface == "none":
                interface = "ide"
                setattr(self, f"hd{drive}_disk_interface", interface)

            disk_name = f"hd{drive}"
            if not os.path.isfile(disk_image) or not os.path.exists(disk_image):
                if os.path.islink(disk_image):
                    raise QemuError(
                        f"'{disk_name}' disk image linked to "
                        f"'{os.path.realpath(disk_image)}' is not accessible"
                    )
                else:
                    raise QemuError(f"'{disk_image}' is not accessible")
            else:
                try:
                    # check for corrupt disk image
                    retcode = await self._qemu_img_exec([qemu_img_path, "check", disk_image])
                    # ignore retcode == 1, one reason is that the image is encrypted and
                    # there is no encrypt.key-secret available
                    if retcode == 3:
                        # image has leaked clusters, but is not corrupted, let's try to fix it
                        log.warning(f"Disk image '{disk_image}' has leaked clusters")
                        if await self._qemu_img_exec([qemu_img_path, "check", "-r", "leaks", f"{disk_image}"]) == 3:
                            self.project.emit(
                                "log.warning",
                                {"message": f"Disk image '{disk_image}' has leaked clusters and could not be fixed"}
                            )
                    elif retcode == 2:
                        # image is corrupted, let's try to fix it
                        log.warning(f"Disk image '{disk_image}' is corrupted")
                        if await self._qemu_img_exec([qemu_img_path, "check", "-r", "all", f"{disk_image}"]) == 2:
                            self.project.emit(
                                "log.warning",
                                {"message": f"Disk image '{disk_image}' is corrupted and could not be fixed"}
                            )
                except (OSError, subprocess.SubprocessError) as e:
                    stdout = self.read_qemu_img_stdout()
                    raise QemuError(f"Could not check '{disk_name}' disk image: {e}\n{stdout}")

            if self.linked_clone and os.path.dirname(disk_image) != self.working_dir:

                #cloned_disk_image = os.path.splitext(os.path.basename(disk_image))
                disk = os.path.join(self.working_dir, f"{disk_name}_disk.qcow2")
                if not os.path.exists(disk):
                    # create the disk
                    await self._create_linked_clone(disk_name, disk_image, disk)
                else:
                    backing_file_format = await self._find_disk_file_format(disk_image)
                    if not backing_file_format:
                        raise QemuError(f"Could not detect format for disk image '{disk_image}'")
                    # Rebase the image. This is in case the base image moved to a different directory,
                    # which will be the case if we imported a portable project. This uses
                    # get_abs_image_path(hdX_disk_image) and ignores the old base path embedded
                    # in the qcow2 file itself.
                    try:
                        qcow2 = Qcow2(disk)
                        await qcow2.rebase(qemu_img_path, disk_image, backing_file_format)
                    except (Qcow2Error, OSError) as e:
                        raise QemuError(f"Could not use qcow2 disk image '{disk_image}' for {disk_name} {e}")

            else:
                disk = disk_image

            options.extend(await self._disk_interface_options(disk, disk_index, interface))

        # config disk
        disk_image = getattr(self, "config_disk_image")
        if disk_image and self._create_config_disk:
            disk_name = getattr(self, "config_disk_name")
            disk = os.path.join(self.working_dir, disk_name)
            if self.hdd_disk_interface == "none":
                # use the HDA interface type if none has been configured for HDD
                self.hdd_disk_interface = getattr(self, "hda_disk_interface", "none")
            await self._import_config()
            disk_exists = os.path.exists(disk)
            if not disk_exists:
                try:
                    shutil.copyfile(disk_image, disk)
                    disk_exists = True
                except OSError as e:
                    log.warning(f"Could not create '{disk_name}' disk image: {e}")
            if disk_exists:
                options.extend(await self._disk_interface_options(disk, 3, self.hdd_disk_interface, "raw"))

        return options

    async def resize_disk(self, drive_name, extend):

        if self.is_running():
            raise QemuError(f"Cannot resize {drive_name} while the VM is running")

        if self.linked_clone:
            disk_image_path = os.path.join(self.working_dir, f"{drive_name}_disk.qcow2")
            if not os.path.exists(disk_image_path):
                disk_image = getattr(self, f"_{drive_name}_disk_image")
                await self._create_linked_clone(drive_name, disk_image, disk_image_path)
        else:
            disk_image_path = getattr(self, f"{drive_name}_disk_image")

        if not os.path.exists(disk_image_path):
            raise QemuError(f"Disk path '{disk_image_path}' does not exist")
        qemu_img_path = self._get_qemu_img()
        await self.manager.resize_disk(qemu_img_path, disk_image_path, extend)

    def _cdrom_option(self):

        options = []
        if self._cdrom_image:
            if not os.path.isfile(self._cdrom_image) or not os.path.exists(self._cdrom_image):
                if os.path.islink(self._cdrom_image):
                    raise QemuError(
                        f"cdrom image '{self._cdrom_image}' linked to '{os.path.realpath(self._cdrom_image)}' is not accessible"
                    )
                else:
                    raise QemuError(f"cdrom image '{self._cdrom_image}' is not accessible")
            if self._hdc_disk_image:
                raise QemuError("You cannot use a disk image on hdc disk and a CDROM image at the same time")
            options.extend(["-cdrom", self._cdrom_image.replace(",", ",,")])
        return options

    def _bios_option(self):

        options = []
        if self._bios_image:
            if self._uefi:
                raise QemuError("Cannot use a bios image and the UEFI boot mode at the same time")
            if not os.path.isfile(self._bios_image) or not os.path.exists(self._bios_image):
                if os.path.islink(self._bios_image):
                    raise QemuError(
                        f"bios image '{self._bios_image}' linked to '{os.path.realpath(self._bios_image)}' is not accessible"
                    )
                else:
                    raise QemuError(f"bios image '{self._bios_image}' is not accessible")
            options.extend(["-bios", self._bios_image.replace(",", ",,")])
        elif self._uefi:
            # get the OVMF firmware from the images directory
            ovmf_firmware_path = self.manager.get_abs_image_path("OVMF_CODE.fd")
            log.info("Configuring UEFI boot mode using OVMF file: '{}'".format(ovmf_firmware_path))
            options.extend(["-drive", "if=pflash,format=raw,readonly,file={}".format(ovmf_firmware_path)])

            # the node should have its own copy of OVMF_VARS.fd (the UEFI variables store)
            ovmf_vars_node_path = os.path.join(self.working_dir, "OVMF_VARS.fd")
            if not os.path.exists(ovmf_vars_node_path):
                try:
                    shutil.copyfile(self.manager.get_abs_image_path("OVMF_VARS.fd"), ovmf_vars_node_path)
                except OSError as e:
                    raise QemuError("Cannot copy OVMF_VARS.fd file to the node working directory: {}".format(e))
            options.extend(["-drive", "if=pflash,format=raw,file={}".format(ovmf_vars_node_path)])
        return options

    def _linux_boot_options(self):

        options = []
        if self._initrd:
            if not os.path.isfile(self._initrd) or not os.path.exists(self._initrd):
                if os.path.islink(self._initrd):
                    raise QemuError(
                        f"initrd file '{self._initrd}' linked to '{os.path.realpath(self._initrd)}' is not accessible"
                    )
                else:
                    raise QemuError(f"initrd file '{self._initrd}' is not accessible")
            options.extend(["-initrd", self._initrd.replace(",", ",,")])
        if self._kernel_image:
            if not os.path.isfile(self._kernel_image) or not os.path.exists(self._kernel_image):
                if os.path.islink(self._kernel_image):
                    raise QemuError(
                        f"kernel image '{self._kernel_image}' linked to '{os.path.realpath(self._kernel_image)}' is not accessible"
                    )
                else:
                    raise QemuError(f"kernel image '{self._kernel_image}' is not accessible")
            options.extend(["-kernel", self._kernel_image.replace(",", ",,")])
        if self._kernel_command_line:
            options.extend(["-append", self._kernel_command_line])
        return options

    async def _start_swtpm(self):
        """
        Start swtpm (TPM emulator)
        """

        if sys.platform.startswith("win"):
            raise QemuError("swtpm (TPM emulator) is not supported on Windows")
        tpm_dir = os.path.join(self.working_dir, "tpm")
        os.makedirs(tpm_dir, exist_ok=True)
        tpm_sock = os.path.join(self.temporary_directory, "swtpm.sock")
        swtpm = shutil.which("swtpm")
        if not swtpm:
            raise QemuError("Could not find swtpm (TPM emulator)")
        swtpm_version = await self.manager.get_swtpm_version(swtpm)
        if swtpm_version and parse_version(swtpm_version) < parse_version("0.8.0"):
            # swtpm >= version 0.8.0 is required
            raise QemuError("swtpm version 0.8.0 or above must be installed (detected version is {})".format(swtpm_version))
        try:
            command = [
                swtpm,
                "socket",
                "--tpm2",
                '--tpmstate', "dir={}".format(tpm_dir),
                "--ctrl",
                "type=unixio,path={},terminate".format(tpm_sock)
            ]
            command_string = " ".join(shlex.quote(s) for s in command)
            log.info("Starting swtpm (TPM emulator) with: {}".format(command_string))
            self._swtpm_process = subprocess.Popen(command, cwd=self.working_dir)
            log.info("swtpm (TPM emulator) has started")
        except (OSError, subprocess.SubprocessError) as e:
            raise QemuError("Could not start swtpm (TPM emulator): {}".format(e))

    def _stop_swtpm(self):
        """
        Stop swtpm (TPM emulator)
        """

        if self._swtpm_process and self._swtpm_process.returncode is None:
            self._swtpm_process.terminate()
            self._swtpm_process = None

    def _tpm_options(self):
        """
        Return the TPM options for Qemu.
        """

        tpm_sock = os.path.join(self.temporary_directory, "swtpm.sock")
        if not os.path.exists(tpm_sock):
            raise QemuError("swtpm socket file '{}' does not exist".format(tpm_sock))
        options = [
            "-chardev",
            "socket,id=chrtpm,path={}".format(tpm_sock),
            "-tpmdev",
            "emulator,id=tpm0,chardev=chrtpm",
            "-device",
            "tpm-tis,tpmdev=tpm0"
        ]
        return options

    async def _network_options(self):

        network_options = []
        network_options.extend(
            ["-net", "none"]
        )  # we do not want any user networking back-end if no adapter is connected.

        # Each 32 PCI device we need to add a PCI bridge with max 9 bridges
        pci_devices = 4 + len(self._ethernet_adapters)  # 4 PCI devices are use by default by qemu
        pci_bridges = math.floor(pci_devices / 32)
        pci_bridges_created = 0
        if pci_bridges >= 1:
            if self._qemu_version and parse_version(self._qemu_version) < parse_version("2.4.0"):
                raise QemuError(
                    "Qemu version 2.4 or later is required to run this VM with a large number of network adapters"
                )

        pci_device_id = 4 + pci_bridges  # Bridge consume PCI ports
        for adapter_number, adapter in enumerate(self._ethernet_adapters):
            mac = int_to_macaddress(macaddress_to_int(self._mac_address) + adapter_number)

            # use a local UDP tunnel to connect to uBridge instead
            if adapter_number not in self._local_udp_tunnels:
                self._local_udp_tunnels[adapter_number] = self._create_local_udp_tunnel()
            nio = self._local_udp_tunnels[adapter_number][0]

            custom_adapter = self._get_custom_adapter_settings(adapter_number)
            adapter_type = custom_adapter.get("adapter_type", self._adapter_type)
            custom_mac_address = custom_adapter.get("mac_address")
            if custom_mac_address:
                mac = int_to_macaddress(macaddress_to_int(custom_mac_address))

            device_string = f"{adapter_type},mac={mac}"
            if adapter_type == "virtio-net-pci":
                device_string = "{},speed=10000,duplex=full".format(device_string)
            bridge_id = math.floor(pci_device_id / 32)
            if bridge_id > 0:
                if pci_bridges_created < bridge_id:
                    network_options.extend(["-device", f"i82801b11-bridge,id=dmi_pci_bridge{bridge_id}"])
                    network_options.extend(
                        [
                            "-device",
                            "pci-bridge,id=pci-bridge{bridge_id},bus=dmi_pci_bridge{bridge_id},chassis_nr=0x1,addr=0x{bridge_id},shpc=off".format(
                                bridge_id=bridge_id
                            ),
                        ]
                    )
                    pci_bridges_created += 1
                addr = pci_device_id % 32
                device_string = f"{device_string},bus=pci-bridge{bridge_id},addr=0x{addr:02x}"
            pci_device_id += 1
            if nio:
                network_options.extend(["-device", f"{device_string},netdev=gns3-{adapter_number}"])
                if isinstance(nio, NIOUDP):
                    network_options.extend(
                        [
                            "-netdev",
                            "socket,id=gns3-{},udp={}:{},localaddr={}:{}".format(
                                adapter_number, nio.rhost, nio.rport, "127.0.0.1", nio.lport
                            ),
                        ]
                    )
                elif isinstance(nio, NIOTAP):
                    network_options.extend(
                        ["-netdev", f"tap,id=gns3-{adapter_number},ifname={nio.tap_device},script=no,downscript=no"]
                    )
            else:
                network_options.extend(["-device", device_string])

        return network_options

    async def _disable_graphics(self):
        """
        Disable graphics depending of the QEMU version
        """

        if any(opt in self._options for opt in ["-display", "-nographic", "-curses", "-sdl" "-spice", "-vnc"]):
            return []
        if self._qemu_version and parse_version(self._qemu_version) >= parse_version("3.0"):
            return ["-display", "none"]
        else:
            return ["-nographic"]

    async def _run_with_hardware_acceleration(self, qemu_path, options):
        """
        Check if we can run Qemu with hardware acceleration

        :param qemu_path: Path to qemu
        :param options: String of qemu user options
        :returns: Boolean True if we need to enable hardware acceleration
        """

        enable_hardware_accel = self.manager.config.settings.Qemu.enable_hardware_acceleration
        require_hardware_accel = self.manager.config.settings.Qemu.require_hardware_acceleration
        if enable_hardware_accel and "-machine accel=tcg" not in options:
            # Turn OFF hardware acceleration for non x86 architectures
            supported_binaries = ["qemu-system-x86_64", "qemu-system-i386", "qemu-kvm"]
            if os.path.basename(qemu_path) not in supported_binaries:
                if require_hardware_accel:
                    raise QemuError(
                        "Hardware acceleration can only be used with the following Qemu executables: {}".format(
                            ", ".join(supported_binaries)
                        )
                    )
                else:
                    return False

            if sys.platform.startswith("linux") and not os.path.exists("/dev/kvm"):
                if require_hardware_accel:
                    raise QemuError(
                        "KVM acceleration cannot be used (/dev/kvm doesn't exist). It is possible to turn off KVM support in the gns3_server.conf by adding enable_hardware_acceleration = false to the [Qemu] section."
                    )
                else:
                    return False
            elif sys.platform.startswith("darwin"):
                process = await asyncio.create_subprocess_shell("kextstat | grep com.intel.kext.intelhaxm")
                await process.wait()
                if process.returncode != 0:
                    if require_hardware_accel:
                        raise QemuError(
                            "HAXM acceleration support is not installed on this host (com.intel.kext.intelhaxm extension not loaded)"
                        )
                    else:
                        return False
            return True
        return False

    async def _clear_save_vm_stated(self, snapshot_name="GNS3_SAVED_STATE"):

        drives = ["a", "b", "c", "d"]
        qemu_img_path = self._get_qemu_img()
        for disk_index, drive in enumerate(drives):
            disk_image = getattr(self, f"_hd{drive}_disk_image")
            if not disk_image:
                continue
            try:
                if self.linked_clone:
                    disk = os.path.join(self.working_dir, f"hd{drive}_disk.qcow2")
                else:
                    disk = disk_image
                if not os.path.exists(disk):
                    continue
                output = await subprocess_check_output(qemu_img_path, "info", "--output=json", disk)
                if output:
                    try:
                        json_data = json.loads(output)
                    except ValueError as e:
                        raise QemuError(
                            f"Invalid JSON data returned by qemu-img while looking for the Qemu VM saved state snapshot: {e}"
                        )
                    if "snapshots" in json_data:
                        for snapshot in json_data["snapshots"]:
                            if snapshot["name"] == snapshot_name:
                                # delete the snapshot
                                command = [qemu_img_path, "snapshot", "-d", snapshot_name, disk]
                                retcode = await self._qemu_img_exec(command)
                                if retcode:
                                    stdout = self.read_qemu_img_stdout()
                                    log.warning(f"Could not delete saved VM state from disk {disk}: {stdout}")
                                else:
                                    log.info(f"Deleted saved VM state from disk {disk}")
            except subprocess.SubprocessError as e:
                raise QemuError(f"Error while looking for the Qemu VM saved state snapshot: {e}")

    async def _saved_state_option(self, snapshot_name="GNS3_SAVED_STATE"):

        drives = ["a", "b", "c", "d"]
        qemu_img_path = self._get_qemu_img()
        for disk_index, drive in enumerate(drives):
            disk_image = getattr(self, f"_hd{drive}_disk_image")
            if not disk_image:
                continue
            try:
                if self.linked_clone:
                    disk = os.path.join(self.working_dir, f"hd{drive}_disk.qcow2")
                else:
                    disk = disk_image
                if not os.path.exists(disk):
                    continue
                output = await subprocess_check_output(qemu_img_path, "info", "--output=json", disk)
                if output:
                    try:
                        json_data = json.loads(output)
                    except ValueError as e:
                        raise QemuError(
                            f"Invalid JSON data returned by qemu-img while looking for the Qemu VM saved state snapshot: {e}"
                        )
                    if "snapshots" in json_data:
                        for snapshot in json_data["snapshots"]:
                            if snapshot["name"] == snapshot_name:
                                log.info(
                                    'QEMU VM "{name}" [{id}] VM saved state detected (snapshot name: {snapshot})'.format(
                                        name=self._name, id=self.id, snapshot=snapshot_name
                                    )
                                )
                                return ["-loadvm", snapshot_name.replace(",", ",,")]

            except subprocess.SubprocessError as e:
                raise QemuError(f"Error while looking for the Qemu VM saved state snapshot: {e}")
        return []

    async def _build_command(self):
        """
        Command to start the QEMU process.
        (to be passed to subprocess.Popen())
        """

        self._qemu_version = await self.manager.get_qemu_version(self.qemu_path)
        vm_name = self._name.replace(",", ",,")
        project_path = self.project.path.replace(",", ",,")
        additional_options = self._options.strip()
        additional_options = additional_options.replace("%vm-name%", '"' + vm_name.replace('"', '\\"') + '"')
        additional_options = additional_options.replace("%vm-id%", self._id)
        additional_options = additional_options.replace("%project-id%", self.project.id)
        additional_options = additional_options.replace("%project-path%", '"' + project_path.replace('"', '\\"') + '"')
        additional_options = additional_options.replace("%guest-cid%", str(self._guest_cid))
        if self._console_type != "none" and self._console:
            additional_options = additional_options.replace("%console-port%", str(self._console))
        command = [self.qemu_path]
        command.extend(["-name", vm_name])
        command.extend(["-m", f"{self._ram}M"])
        # set the maximum number of the hotpluggable CPUs to match the number of CPUs to avoid issues.
        maxcpus = self._maxcpus
        if self._cpus > maxcpus:
            maxcpus = self._cpus
        command.extend(["-smp", f"cpus={self._cpus},maxcpus={maxcpus},sockets=1"])
        if await self._run_with_hardware_acceleration(self.qemu_path, self._options):
            if sys.platform.startswith("linux"):
                command.extend(["-enable-kvm"])
                # Issue on some combo Intel CPU + KVM + Qemu 2.4.0
                # https://github.com/GNS3/gns3-server/issues/685
                if self._qemu_version and parse_version(self._qemu_version) >= parse_version("2.4.0") and self.platform == "x86_64":
                    command.extend(["-machine", "smm=off"])
            elif sys.platform.startswith("darwin"):
                command.extend(["-enable-hax"])
        command.extend(["-boot", f"order={self._boot_priority}"])
        command.extend(self._bios_option())
        command.extend(self._cdrom_option())
        command.extend(await self._disk_options())
        command.extend(self._linux_boot_options())
        if "-uuid" not in additional_options:
            command.extend(["-uuid", self._id])
        command.extend(self._console_options())
        command.extend(self._aux_options())
        command.extend(self._monitor_options())
        command.extend(await self._network_options())
        if self.on_close != "save_vm_state":
            await self._clear_save_vm_stated()
        else:
            command.extend(await self._saved_state_option())
        if self._console_type == "telnet":
            command.extend(await self._disable_graphics())
        if self._tpm:
            command.extend(self._tpm_options())
        if additional_options:
            try:
                command.extend(shlex.split(additional_options))
            except ValueError as e:
                raise QemuError(f"Invalid additional options: {additional_options} error {e}")
        # avoiding mouse offset (see https://github.com/GNS3/gns3-server/issues/2335)
        if self._console_type == "vnc":
            command.extend(['-machine', 'usb=on', '-device', 'usb-tablet'])
        return command

    def asdict(self):
        answer = {"project_id": self.project.id, "node_id": self.id, "node_directory": self.working_path}
        # Qemu has a long list of options. The JSON schema is the single source of information
        for field in Qemu.model_json_schema()["properties"]:
            if field not in answer:
                try:
                    answer[field] = getattr(self, field)
                except AttributeError:
                    pass

        for drive in ["a", "b", "c", "d"]:
            disk_image = getattr(self, f"_hd{drive}_disk_image")
            if not disk_image:
                continue
            answer[f"hd{drive}_disk_image"] = self.manager.get_relative_image_path(disk_image, self.working_dir)
            answer[f"hd{drive}_disk_image_md5sum"] = md5sum(disk_image, self.working_dir)

            local_disk = os.path.join(self.working_dir, f"hd{drive}_disk.qcow2")
            if os.path.exists(local_disk):
                try:
                    qcow2 = Qcow2(local_disk)
                    if qcow2.backing_file:
                        answer[f"hd{drive}_disk_image_backed"] = os.path.basename(local_disk)
                except (Qcow2Error, OSError) as e:
                    log.error(f"Could not read qcow2 disk image '{local_disk}': {e}")
                    continue

        answer["cdrom_image"] = self.manager.get_relative_image_path(self._cdrom_image, self.working_dir)
        answer["cdrom_image_md5sum"] = md5sum(self._cdrom_image, self.working_dir)
        answer["bios_image"] = self.manager.get_relative_image_path(self._bios_image, self.working_dir)
        answer["bios_image_md5sum"] = md5sum(self._bios_image, self.working_dir)
        answer["initrd"] = self.manager.get_relative_image_path(self._initrd, self.working_dir)
        answer["initrd_md5sum"] = md5sum(self._initrd, self.working_dir)
        answer["kernel_image"] = self.manager.get_relative_image_path(self._kernel_image, self.working_dir)
        answer["kernel_image_md5sum"] = md5sum(self._kernel_image, self.working_dir)
        return answer
