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

import os
import shutil

from .virtualbox_error import VirtualBoxError
from .virtualbox_controller import VirtualBoxController
from .adapters.ethernet_adapter import EthernetAdapter
from ..attic import find_unused_port

import logging
log = logging.getLogger(__name__)


class VirtualBoxVM(object):
    """
    VirtualBox VM implementation.

    :param vboxwrapper client: VboxWrapperClient instance
    :param vboxmanager: VirtualBox manager from the VirtualBox API
    :param name: name of this VirtualBox VM
    :param vmname: name of this VirtualBox VM in VirtualBox itself
    :param working_dir: path to a working directory
    :param host: host/address to bind for console and UDP connections
    :param vbox_id: VirtalBox VM instance ID
    :param console: TCP console port
    :param console_start_port_range: TCP console port range start
    :param console_end_port_range: TCP console port range end
    """

    _instances = []
    _allocated_console_ports = []

    def __init__(self,
                 vboxwrapper,
                 vboxmanager,
                 name,
                 vmname,
                 working_dir,
                 host="127.0.0.1",
                 vbox_id=None,
                 console=None,
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
        self._working_dir = None
        self._host = host
        self._command = []
        self._vboxwrapper = vboxwrapper
        self._started = False
        self._console_start_port_range = console_start_port_range
        self._console_end_port_range = console_end_port_range

        # VirtualBox settings
        self._console = console
        self._ethernet_adapters = []
        self._headless = False
        self._enable_console = True
        self._vmname = vmname
        self._adapter_start_index = 0
        self._adapter_type = "Automatic"

        working_dir_path = os.path.join(working_dir, "vbox", "vm-{}".format(self._id))

        if vbox_id and not os.path.isdir(working_dir_path):
            raise VirtualBoxError("Working directory {} doesn't exist".format(working_dir_path))

        # create the device own working directory
        self.working_dir = working_dir_path

        if not self._console:
            # allocate a console port
            try:
                self._console = find_unused_port(self._console_start_port_range,
                                                 self._console_end_port_range,
                                                 self._host,
                                                 ignore_ports=self._allocated_console_ports)
            except Exception as e:
                raise VirtualBoxError(e)

        if self._console in self._allocated_console_ports:
            raise VirtualBoxError("Console port {} is already used by another VirtualBox VM".format(console))
        self._allocated_console_ports.append(self._console)

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox create vbox "{}"'.format(self._name))
            self._vboxwrapper.send('vbox setattr "{}" image "{}"'.format(self._name, vmname))
            self._vboxwrapper.send('vbox setattr "{}" console {}'.format(self._name, self._console))
        else:
            self._vboxcontroller = VirtualBoxController(self._vmname, vboxmanager, self._host)
            self._vboxcontroller.console = self._console

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
                         "adapter_type": "Automatic",
                         "console": self._console,
                         "enable_console": self._enable_console,
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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox rename "{}" "{}"'.format(self._name, new_name))
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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox setattr "{}" console {}'.format(self._name, self._console))
        else:
            self._vboxcontroller.console = console

        log.info("VirtualBox VM {name} [id={id}]: console port set to {port}".format(name=self._name,
                                                                                     id=self._id,
                                                                                     port=console))

    def delete(self):
        """
        Deletes this VirtualBox VM.
        """

        self.stop()
        if self._id in self._instances:
            self._instances.remove(self._id)

        if self.console and self.console in self._allocated_console_ports:
            self._allocated_console_ports.remove(self.console)

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox delete "{}"'.format(self._name))

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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox delete "{}"'.format(self._name))

        try:
            shutil.rmtree(self._working_dir)
        except OSError as e:
            log.error("could not delete VirtualBox VM {name} [id={id}]: {error}".format(name=self._name,
                                                                                        id=self._id,
                                                                                        error=e))
            return

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
            if self._vboxwrapper:
                self._vboxwrapper.send('vbox setattr "{}" headless_mode True'.format(self._name))
            else:
                self._vboxcontroller.headless = True
            log.info("VirtualBox VM {name} [id={id}] has enabled the headless mode".format(name=self._name, id=self._id))
        else:
            if self._vboxwrapper:
                self._vboxwrapper.send('vbox setattr "{}" headless_mode False'.format(self._name))
            else:
                self._vboxcontroller.headless = False
            log.info("VirtualBox VM {name} [id={id}] has disabled the headless mode".format(name=self._name, id=self._id))
        self._headless = headless

    @property
    def enable_console(self):
        """
        Returns either the console is enabled or not

        :returns: boolean
        """

        return self._enable_console

    @enable_console.setter
    def enable_console(self, enable_console):
        """
        Sets either the console is enabled or not

        :param enable_console: boolean
        """

        if enable_console:
            if self._vboxwrapper:
                self._vboxwrapper.send('vbox setattr "{}" enable_console True'.format(self._name))
            else:
                self._vboxcontroller.enable_console = True
            log.info("VirtualBox VM {name} [id={id}] has enabled the console".format(name=self._name, id=self._id))
        else:
            if self._vboxwrapper:
                self._vboxwrapper.send('vbox setattr "{}" enable_console False'.format(self._name))
            else:
                self._vboxcontroller.enable_console = False
            log.info("VirtualBox VM {name} [id={id}] has disabled the console".format(name=self._name, id=self._id))
        self._enable_console = enable_console

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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox setattr "{}" image "{}"'.format(self._name, vmname))
        else:
            self._vboxcontroller.vmname = vmname

        log.info("VirtualBox VM {name} [id={id}] has set the VM name to {vmname}".format(name=self._name, id=self._id, vmname=vmname))
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

        self._ethernet_adapters.clear()
        for adapter_id in range(0, self._adapter_start_index + adapters):
            if adapter_id < self._adapter_start_index:
                self._ethernet_adapters.append(None)
                continue
            self._ethernet_adapters.append(EthernetAdapter())

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox setattr "{}" nics {}'.format(self._name, adapters))
        else:
            self._vboxcontroller.adapters = self._ethernet_adapters

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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox setattr "{}" nic_start_index {}'.format(self._name, adapter_start_index))

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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox setattr "{}" netcard "{}"'.format(self._name, adapter_type))
        else:
            self._vboxcontroller.adapter_type = adapter_type

        log.info("VirtualBox VM {name} [id={id}]: adapter type changed to {adapter_type}".format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 adapter_type=adapter_type))

    def start(self):
        """
        Starts this VirtualBox VM.
        """

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox start "{}"'.format(self._name))
        else:
            self._vboxcontroller.start()

    def stop(self):
        """
        Stops this VirtualBox VM.
        """

        if self._vboxwrapper:
            try:
                self._vboxwrapper.send('vbox stop "{}"'.format(self._name))
            except VirtualBoxError:
                # probably lost the connection
                return
        else:
            self._vboxcontroller.stop()

    def suspend(self):
        """
        Suspends this VirtualBox VM.
        """

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox suspend "{}"'.format(self._name))
        else:
            self._vboxcontroller.suspend()

    def reload(self):
        """
        Reloads this VirtualBox VM.
        """

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox reset "{}"'.format(self._name))
        else:
            self._vboxcontroller.reload()

    def resume(self):
        """
        Resumes this VirtualBox VM.
        """

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox resume "{}"'.format(self._name))
        else:
            self._vboxcontroller.resume()

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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox create_udp "{}" {} {} {} {}'.format(self._name,
                                                                             adapter_id,
                                                                             nio.lport,
                                                                             nio.rhost,
                                                                             nio.rport))
        else:
            self._vboxcontroller.create_udp(adapter_id, nio.lport, nio.rhost, nio.rport)

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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox delete_udp "{}" {}'.format(self._name,
                                                                    adapter_id))
        else:
            self._vboxcontroller.delete_udp(adapter_id)

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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox create_capture "{}" {} "{}"'.format(self._name,
                                                                            adapter_id,
                                                                            output_file))

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

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox delete_capture "{}" {}'.format(self._name,
                                                                        adapter_id))

        log.info("VirtualBox VM {name} [id={id}]: stopping packet capture on adapter {adapter_id}".format(name=self._name,
                                                                                                          id=self._id,
                                                                                                          adapter_id=adapter_id))
