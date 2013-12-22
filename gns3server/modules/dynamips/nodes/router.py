# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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
Interface for Dynamips virtual Machine module ("vm")
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L77
"""

from __future__ import unicode_literals
from ..dynamips_error import DynamipsError
import os


class Router(object):
    """
    Dynamips router

    :param hypervisor: Dynamips hypervisor object
    :param name: name for this router
    :param platform: c7200, c3745, c3725, c3600, c2691, c2600 or c1700
    :param console_flag: create console ports if True.
    """

    _instance_count = 0
    _status = {0: "inactive",
               1: "shutting down",
               2: "running",
               3: "suspended"}

    def __init__(self, hypervisor, name, platform="c7200", console_flag=True):

        # create an unique ID
        self._id = Router._instance_count
        Router._instance_count += 1

        self._hypervisor = hypervisor
        self._name = '"' + name + '"'  # put name into quotes to protect spaces
        self._platform = platform
        self._image = ""
        self._ram = 128  # Megabytes
        self._nvram = 128  # Kilobytes
        self._mmap = True
        self._sparsemem = True
        self._clock_divisor = 8
        self._idlepc = ""
        self._idlemax = 1500
        self._idlesleep = 30
        self._ghost_file = ""
        self._ghost_status = 0
        self._exec_area = None  # Megabytes (None = default for the router platform)
        self._jit_sharing_group = None
        self._disk0 = 0  # Megabytes
        self._disk1 = 0  # Megabytes
        self._confreg = '0x2102'
        self._console = None
        self._aux = None
        self._mac_addr = None
        self._system_id = None  # processor board ID in IOS
        self._slots = []

        self._hypervisor.send("vm create {name} {id} {platform}".format(name=self._name,
                                                                        id=self._id,
                                                                        platform=self._platform))

        if console_flag:
            self.console = self._hypervisor.baseconsole + self._id
            self.aux = self._hypervisor.baseaux + self._id

        self._hypervisor.devices.append(self)

    @property
    def id(self):
        """
        Returns the unique ID for this router.

        :returns: id (integer)
        """

        return self._id

    @property
    def name(self):
        """
        Returns the name of this router.

        :returns: name (string)
        """

        return self._name[1:-1]  # remove quotes

    @property
    def platform(self):
        """
        Returns the platform of this router.

        :returns: platform name (string):
        c7200, c3745, c3725, c3600, c2691, c2600 or c1700
        """

        return self._platform

    @property
    def hypervisor(self):
        """
        Returns the current hypervisor.

        :returns: hypervisor object
        """

        return self._hypervisor

    def list(self):
        """
        Returns all VM instances

        :returns: list of all VM instances
        """

        return self._hypervisor.send("vm list")

    def list_con_ports(self):
        """
        Returns all VM console TCP ports

        :returns: list of port numbers
        """

        return self._hypervisor.send("vm list_con_ports")

    def rename(self, new_name):
        """
        Renames this router.

        :param new_name: new name string
        """

        new_name = '"' + new_name + '"'  # put the new name into quotes to protect spaces
        self._hypervisor.send("vm rename {name} {new_name}".format(name=self._name,
                                                                   new_name=new_name))
        self._name = new_name

    def delete(self):
        """
        Deletes this router.
        """

        self._hypervisor.send("vm delete {}".format(self._name))
        self._hypervisor.devices.remove(self)

    def start(self):
        """
        Starts this router.
        At least the IOS image must be set.
        """

        self._hypervisor.send("vm start {}".format(self._name))

    def stop(self):
        """
        Stops this router.
        The settings are kept.
        """

        self._hypervisor.send("vm stop {}".format(self._name))

    def suspend(self):
        """
        Suspends this router
        """

        self._hypervisor.send("vm suspend {}".format(self._name))

    def resume(self):
        """
        Resumes this suspended router
        """

        self._hypervisor.send("vm resume {}".format(self._name))

    def get_status(self):
        """
        Returns the status of this router

        :returns: 0=inactive, 1=shutting down, 2=running, 3=suspended
        """

        status_id = int(self._hypervisor.send("vm get_status {}".format(self._name))[0])
        return self._status[status_id]

    def is_running(self):
        """
        Checks if this router is running.

        :returns: True if running, False otherwise
        """

        if self.get_status() == "running":
            return True
        return False

    @property
    def jit_sharing_group(self):
        """
        Returns the JIT sharing group for this router.

        :returns: translation sharing group ID
        """

        return self._jit_sharing_group

    @jit_sharing_group.setter
    def jit_sharing_group(self, group_id):
        """
        Set the translation sharing group (unstable).

        :param group_id: translation sharing group ID
        """

        if not self._image:
            raise DynamipsError("Register an IOS image fist")

        self._hypervisor.send("vm set_tsg {name} {group_id}".format(name=self._name,
                                                                    group_id=group_id))

        self._jit_sharing_group = group_id
        self._hypervisor.add_jitsharing_group(os.path.basename(self._image), group_id)

    def set_debug_level(self, level):
        """
        Set the debug level for this router (default is 0).

        :param level: level number
        """

        self._hypervisor.send("vm set_debug_level {name} {level}".format(name=self._name,
                                                                         level=level))

    @property
    def image(self):
        """
        Returns this IOS image for this router.

        :returns: path to IOS image file
        """

        return self._image

    @image.setter
    def image(self, image):
        """
        Set the IOS image for this router.
        There is no default.

        :param image: path to IOS image file
        """

        # encase image in quotes to protect spaces in the path
        self._hypervisor.send("vm set_ios {name} {image}".format(name=self._name,
                                                                 image='"' + image + '"'))
        self._image = image

    def set_config(self, startup_config, private_config=''):
        """
        Set the config files that are pushed to startup-config and
        private-config in NVRAM when the instance is started.

        :param startup_config: path to statup-config file
        :param private_config: path to private-config file
        (keep existing data when if an empty string)
        """

        self._hypervisor.send("vm set_config {name} {startup} {private}".format(name=self._name,
                                                                                startup='"' + startup_config + '"',
                                                                                private='"' + private_config + '"'))

    def extract_config(self):
        """
        Gets the contents of the config files
        startup-config and private-config from NVRAM.

        :returns: tuple (startup-config, private-config) base64 encoded
        """

        try:
            reply = self._hypervisor.send("vm extract_config {}".format(self._name))[0].rsplit(' ', 2)[-2:]
        except IOError:
            #for some reason Dynamips gets frozen when it does not find the magic number in the NVRAM file.
            return (None, None)
        startup_config = reply[0][1:-1]  # get statup-config and remove single quotes
        private_config = reply[1][1:-1]  # get private-config and remove single quotes
        return (startup_config, private_config)

    def push_config(self, startup_config, private_config='(keep)'):
        """
        Pushes configuration to the config files startup-config and private-config in NVRAM.
        The data is a Base64 encoded string, or '(keep)' to keep existing data.

        :param startup_config: statup-config string base64 encoded
        :param private_config: private-config string base64 encoded
        (keep existing data when if the value is ('keep'))
        """

        self._hypervisor.send("vm push_config {name} {startup} {private}".format(name=self._name,
                                                                                 startup=startup_config,
                                                                                 private=private_config))

    @property
    def ram(self):
        """
        Returns the amount of RAM allocated to this router.

        :returns: amount of RAM in Mbytes (integer)
        """

        return self._ram

    @ram.setter
    def ram(self, ram):
        """
        Set amount of RAM allocated to this router

        :param ram: amount of RAM in Mbytes (integer)
        """

        self._hypervisor.send("vm set_ram {name} {ram}".format(name=self._name,
                                                               ram=self._ram))
        self._hypervisor.decrease_memory_load(self._ram)
        self._ram = ram
        self._hypervisor.increase_memory_load(self._ram)

    @property
    def nvram(self):
        """
        Returns the mount of NVRAM allocated to this router.

        :returns: amount of NVRAM in Kbytes (integer)
        """

        return self._nvram

    @nvram.setter
    def nvram(self, nvram):
        """
        Set amount of NVRAM allocated to this router

        :param nvram: amount of NVRAM in Kbytes (integer)
        """

        self._hypervisor.send("vm set_nvram {name} {nvram}".format(name=self._name,
                                                                   nvram=self._nvram))
        self._nvram = nvram

    @property
    def mmap(self):
        """
        Returns True if a mapped file is used to simulate this router memory.

        :returns: boolean either mmap is activated or not
        """

        return self._mmap

    @mmap.setter
    def mmap(self, mmap):
        """
        Enable/Disable use of a mapped file to simulate router memory.
        By default, a mapped file is used. This is a bit slower, but requires less memory.

        :param mmap: activate/deactivate mmap (boolean)
        """

        if mmap:
            flag = 1
        else:
            flag = 0
        self._hypervisor.send("vm set_ram_mmap {name} {mmap}".format(name=self._name,
                                                                     mmap=flag))
        self._mmap = mmap

    @property
    def sparsemem(self):
        """
        Returns True if sparse memory is used on this router.

        :returns: boolean either mmap is activated or not
        """

        return self._sparsemem

    @sparsemem.setter
    def sparsemem(self, sparsemem):
        """
        Enable/disable use of sparse memory

        :param sparsemem: activate/deactivate sparsemem (boolean)
        """

        if sparsemem:
            flag = 1
        else:
            flag = 0
        self._hypervisor.send("vm set_sparse_mem {name} {sparsemem}".format(name=self._name,
                                                                     sparsemem=flag))
        self._sparsemem = sparsemem

    @property
    def clock_divisor(self):
        """
        Returns the clock divisor value for this router.

        :returns: clock divisor value (integer)
        """

        return self._clock_divisor

    @clock_divisor.setter
    def clock_divisor(self, clock_divisor):
        """
        Set the clock divisor value. The higher is the value, the faster is the clock in the
        virtual machine. The default is 4, but it is often required to adjust it.

        :param clock_divisor: clock divisor value (integer)
        """

        self._hypervisor.send("vm set_clock_divisor {name} {clock}".format(name=self._name,
                                                                           clock=clock_divisor))
        self._clock_divisor = clock_divisor

    @property
    def idlepc(self):
        """
        Returns the idle Pointer Counter (PC).

        :returns: idlepc value (string)
        """

        return self._idlepc

    @idlepc.setter
    def idlepc(self, idlepc):
        """
        Set the idle Pointer Counter (PC)

        :param idlepc: idlepc value (string)
        """

        if not self.is_running():
            # router is not running
            self._hypervisor.send("vm set_idle_pc {name} {idlepc}".format(name=self._name,
                                                                          idlepc=idlepc))
        else:
            self._hypervisor.send("vm set_idle_pc_online {name} 0 {idlepc}".format(name=self._name,
                                                                                   idlepc=idlepc))
        self._idlepc = idlepc

    def get_idle_pc_prop(self):
        """
        Gets the idle PC proposals.
        Takes 1000 measurements and records up to 10 idle PC proposals.
        There is a 10ms wait between each measurement.

        :returns: list of idle PC proposal
        """

        return self._hypervisor.send("vm get_idle_pc_prop {} 0".format(self._name))

    def show_idle_pc_prop(self):
        """
        Dumps the idle PC proposals (previously generated).

        :returns: list of idle PC proposal
        """

        return self._hypervisor.send("vm show_idle_pc_prop {} 0".format(self._name))

    @property
    def idlemax(self):
        """
        Returns CPU idle max value.

        :returns: idle max (integer)
        """

        return self._idlemax

    @idlemax.setter
    def idlemax(self, idlemax):
        """
        Set CPU idle max value

        :param idlemax: idle max value (integer)
        """

        if self.is_running():  # router is running
            self._hypervisor.send("vm set_idle_max {name} 0 {idlemax}".format(name=self._name,
                                                                              idlemax=idlemax))
        self._idlemax = idlemax

    @property
    def idlesleep(self):
        """
        Returns CPU idle sleep time value.

        :returns: idle sleep (integer)
        """

        return self._idlesleep

    @idlesleep.setter
    def idlesleep(self, idlesleep):
        """
        Set CPU idle sleep time value.

        :param idlesleep: idle sleep value (integer)
        """

        if self.is_running():  # router is running
            self._hypervisor.send("vm set_idle_sleep_time {name} 0 {idlesleep}".format(name=self._name,
                                                                                       idlesleep=idlesleep))
        self._idlesleep = idlesleep

    def show_timer_drift(self):
        """
        Shows info about potential timer drift.

        :returns: timer drift info.
        """

        return self._hypervisor.send("vm show_timer_drift {} 0".format(self._name))

    @property
    def ghost_file(self):
        """
        Returns ghost RAM file.

        :returns: path to ghost file
        """

        return self._ghost_file

    @ghost_file.setter
    def ghost_file(self, ghost_file):
        """
        Set ghost RAM file

        :ghost_file: path to ghost file
        """

        self._hypervisor.send("vm set_ghost_file {name} {ghost_file}".format(name=self._name,
                                                                             ghost_file=ghost_file))
        self._ghost_file = ghost_file

        # If this is a ghost instance, track this as a hosted ghost instance by this hypervisor
        if self.ghost_status == 1:
            self._hypervisor.add_ghost(ghost_file, self)

    def formatted_ghost_file(self):
        """
        Returns a properly formatted ghost file name.

        :returns: formatted ghost_file name (string)
        """

        # Replace specials characters in 'drive:\filename' in Linux and Dynamips in MS Windows or viceversa.
        ghost_file = os.path.basename(self._image) + '-' + self._hypervisor.host + '.ghost'
        ghost_file = ghost_file.replace('\\', '-').replace('/', '-').replace(':', '-')
        return ghost_file

    @property
    def ghost_status(self):
        """Returns ghost RAM status

        :returns: ghost status (integer)
        """

        return self._ghost_status

    @ghost_status.setter
    def ghost_status(self, ghost_status):
        """
        Set ghost RAM status

        :param ghost_status: state flag indicating status
        0 => Do not use IOS ghosting
        1 => This is a ghost instance
        2 => Use an existing ghost instance
        """

        self._hypervisor.send("vm set_ghost_status {name} {ghost_status}".format(name=self._name,
                                                                                 ghost_status=ghost_status))
        self._ghost_status = ghost_status

    @property
    def exec_area(self):
        """
        Returns the exec area value.

        :returns: exec area value (integer)
        """

        return self._exec_area

    @exec_area.setter
    def exec_area(self, exec_area):
        """
        Set the exec area value.
        The exec area is a pool of host memory used to store pages
        translated by the JIT (they contain the native code
        corresponding to MIPS code pages).

        :param excec_area: exec area value (integer)
        """

        self._hypervisor.send("vm set_exec_area {name} {exec_area}".format(name=self._name,
                                                                           exec_area=exec_area))
        self._exec_area = exec_area

    @property
    def disk0(self):
        """
        Returns the size (MB) for PCMCIA disk0.

        :returns: disk0 size (integer)
        """

        return self._disk0

    @disk0.setter
    def disk0(self, disk0):
        """
        Set the size (MB) for PCMCIA disk0.

        :param disk0: disk0 size (integer)
        """

        self._hypervisor.send("vm set_disk0 {name} {disk0}".format(name=self._name,
                                                                   disk0=disk0))
        self._disk0 = disk0

    @property
    def disk1(self):
        """
        Returns the size (MB) for PCMCIA disk1.

        :returns: disk1 size (integer)
        """

        return self._disk1

    @disk1.setter
    def disk1(self, disk1):
        """
        Set the size (MB) for PCMCIA disk1.

        :param disk1: disk1 size (integer)
        """

        self._hypervisor.send("vm set_disk1 {name} {disk1}".format(name=self._name,
                                                                   disk1=disk1))
        self._disk1 = disk1

    @property
    def confreg(self):
        """
        Returns the configuration register.
        The default is 0x2102.

        :returns: configuration register value (string)
        """

        return self._confreg

    @confreg.setter
    def confreg(self, confreg):
        """
        Set the configuration register.

        :param confreg: configuration register value (string)
        """

        self._hypervisor.send("vm set_conf_reg {name} {confreg}".format(name=self._name,
                                                                        confreg=confreg))
        self._confreg = confreg

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
        Set the TCP console port.

        :param console: console port (integer)
        """

        if console == self._console:
            return

        self._hypervisor.send("vm set_con_tcp_port {name} {console}".format(name=self._name,
                                                                            console=console))
        self._console = console

    @property
    def aux(self):
        """
        Returns the TCP auxiliary port.

        :returns: console auxiliary port (integer)
        """

        return self._aux

    @aux.setter
    def aux(self, aux):
        """
        Set the TCP auxiliary port.

        :param aux: console auxiliary port (integer)
        """

        if aux == self._aux:
            return

        self._hypervisor.send("vm set_aux_tcp_port {name} {aux}".format(name=self._name,
                                                                        aux=aux))
        self._aux = aux

    def get_cpu_info(self, cpu_id=0):
        """
        Shows info about the CPU identified by cpu_id.
        The boot CPU (which is typically the only CPU) has ID 0.

        :returns: ? (could not test)
        """

        #  FIXME: nothing returned by Dynamips.
        return self._hypervisor.send("vm cpu_info {name} {cpu_id}".format(name=self._name,
                                                                          cpu_id=cpu_id))

    def get_cpu_usage(self, cpu_id=0):
        """
        Shows cpu usage in seconds, "cpu_id" is ignored.

        :returns: cpu usage in seconds
        """

        return int(self._hypervisor.send("vm cpu_usage {name} {cpu_id}".format(name=self._name,
                                                                               cpu_id=cpu_id))[0])

    def send_console_msg(self, message):
        """
        Sends a message to the console.

        :param message: message to send to the console
        """

        self._hypervisor.send("vm send_con_msg {name} {message}".format(name=self._name,
                                                                        message=message))

    def send_aux_msg(self, message):
        """
        Sends a message to the auxiliary console.

        :param message: message to send to the auxiliary console
        """

        self._hypervisor.send("vm send_aux_msg {name} {message}".format(name=self._name,
                                                                        message=message))

    @property
    def mac_addr(self):
        """
        Returns the MAC address.

        :returns: the MAC address (hexadecimal format: hh:hh:hh:hh:hh:hh)
        """

        return self._mac_addr

    @mac_addr.setter
    def mac_addr(self, mac_addr):
        """
        Set the MAC address.

        :param mac_addr: a MAC address (hexadecimal format: hh:hh:hh:hh:hh:hh)
        """

        self._hypervisor.send("{platform} set_mac_addr {name} {mac_addr}".format(platform=self._platform,
                                                                                 name=self._name,
                                                                                 mac_addr=mac_addr))
        self._mac_addr = mac_addr

    @property
    def system_id(self):
        """
        Returns the system ID.

        :returns: the system ID (also called board processor ID)
        """

        return self._system_id

    @system_id.setter
    def system_id(self, system_id):
        """
        Set the system ID.

        :param system_id: a system ID (also called board processor ID)
        """

        self._hypervisor.send("{platform} set_system_id {name} {system_id}".format(platform=self._platform,
                                                                                   name=self._name,
                                                                                   system_id=system_id))
        self._system_id = system_id

    def get_hardware_info(self):
        """
        Get some hardware info about this router.

        :returns: ? (could not test)
        """

        #  FIXME: nothing returned by Dynamips.
        return (self._hypervisor.send("{platform} show_hardware {name}".format(platform=self._platform,
                                                                               name=self._name)))

    def get_slot_bindings(self):
        """
        Returns slot bindings.

        :returns: slot bindings (adapter names) list
        """

        return (self._hypervisor.send("vm slot_bindings {}".format(self._name)))

    def slot_add_binding(self, slot_id, adapter):
        """
        Adds a slot binding.

        :param slot_id: slot ID
        :param adapter: device to add in the corresponding slot (object)
        """

        try:
            slot = self._slots[slot_id]
        except IndexError:
            raise DynamipsError("Slot {slot_id} doesn't exist on router {name}".format(name=self._name,
                                                                                       slot_id=slot_id))

        if slot != None:
            current_adapter = slot
            raise DynamipsError("Slot {slot_id} is already occupied by adapter {adapter} on router {name}".format(name=self._name,
                                                                                                                  slot_id=slot_id,
                                                                                                                  adapter=current_adapter))

        self._hypervisor.send("vm slot_add_binding {name} {slot_id} 0 {adapter}".format(name=self._name,
                                                                                        slot_id=slot_id,
                                                                                        adapter=adapter))
        self._slots[slot_id] = adapter

        # Generate an OIR event if the router is running and
        # only for c7200, c3600 and c3745 (NM-4T only)
        if self.is_running() and self._platform == 'c7200' \
        or (self._platform == 'c3600' and self.chassis == '3660') \
        or (self._platform == 'c3745' and adapter == 'NM-4T'):

            self._hypervisor.send("vm slot_oir_start {name} {slot_id} 0".format(name=self._name,
                                                                                slot_id=slot_id))

    def slot_remove_binding(self, slot_id):
        """
        Removes a slot binding.

        :param slot_id: slot ID
        """

        try:
            slot = self._slots[slot_id]
        except IndexError:
            raise DynamipsError("Slot {slot_id} doesn't exist on router {name}".format(name=self._name,
                                                                                       slot_id=slot_id))

        if slot == None:
            return

        # Generate an OIR event if the router is running and
        # only for c7200, c3600 and c3745 (NM-4T only)
        if self.is_running() and self._platform == 'c7200' \
        or (self._platform == 'c3600' and self.chassis == '3660') \
        or (self._platform == 'c3745' and slot == 'NM-4T'):

            self._hypervisor.send("vm slot_oir_stop {name} {slot_id} 0".format(name=self._name,
                                                                               slot_id=slot_id))

        self._hypervisor.send("vm slot_remove_binding {name} {slot_id} 0".format(name=self._name,
                                                                                     slot_id=slot_id))
        self._slots[slot_id] = None

    def install_wic(self, wic_slot_id, wic):
        """
        Installs a WIC adapter into this router.

        :param wic_slot_id: WIC slot ID
        :param wic: WIC to be install (object)
        """

        # WICs are always installed on adapters in slot 0
        slot_id = 0

        # Do not check if slot has an adapter because adapters with WICs interfaces
        # must be inserted by default in the router and cannot be removed.
        adapter = self._slots[slot_id]

        if wic_slot_id > len(adapter.wics) - 1:
            raise DynamipsError("WIC slot {wic_slot_id} doesn't exist".format(name=self._name,
                                                                              wic_slot_id=wic_slot_id))

        if not adapter.wic_slot_available(wic_slot_id):
            raise DynamipsError("WIC slot {wic_slot_id} is already occupied by another WIC".format(name=self._name,
                                                                                                   wic_slot_id=wic_slot_id))

        # Dynamips WICs slot IDs start on a multiple of 16
        # WIC1 = 16, WIC2 = 32 and WIC3 = 48
        internal_wic_slot_id = 16 * (wic_slot_id + 1)
        self._hypervisor.send("vm slot_add_binding {name} {slot_id} {wic_slot_id} {wic}".format(name=self._name,
                                                                                                slot_id=slot_id,
                                                                                                wic_slot_id=internal_wic_slot_id,
                                                                                                wic=wic))
        adapter.install_wic(wic_slot_id, wic)

    def uninstall_wic(self, wic_slot_id):
        """
        Uninstalls a WIC adapter from this router.

        :param wic_slot_id: WIC slot ID
        """

        # WICs are always installed on adapters in slot 0
        slot_id = 0

        # Do not check if slot has an adapter because adapters with WICs interfaces
        # must be inserted by default in the router and cannot be removed.
        adapter = self._slots[slot_id]

        if wic_slot_id > len(adapter.wics) - 1:
            raise DynamipsError("WIC slot {wic_slot_id} doesn't exist".format(name=self._name,
                                                                              wic_slot_id=wic_slot_id))

        if adapter.wic_slot_available(wic_slot_id):
            raise DynamipsError("No WIC is installed in WIC slot {wic_slot_id}".format(name=self._name,
                                                                                       wic_slot_id=wic_slot_id))
        # Dynamips WICs slot IDs start on a multiple of 16
        # WIC1 = 16, WIC2 = 32 and WIC3 = 48
        internal_wic_slot_id = 16 * (wic_slot_id + 1)
        self._hypervisor.send("vm slot_remove_binding {name} {slot_id} {wic_slot_id}".format(name=self._name,
                                                                                         slot_id=slot_id,
                                                                                         wic_slot_id=internal_wic_slot_id))
        adapter.uninstall_wic(wic_slot_id)

    def get_slot_nio_bindings(self, slot_id):
        """
        Returns slot NIO bindings.

        :param slot_id: slot ID

        :returns: list of NIO bindings
        """

        return (self._hypervisor.send("vm slot_nio_bindings {name} {slot_id}".format(name=self._name,
                                                                                     slot_id=slot_id)))

    def slot_add_nio_binding(self, slot_id, port_id, nio):
        """
        Adds a slot NIO binding.

        :param slot_id: slot ID
        :param port_id: port ID
        :param nio: NIO to add to the slot/port (object)
        """

        try:
            adapter = self._slots[slot_id]
        except IndexError:
            raise DynamipsError("Slot {slot_id} doesn't exist on router {name}".format(name=self._name,
                                                                                       slot_id=slot_id))
        if not adapter.port_exists(port_id):
            raise DynamipsError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=adapter,
                                                                                           port_id=port_id))

        self._hypervisor.send("vm slot_add_nio_binding {name} {slot_id} {port_id} {nio}".format(name=self._name,
                                                                                                slot_id=slot_id,
                                                                                                port_id=port_id,
                                                                                                nio=nio))
        self.slot_enable_nio(slot_id, port_id)
        adapter.add_nio(port_id, nio)

    def slot_remove_nio_binding(self, slot_id, port_id):
        """
        Removes a slot NIO binding.

        :param slot_id: slot ID
        :param port_id: port ID
        """

        try:
            adapter = self._slots[slot_id]
        except IndexError:
            raise DynamipsError("Slot {slot_id} doesn't exist on router {name}".format(name=self._name,
                                                                                       slot_id=slot_id))
        if not adapter.port_exists(port_id):
            raise DynamipsError("Port {port_id} doesn't exist in adapter {adapter}".format(adapter=adapter,
                                                                                           port_id=port_id))

        self.slot_disable_nio(slot_id, port_id)
        self._hypervisor.send("vm slot_remove_binding {name} {slot_id} {port_id}".format(name=self._name,
                                                                                         slot_id=slot_id,
                                                                                         port_id=port_id))

        adapter.remove_nio(port_id)

    def slot_enable_nio(self, slot_id, port_id):
        """
        Enables a slot NIO binding.

        :param slot_id: slot ID
        :param port_id: port ID
        """

        if self.is_running():  # running router
            self._hypervisor.send("vm slot_enable_nio {name} {slot_id} {port_id}".format(name=self._name,
                                                                                         slot_id=slot_id,
                                                                                         port_id=port_id))

    def slot_disable_nio(self, slot_id, port_id):
        """
        Disables a slot NIO binding.

        :param slot_id: slot ID
        :param port_id: port ID
        """

        if self.is_running():  # running router
            self._hypervisor.send("vm slot_disable_nio {name} {slot_id} {port_id}".format(name=self._name,
                                                                                          slot_id=slot_id,
                                                                                          port_id=port_id))

    def _create_slots(self, numslots):
        """
        Creates the appropriate number of slots for this router.

        :param numslots: number of slots to create
        """

        self._slots = numslots * [None]

    @property
    def slots(self):
        """
        Returns the slots for this router.

        :return: slot list
        """

        return self._slots
