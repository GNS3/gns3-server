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
import os
import shutil
import tempfile
import re
import time
import socket
import subprocess

from .pipe_proxy import PipeProxy
from .virtualbox_error import VirtualBoxError
from .adapters.ethernet_adapter import EthernetAdapter
from ..attic import find_unused_port

if sys.platform.startswith('win'):
    import msvcrt
    import win32file

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

        # Telnet to pipe mini-server
        self._serial_pipe_thread = None
        self._serial_pipe = None

        # VirtualBox API variables
        self._machine = None
        self._session = None
        self._vboxmanager = vboxmanager
        self._maximum_adapters = 0

        # VirtualBox settings
        self._console = console
        self._ethernet_adapters = []
        self._headless = False
        self._vmname = vmname
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
            self._vboxwrapper.send('vbox setattr "{}" console_support True'.format(self._name))
            self._vboxwrapper.send('vbox setattr "{}" console_telnet_server True'.format(self._name))
        else:
            try:
                self._machine = self._vboxmanager.vbox.findMachine(self._vmname)
            except Exception as e:
                raise VirtualBoxError("VirtualBox error: {}".format(e))

            # The maximum support network cards depends on the Chipset (PIIX3 or ICH9)
            self._maximum_adapters = self._vboxmanager.vbox.systemProperties.getMaxNetworkAdapters(self._machine.chipsetType)

        self.adapters = 2

        log.info("VirtualBox VM {name} [id={id}] has been created".format(name=self._name,
                                                                          id=self._id))

    def defaults(self):
        """
        Returns all the default attribute values for this VirtualBox VM.

        :returns: default values (dictionary)
        """

        vbox_defaults = {"name": self._name,
                         "vmname": self._vmname,
                         "adapters": len(self._ethernet_adapters),
                         "adapter_type": "Automatic",
                         "console": self._console,
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
            log.info("VirtualBox VM {name} [id={id}] has enabled the headless mode".format(name=self._name, id=self._id))
        else:
            if self._vboxwrapper:
                self._vboxwrapper.send('vbox setattr "{}" headless_mode False'.format(self._name))
            log.info("VirtualBox VM {name} [id={id}] has disabled the headless mode".format(name=self._name, id=self._id))
        self._headless = headless

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
            try:
                self._machine = self._vboxmanager.vbox.findMachine(vmname)
            except Exception as e:
                raise VirtualBoxError("VirtualBox error: {}".format(e))

            # The maximum support network cards depends on the Chipset (PIIX3 or ICH9)
            self._maximum_adapters = self._vboxmanager.vbox.systemProperties.getMaxNetworkAdapters(self._machine.chipsetType)

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
        for _ in range(0, adapters):
            self._ethernet_adapters.append(EthernetAdapter())

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox setattr "{}" nics {}'.format(self._name, len(self._ethernet_adapters)))

        log.info("VirtualBox VM {name} [id={id}]: number of Ethernet adapters changed to {adapters}".format(name=self._name,
                                                                                                            id=self._id,
                                                                                                            adapters=len(self._ethernet_adapters)))

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

        log.info("VirtualBox VM {name} [id={id}]: adapter type changed to {adapter_type}".format(name=self._name,
                                                                                                 id=self._id,
                                                                                                 adapter_type=adapter_type))

    def start(self):
        """
        Starts this VirtualBox VM.
        """

        if self._vboxwrapper:
            status = int(self._vboxwrapper.send('vbox status "{}"'.format(self._name))[0])
            if status == 6:  # paused
                self.resume()
                return
            self._vboxwrapper.send('vbox start "{}"'.format(self._name))
        else:

            if self._machine.state == self._vboxmanager.constants.MachineState_Paused:
                self.resume()
                return

            self._get_session()
            self._set_network_options()
            self._set_console_options()

            progress = self._launch_vm_process()
            log.info("VM is starting with {}% completed".format(progress.percent))
            if progress.percent != 100:
                # This will happen if you attempt to start VirtualBox with unloaded "vboxdrv" module.
                # or have too little RAM or damaged vHDD, or connected to non-existent network.
                # We must unlock machine, otherwise it locks the VirtualBox Manager GUI. (on Linux hosts)
                self._unlock_machine()
                raise VirtualBoxError("Unable to start the VM (failed at {}%)".format(progress.percent))

            try:
                self._machine.setGuestPropertyValue("NameInGNS3", self._name)
            except Exception:
                pass

            # starts the Telnet to pipe thread
            pipe_name = self._get_pipe_name()
            if sys.platform.startswith('win'):
                try:
                    self._serial_pipe = open(pipe_name, "a+b")
                except OSError as e:
                    raise VirtualBoxError("Could not open the pipe {}: {}".format(pipe_name, e))
                self._serial_pipe_thread = PipeProxy(self._vmname, msvcrt.get_osfhandle(self._serial_pipe.fileno()), self._host, self._console)
                #self._serial_pipe_thread.setDaemon(True)
                self._serial_pipe_thread.start()
            else:
                try:
                    self._serial_pipe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self._serial_pipe.connect(pipe_name)
                except OSError as e:
                    raise VirtualBoxError("Could not connect to the pipe {}: {}".format(pipe_name, e))
                self._serial_pipe_thread = PipeProxy(self._vmname, self._serial_pipe, self._host, self._console)
                #self._serial_pipe_thread.setDaemon(True)
                self._serial_pipe_thread.start()

    def stop(self):
        """
        Stops this VirtualBox VM.
        """

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox stop "{}"'.format(self._name))
        else:

            if self._serial_pipe_thread:
                self._serial_pipe_thread.stop()
                self._serial_pipe_thread.join(1)
                if self._serial_pipe_thread.isAlive():
                    log.warn("Serial pire thread is still alive!")
                self._serial_pipe_thread = None

            if self._serial_pipe:
                if sys.platform.startswith('win'):
                    win32file.CloseHandle(msvcrt.get_osfhandle(self._serial_pipe.fileno()))
                else:
                    self._serial_pipe.close()
                self._serial_pipe = None

            try:
                if sys.platform.startswith('win') and "VBOX_INSTALL_PATH" in os.environ:
                    # work around VirtualBox bug #9239
                    vboxmanage_path = os.path.join(os.environ["VBOX_INSTALL_PATH"], "VBoxManage.exe")
                    command = '"{}" controlvm "{}" poweroff'.format(vboxmanage_path, self._vmname)
                    subprocess.call(command, timeout=3)
                else:
                    progress = self._session.console.powerDown()
                    # wait for VM to actually go down
                    progress.waitForCompletion(3000)
                    log.info("VM is stopping with {}% completed".format(self.vmname, progress.percent))

                self._lock_machine()
                for adapter_id in range(0, len(self._ethernet_adapters)):
                    self._disable_adapter(adapter_id, disable=True)
                self._session.machine.saveSettings()
                self._unlock_machine()
            except Exception as e:
                # Do not crash "vboxwrapper", if stopping VM fails.
                # But return True anyway, so VM state in GNS3 can become "stopped"
                # This can happen, if user manually kills VBox VM.
                log.warn("could not stop VM for {}: {}".format(self._vmname, e))
                return

    def suspend(self):
        """
        Suspends this VirtualBox VM.
        """

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox suspend "{}"'.format(self._name))
        else:
            try:
                self._session.console.pause()
            except Exception as e:
                raise VirtualBoxError("VirtualBox error: {}".format(e))

    def reload(self):
        """
        Reloads this VirtualBox VM.
        """

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox reset "{}"'.format(self._name))
        else:
            try:
                progress = self._session.console.reset()
                progress.waitForCompletion(-1)
            except Exception as e:
                raise VirtualBoxError("VirtualBox error: {}".format(e))

    def resume(self):
        """
        Resumes this VirtualBox VM.
        """

        if self._vboxwrapper:
            self._vboxwrapper.send('vbox resume "{}"'.format(self._name))
        else:
            try:
                self._session.console.resume()
            except Exception as e:
                raise VirtualBoxError("VirtualBox error: {}".format(e))

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
            self._create_udp(adapter_id, nio.lport, nio.rhost, nio.rport)

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
            self._delete_udp(adapter_id)

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

    def _get_session(self):

        log.debug("getting session for {}".format(self._vmname))
        try:
            self._session = self._vboxmanager.mgr.getSessionObject(self._vboxmanager.vbox)
        except Exception as e:
            # fails on heavily loaded hosts...
            raise VirtualBoxError("VirtualBox error: {}".format(e))

    def _set_network_options(self):

        log.debug("setting network options for {}".format(self._vmname))

        self._lock_machine()

        first_adapter_type = self._vboxmanager.constants.NetworkAdapterType_I82540EM
        try:
            first_adapter = self._session.machine.getNetworkAdapter(0)
            first_adapter_type = first_adapter.adapterType
        except Exception as e:
            pass
            #raise VirtualBoxError("VirtualBox error: {}".format(e))

        for adapter_id in range(0, len(self._ethernet_adapters)):
            try:
                # VirtualBox starts counting from 0
                adapter = self._session.machine.getNetworkAdapter(adapter_id)
                adapter_type = adapter.adapterType

                if self._adapter_type == "PCnet-PCI II (Am79C970A)":
                    adapter_type = self._vboxmanager.constants.NetworkAdapterType_Am79C970A
                if self._adapter_type == "PCNet-FAST III (Am79C973)":
                    adapter_type = self._vboxmanager.constants.NetworkAdapterType_Am79C973
                if self._adapter_type == "Intel PRO/1000 MT Desktop (82540EM)":
                    adapter_type = self._vboxmanager.constants.NetworkAdapterType_I82540EM
                if self._adapter_type == "Intel PRO/1000 T Server (82543GC)":
                    adapter_type = self._vboxmanager.constants.NetworkAdapterType_I82543GC
                if self._adapter_type == "Intel PRO/1000 MT Server (82545EM)":
                    adapter_type = self._vboxmanager.constants.NetworkAdapterType_I82545EM
                if self._adapter_type == "Paravirtualized Network (virtio-net)":
                    adapter_type = self._vboxmanager.constants.NetworkAdapterType_Virtio
                if self._adapter_type == "Automatic":  # "Auto-guess, based on first NIC"
                    adapter_type = first_adapter_type

                adapter.adapterType = adapter_type

            except Exception as e:
                raise VirtualBoxError("VirtualBox error: {}".format(e))

            nio = self._ethernet_adapters[adapter_id].get_nio(0)
            if nio:
                log.debug("setting UDP params on adapter {}".format(adapter_id))
                try:
                    adapter.enabled = True
                    adapter.cableConnected = True
                    adapter.traceEnabled = False
                    # Temporary hack around VBox-UDP patch limitation: inability to use DNS
                    if nio.rhost == 'localhost':
                        rhost = '127.0.0.1'
                    else:
                        rhost = nio.rhost
                    adapter.attachmentType = self._vboxmanager.constants.NetworkAttachmentType_Generic
                    adapter.genericDriver = "UDPTunnel"
                    adapter.setProperty("sport", str(nio.lport))
                    adapter.setProperty("dest", rhost)
                    adapter.setProperty("dport", str(nio.rport))
                except Exception as e:
                    # usually due to COM Error: "The object is not ready"
                    raise VirtualBoxError("VirtualBox error: {}".format(e))

                if nio.capturing:
                    self._enable_capture(adapter, nio.pcap_output_file)

            else:
                # shutting down unused adapters...
                try:
                    adapter.enabled = True
                    adapter.attachmentType = self._vboxmanager.constants.NetworkAttachmentType_Null
                    adapter.cableConnected = False
                except Exception as e:
                    raise VirtualBoxError("VirtualBox error: {}".format(e))

        #for adapter_id in range(len(self._ethernet_adapters), self._maximum_adapters):
        #    log.debug("disabling remaining adapter {}".format(adapter_id))
        #    self._disable_adapter(adapter_id)

        try:
            self._session.machine.saveSettings()
        except Exception as e:
            raise VirtualBoxError("VirtualBox error: {}".format(e))

        self._unlock_machine()

    def _disable_adapter(self, adapter_id, disable=True):

        log.debug("disabling network adapter for {}".format(self._vmname))
        # this command is retried several times, because it fails more often...
        retries = 6
        last_exception = None
        for retry in range(retries):
            if retry == (retries - 1):
                raise VirtualBoxError("Could not disable network adapter after 4 retries: {}".format(last_exception))
            try:
                adapter = self._session.machine.getNetworkAdapter(adapter_id)
                adapter.traceEnabled = False
                adapter.attachmentType = self._vboxmanager.constants.NetworkAttachmentType_Null
                if disable:
                    adapter.enabled = False
                break
            except Exception as e:
                # usually due to COM Error: "The object is not ready"
                log.warn("cannot disable network adapter for {}, retrying {}: {}".format(self._vmname, retry + 1, e))
                last_exception = e
                time.sleep(1)
                continue

    def _enable_capture(self, adapter, output_file):

        log.debug("enabling capture for {}".format(self._vmname))
        # this command is retried several times, because it fails more often...
        retries = 4
        last_exception = None
        for retry in range(retries):
            if retry == (retries - 1):
                raise VirtualBoxError("Could not enable packet capture after 4 retries: {}".format(last_exception))
            try:
                adapter.traceEnabled = True
                adapter.traceFile = output_file
                break
            except Exception as e:
                log.warn("cannot enable packet capture for {}, retrying {}: {}".format(self._vmname, retry + 1, e))
                last_exception = e
                time.sleep(0.75)
                continue

    def _create_udp(self, adapter_id, sport, daddr, dport):

        if self._machine.state >= self._vboxmanager.constants.MachineState_FirstOnline and \
                self._machine.state <= self._vboxmanager.constants.MachineState_LastOnline:
            # the machine is being executed
            retries = 4
            last_exception = None
            for retry in range(retries):
                if retry == (retries - 1):
                    raise VirtualBoxError("Could not create an UDP tunnel after 4 retries :{}".format(last_exception))
                try:
                    adapter = self._session.machine.getNetworkAdapter(adapter_id)
                    adapter.cableConnected = True
                    adapter.attachmentType = self._vboxmanager.constants.NetworkAttachmentType_Null
                    self._session.machine.saveSettings()
                    adapter.attachmentType = self._vboxmanager.constants.NetworkAttachmentType_Generic
                    adapter.genericDriver = "UDPTunnel"
                    adapter.setProperty("sport", str(sport))
                    adapter.setProperty("dest", daddr)
                    adapter.setProperty("dport", str(dport))
                    self._session.machine.saveSettings()
                    break
                except Exception as e:
                    # usually due to COM Error: "The object is not ready"
                    log.warn("cannot create UDP tunnel for {}: {}".format(self._vmname, e))
                    last_exception = e
                    time.sleep(0.75)
                    continue

    def _delete_udp(self, adapter_id):

        if self._machine.state >= self._vboxmanager.constants.MachineState_FirstOnline and \
                self._machine.state <= self._vboxmanager.constants.MachineState_LastOnline:
            # the machine is being executed
            retries = 4
            last_exception = None
            for retry in range(retries):
                if retry == (retries - 1):
                    raise VirtualBoxError("Could not delete an UDP tunnel after 4 retries :{}".format(last_exception))
                try:
                    adapter = self._session.machine.getNetworkAdapter(adapter_id)
                    adapter.attachmentType = self._vboxmanager.constants.NetworkAttachmentType_Null
                    adapter.cableConnected = False
                    self._session.machine.saveSettings()
                    break
                except Exception as e:
                    # usually due to COM Error: "The object is not ready"
                    log.debug("cannot delete UDP tunnel for {}: {}".format(self._vmname, e))
                    last_exception = e
                    time.sleep(0.75)
                    continue

    def _get_pipe_name(self):

        p = re.compile('\s+', re.UNICODE)
        pipe_name = p.sub("_", self._vmname)
        if sys.platform.startswith('win'):
            pipe_name = r"\\.\pipe\VBOX\{}".format(pipe_name)
        else:
            pipe_name = os.path.join(tempfile.gettempdir(), "pipe_{}".format(pipe_name))
        return pipe_name

    def _set_console_options(self):

        log.info("setting console options for {}".format(self.vmname))

        self._lock_machine()
        pipe_name = self._get_pipe_name()

        try:
            serial_port = self._session.machine.getSerialPort(0)
            serial_port.enabled = True
            serial_port.path = pipe_name
            serial_port.hostMode = 1
            serial_port.server = True
            self._session.machine.saveSettings()
        except Exception as e:
            raise VirtualBoxError("VirtualBox error: {}".format(e))

        self._unlock_machine()

    def _launch_vm_process(self):

        log.debug("launching VM {}".format(self._vmname))
        # this command is retried several times, because it fails more often...
        retries = 4
        last_exception = None
        for retry in range(retries):
            if retry == (retries - 1):
                raise VirtualBoxError("Could not launch the VM after 4 retries: {}".format(last_exception))
            try:
                if self._headless:
                    mode = "headless"
                else:
                    mode = "gui"
                log.info("starting {} in {} mode".format(self._vmname, mode))
                progress = self._machine.launchVMProcess(self._session, mode, "")
                break
            except Exception as e:
                # This will usually happen if you try to start the same VM twice,
                # but may happen on loaded hosts too...
                log.warn("cannot launch VM {}, retrying {}: {}".format(self._vmname, retry + 1, e))
                last_exception = e
                time.sleep(0.6)
                continue

        try:
            progress.waitForCompletion(-1)
        except Exception as e:
            raise VirtualBoxError("VirtualBox error: {}".format(e))

        return progress

    def _lock_machine(self):

        log.debug("locking machine for {}".format(self._vmname))
        # this command is retried several times, because it fails more often...
        retries = 4
        last_exception = None
        for retry in range(retries):
            if retry == (retries - 1):
                raise VirtualBoxError("Could not lock the machine after 4 retries: {}".format(last_exception))
            try:
                self._machine.lockMachine(self._session, 1)
                break
            except Exception as e:
                log.warn("cannot lock the machine for {}, retrying {}: {}".format(self._vmname, retry + 1, e))
                last_exception = e
                time.sleep(1)
                continue

    def _unlock_machine(self):

        log.debug("unlocking machine for {}".format(self._vmname))
        # this command is retried several times, because it fails more often...
        retries = 4
        last_exception = None
        for retry in range(retries):
            if retry == (retries - 1):
                raise VirtualBoxError("Could not unlock the machine after 4 retries: {}".format(last_exception))
            try:
                self._session.unlockMachine()
                break
            except Exception as e:
                log.warn("cannot unlock the machine for {}, retrying {}: {}".format(self._vmname, retry + 1, e))
                time.sleep(1)
                last_exception = e
                continue
