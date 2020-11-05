#!/usr/bin/env python
#
# Copyright (C) 2018 GNS3 Technologies Inc.
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

import sys
import logging
import asyncio
import psutil
import ipaddress

from .base_gns3_vm import BaseGNS3VM
from .gns3_vm_error import GNS3VMError
log = logging.getLogger(__name__)


class HyperVGNS3VM(BaseGNS3VM):

    _HYPERV_VM_STATE_ENABLED = 2
    _HYPERV_VM_STATE_DISABLED = 3
    _HYPERV_VM_STATE_SHUTDOWN = 4
    _HYPERV_VM_STATE_PAUSED = 9

    _WMI_JOB_STATUS_STARTED = 4096
    _WMI_JOB_STATE_RUNNING = 4
    _WMI_JOB_STATE_COMPLETED = 7

    def __init__(self, controller):

        self._engine = "hyper-v"
        super().__init__(controller)
        self._conn = None
        self._vm = None
        self._management = None
        self._wmi = None

    def _check_requirements(self):
        """
        Checks if the GNS3 VM can run on Hyper-V.
        """

        if not sys.platform.startswith("win"):
            raise GNS3VMError("Hyper-V is only supported on Windows")

        if sys.getwindowsversion().platform_version[0] < 10:
            raise GNS3VMError("Windows 10/Windows Server 2016 or a later version is required to run Hyper-V with nested virtualization enabled (version {} detected)".format(sys.getwindowsversion().platform_version[0]))

        is_windows_10 = sys.getwindowsversion().platform_version[0] == 10 and sys.getwindowsversion().platform_version[1] == 0

        if is_windows_10 and sys.getwindowsversion().platform_version[2] < 14393:
            raise GNS3VMError("Hyper-V with nested virtualization is only supported on Windows 10 Anniversary Update (build 10.0.14393) or later")

        try:
            import pythoncom
            pythoncom.CoInitialize()
            import wmi
            self._wmi = wmi
            conn = self._wmi.WMI()
        except self._wmi.x_wmi as e:
            raise GNS3VMError("Could not connect to WMI: {}".format(e))

        if not conn.Win32_ComputerSystem()[0].HypervisorPresent:
            raise GNS3VMError("Hyper-V is not installed or activated")

        if conn.Win32_Processor()[0].Manufacturer != "GenuineIntel":
            if is_windows_10 and conn.Win32_Processor()[0].Manufacturer == "AuthenticAMD":
                if sys.getwindowsversion().platform_version[2] < 19640:
                    raise GNS3VMError("Windows 10 (build 10.0.19640) or later is required by Hyper-V to support nested virtualization with AMD processors")
            else:
                raise GNS3VMError("An Intel processor is required by Hyper-V to support nested virtualization on this version of Windows")

        # This is not reliable
        #if not conn.Win32_Processor()[0].VirtualizationFirmwareEnabled:
        #    raise GNS3VMError("Nested Virtualization (VT-x) is not enabled on this system")

    def _connect(self):
        """
        Connects to local host using WMI.
        """

        self._check_requirements()

        try:
            self._conn = self._wmi.WMI(namespace=r"root\virtualization\v2")
        except self._wmi.x_wmi as e:
            raise GNS3VMError("Could not connect to WMI: {}".format(e))

        if not self._conn.Msvm_VirtualSystemManagementService():
            raise GNS3VMError("The Windows account running GNS3 does not have the required permissions for Hyper-V")

        self._management = self._conn.Msvm_VirtualSystemManagementService()[0]

    def _find_vm(self, vm_name):
        """
        Finds a Hyper-V VM.
        """

        if self._conn is None:
            self._connect()
        vms = self._conn.Msvm_ComputerSystem(ElementName=vm_name)
        nb_vms = len(vms)
        if nb_vms == 0:
            return None
        elif nb_vms > 1:
            raise GNS3VMError("Duplicate VM name found for {}".format(vm_name))
        else:
            return vms[0]

    def _is_running(self):
        """
        Checks if the VM is running.
        """

        if self._vm is not None and self._vm.EnabledState == HyperVGNS3VM._HYPERV_VM_STATE_ENABLED:
            return True
        return False

    def _get_vm_setting_data(self, vm):
        """
        Gets the VM settings.

        :param vm: VM instance
        """

        vm_settings = vm.associators(wmi_result_class='Msvm_VirtualSystemSettingData')
        return [s for s in vm_settings if s.VirtualSystemType == 'Microsoft:Hyper-V:System:Realized'][0]

    def _get_vm_resources(self, vm, resource_class):
        """
        Gets specific VM resource.

        :param vm: VM instance
        :param resource_class: resource class name
        """

        setting_data = self._get_vm_setting_data(vm)
        return setting_data.associators(wmi_result_class=resource_class)

    def _set_vcpus_ram(self, vcpus, ram):
        """
        Set the number of vCPU cores and amount of RAM for the GNS3 VM.

        :param vcpus: number of vCPU cores
        :param ram: amount of RAM
        """

        available_vcpus = psutil.cpu_count(logical=False)
        if vcpus > available_vcpus:
            raise GNS3VMError("You have allocated too many vCPUs for the GNS3 VM! (max available is {} vCPUs)".format(available_vcpus))

        try:
            mem_settings = self._get_vm_resources(self._vm, 'Msvm_MemorySettingData')[0]
            cpu_settings = self._get_vm_resources(self._vm, 'Msvm_ProcessorSettingData')[0]

            mem_settings.VirtualQuantity = ram
            mem_settings.Reservation = ram
            mem_settings.Limit = ram
            self._management.ModifyResourceSettings(ResourceSettings=[mem_settings.GetText_(1)])

            cpu_settings.VirtualQuantity = vcpus
            cpu_settings.Reservation = vcpus
            cpu_settings.Limit = 100000  # use 100% of CPU
            cpu_settings.ExposeVirtualizationExtensions = True  # allow the VM to use nested virtualization
            self._management.ModifyResourceSettings(ResourceSettings=[cpu_settings.GetText_(1)])

            log.info("GNS3 VM vCPU count set to {} and RAM amount set to {}".format(vcpus, ram))
        except Exception as e:
            raise GNS3VMError("Could not set to {} and RAM amount set to {}: {}".format(vcpus, ram, e))

    async def list(self):
        """
        List all Hyper-V VMs
        """

        if self._conn is None or self._management is None:
            self._connect()

        vms = []
        try:
            for vm in self._conn.Msvm_ComputerSystem():
                if vm.ElementName != self._management.SystemName:
                    vms.append({"vmname": vm.ElementName})
        except self._wmi.x_wmi as e:
            raise GNS3VMError("Could not list Hyper-V VMs: {}".format(e))
        return vms

    def _get_wmi_obj(self, path):
        """
        Gets the WMI object.
        """

        return self._wmi.WMI(moniker=path.replace('\\', '/'))

    async def _set_state(self, state):
        """
        Set the desired state of the VM
        """

        if not self._vm:
            self._vm = self._find_vm(self.vmname)
        if not self._vm:
            raise GNS3VMError("Could not find Hyper-V VM {}".format(self.vmname))
        job_path, ret = self._vm.RequestStateChange(state)
        if ret == HyperVGNS3VM._WMI_JOB_STATUS_STARTED:
            job = self._get_wmi_obj(job_path)
            while job.JobState == HyperVGNS3VM._WMI_JOB_STATE_RUNNING:
                await asyncio.sleep(0.1)
                job = self._get_wmi_obj(job_path)
            if job.JobState != HyperVGNS3VM._WMI_JOB_STATE_COMPLETED:
                raise GNS3VMError("Error while changing state: {}".format(job.ErrorSummaryDescription))
        elif ret != 0 or ret != 32775:
            raise GNS3VMError("Failed to change state to {}".format(state))

    async def _is_vm_network_active(self):
        """
        Check if WMI is updated with VM virtual network adapters
        and wait until their count becomes > 0
        ProtocolIFType  Unknown (0)
                        Other (1)
                        IPv4 (4096)
                        IPv6 (4097)
                        IPv4/v6 (4098)
        """

        wql = "SELECT * FROM Msvm_GuestNetworkAdapterConfiguration WHERE InstanceID like \
               'Microsoft:GuestNetwork\\" + self._vm.Name + "%' and ProtocolIFType > 0 "
        nic_count = len(self._conn.query(wql))
        while nic_count == 0:
            await asyncio.sleep(0.1)  # 100ms
            nic_count = len(self._conn.query(wql))

    async def start(self):
        """
        Starts the GNS3 VM.
        """

        self._vm = self._find_vm(self.vmname)
        if not self._vm:
            raise GNS3VMError("Could not find Hyper-V VM {}".format(self.vmname))

        if not self._is_running():
            if self.allocate_vcpus_ram:
                log.info("Update GNS3 VM settings (CPU and RAM)")
                # set the number of vCPUs and amount of RAM
                self._set_vcpus_ram(self.vcpus, self.ram)

            # start the VM
            try:
                await self._set_state(HyperVGNS3VM._HYPERV_VM_STATE_ENABLED)
            except GNS3VMError as e:
                raise GNS3VMError("Failed to start the GNS3 VM: {}".format(e))
            log.info("GNS3 VM has been started")

        # check if VM network is active
        await self._is_vm_network_active()

        # Get the guest IP address
        # LIS (Linux Integration Services) must be installed on the guest
        # See https://oitibs.com/hyper-v-lis-on-ubuntu-18-04/ for details.
        trial = 120
        guest_ip_address = ""
        log.info("Waiting for GNS3 VM IP")
        ports = self._get_vm_resources(self._vm, 'Msvm_EthernetPortAllocationSettingData')
        vnics = self._get_vm_resources(self._vm, 'Msvm_SyntheticEthernetPortSettingData')
        while True:
            for port in ports:
                try:
                    vnic = [v for v in vnics if port.Parent == v.path_()][0]
                except IndexError:
                    continue
                config = vnic.associators(wmi_result_class='Msvm_GuestNetworkAdapterConfiguration')
                ip_addresses = config[0].IPAddresses
                for ip_address in ip_addresses:
                    # take the first valid IPv4 address
                    try:
                        ipaddress.IPv4Address(ip_address)
                        guest_ip_address = ip_address
                    except ipaddress.AddressValueError:
                        continue
                if len(ip_addresses):
                    guest_ip_address = ip_addresses[0]
                    break
            trial -= 1
            if guest_ip_address:
                break
            elif trial == 0:
                raise GNS3VMError("Could not find guest IP address for {}".format(self.vmname))
            await asyncio.sleep(1)
        self.ip_address = guest_ip_address
        log.info("GNS3 VM IP address set to {}".format(guest_ip_address))
        self.running = True

    async def suspend(self):
        """
        Suspends the GNS3 VM.
        """

        try:
            await self._set_state(HyperVGNS3VM._HYPERV_VM_STATE_PAUSED)
        except GNS3VMError as e:
            raise GNS3VMError("Failed to suspend the GNS3 VM: {}".format(e))
        log.info("GNS3 VM has been suspended")
        self.running = False

    async def stop(self):
        """
        Stops the GNS3 VM.
        """

        try:
            await self._set_state(HyperVGNS3VM._HYPERV_VM_STATE_SHUTDOWN)
        except GNS3VMError as e:
            raise GNS3VMError("Failed to stop the GNS3 VM: {}".format(e))
        log.info("GNS3 VM has been stopped")
        self.running = False
