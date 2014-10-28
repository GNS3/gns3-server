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
Controls VirtualBox using the VBox API.
"""

import sys
import os
import tempfile
import re
import time
import socket
import subprocess

if sys.platform.startswith('win'):
    import msvcrt
    import win32file

from .virtualbox_error import VirtualBoxError
from .pipe_proxy import PipeProxy

import logging
log = logging.getLogger(__name__)


class VirtualBoxController(object):

    def __init__(self, vmname, vboxmanager, host):

        self._host = host
        self._machine = None
        self._session = None
        self._vboxmanager = vboxmanager
        self._maximum_adapters = 0
        self._serial_pipe_thread = None
        self._serial_pipe = None

        self._vmname = vmname
        self._console = 0
        self._adapters = []
        self._headless = False
        self._enable_console = False
        self._adapter_type = "Automatic"

        try:
            self._machine = self._vboxmanager.vbox.findMachine(self._vmname)
        except Exception as e:
            raise VirtualBoxError("VirtualBox error: {}".format(e))

        # The maximum support network cards depends on the Chipset (PIIX3 or ICH9)
        self._maximum_adapters = self._vboxmanager.vbox.systemProperties.getMaxNetworkAdapters(self._machine.chipsetType)

    @property
    def vmname(self):

        return self._vmname

    @vmname.setter
    def vmname(self, new_vmname):

        self._vmname = new_vmname
        try:
            self._machine = self._vboxmanager.vbox.findMachine(new_vmname)
        except Exception as e:
            raise VirtualBoxError("VirtualBox error: {}".format(e))

        # The maximum support network cards depends on the Chipset (PIIX3 or ICH9)
        self._maximum_adapters = self._vboxmanager.vbox.systemProperties.getMaxNetworkAdapters(self._machine.chipsetType)

    @property
    def console(self):

        return self._console

    @console.setter
    def console(self, console):

        self._console = console

    @property
    def headless(self):

        return self._headless

    @headless.setter
    def headless(self, headless):

        self._headless = headless

    @property
    def enable_console(self):

        return self._enable_console

    @enable_console.setter
    def enable_console(self, enable_console):

        self._enable_console = enable_console

    @property
    def adapters(self):

        return self._adapters

    @adapters.setter
    def adapters(self, adapters):

        self._adapters = adapters

    @property
    def adapter_type(self):

        return self._adapter_type

    @adapter_type.setter
    def adapter_type(self, adapter_type):

        self._adapter_type = adapter_type

    def start(self):

        if len(self._adapters) > self._maximum_adapters:
            raise VirtualBoxError("Number of adapters above the maximum supported of {}".format(self._maximum_adapters))

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

        if self._enable_console:
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

        if self._machine.state >= self._vboxmanager.constants.MachineState_FirstOnline and \
                self._machine.state <= self._vboxmanager.constants.MachineState_LastOnline:
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

                for adapter_id in range(0, len(self._adapters)):
                    if self._adapters[adapter_id] is None:
                        continue
                    self._disable_adapter(adapter_id, disable=True)
                serial_port = self._session.machine.getSerialPort(0)
                serial_port.enabled = False
                self._session.machine.saveSettings()
                self._unlock_machine()
            except Exception as e:
                # Do not crash "vboxwrapper", if stopping VM fails.
                # But return True anyway, so VM state in GNS3 can become "stopped"
                # This can happen, if user manually kills VBox VM.
                log.warn("could not stop VM for {}: {}".format(self._vmname, e))
                return

    def suspend(self):

        try:
            self._session.console.pause()
        except Exception as e:
            raise VirtualBoxError("VirtualBox error: {}".format(e))

    def reload(self):

        try:
            self._session.console.reset()
        except Exception as e:
            raise VirtualBoxError("VirtualBox error: {}".format(e))

    def resume(self):

        try:
            self._session.console.resume()
        except Exception as e:
            raise VirtualBoxError("VirtualBox error: {}".format(e))

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

        for adapter_id in range(0, len(self._adapters)):

            try:
                # VirtualBox starts counting from 0
                adapter = self._session.machine.getNetworkAdapter(adapter_id)
                if self._adapters[adapter_id] is None:
                    # force enable to avoid any discrepancy in the interface numbering inside the VM
                    # e.g. Ethernet2 in GNS3 becoming eth0 inside the VM when using a start index of 2.
                    adapter.enabled = True
                    continue

                vbox_adapter_type = adapter.adapterType
                if self._adapter_type == "PCnet-PCI II (Am79C970A)":
                    vbox_adapter_type = self._vboxmanager.constants.NetworkAdapterType_Am79C970A
                if self._adapter_type == "PCNet-FAST III (Am79C973)":
                    vbox_adapter_type = self._vboxmanager.constants.NetworkAdapterType_Am79C973
                if self._adapter_type == "Intel PRO/1000 MT Desktop (82540EM)":
                    vbox_adapter_type = self._vboxmanager.constants.NetworkAdapterType_I82540EM
                if self._adapter_type == "Intel PRO/1000 T Server (82543GC)":
                    vbox_adapter_type = self._vboxmanager.constants.NetworkAdapterType_I82543GC
                if self._adapter_type == "Intel PRO/1000 MT Server (82545EM)":
                    vbox_adapter_type = self._vboxmanager.constants.NetworkAdapterType_I82545EM
                if self._adapter_type == "Paravirtualized Network (virtio-net)":
                    vbox_adapter_type = self._vboxmanager.constants.NetworkAdapterType_Virtio
                if self._adapter_type == "Automatic":  # "Auto-guess, based on first NIC"
                    vbox_adapter_type = first_adapter_type

                adapter.adapterType = vbox_adapter_type

            except Exception as e:
                raise VirtualBoxError("VirtualBox error: {}".format(e))

            nio = self._adapters[adapter_id].get_nio(0)
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

        for adapter_id in range(len(self._adapters), self._maximum_adapters):
            log.debug("disabling remaining adapter {}".format(adapter_id))
            self._disable_adapter(adapter_id)

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

    def create_udp(self, adapter_id, sport, daddr, dport):

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

    def delete_udp(self, adapter_id):

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
        """
        # Example to manually set serial parameters using Python

        from vboxapi import VirtualBoxManager
        mgr = VirtualBoxManager(None, None)
        mach = mgr.vbox.findMachine("My VM")
        session = mgr.mgr.getSessionObject(mgr.vbox)
        mach.lockMachine(session, 1)
        mach2=session.machine
        serial_port = mach2.getSerialPort(0)
        serial_port.enabled = True
        serial_port.path = "/tmp/test_pipe"
        serial_port.hostMode = 1
        serial_port.server = True
        session.unlockMachine()
        """

        log.info("setting console options for {}".format(self._vmname))

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
