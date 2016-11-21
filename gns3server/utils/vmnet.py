#!/usr/bin/env python
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

import sys
import os
import ipaddress
import argparse
import shutil

from collections import OrderedDict

if sys.platform.startswith("darwin"):
    VMWARE_NETWORKING_FILE = "/Library/Preferences/VMware Fusion/networking"
else:
    # location on Linux
    VMWARE_NETWORKING_FILE = "/etc/vmware/networking"

if sys.platform.startswith("win"):
    DEFAULT_RANGE = [1, 19]
else:
    DEFAULT_RANGE = [10, 99]


def parse_networking_file():
    """
    Parse the VMware networking file.
    """

    pairs = dict()
    allocated_subnets = []
    try:
        with open(VMWARE_NETWORKING_FILE, "r", encoding="utf-8") as f:
            version = f.readline()
            for line in f.read().splitlines():
                try:
                    _, key, value = line.split(' ', 3)
                    key = key.strip()
                    value = value.strip()
                    pairs[key] = value
                    if key.endswith("HOSTONLY_SUBNET"):
                        allocated_subnets.append(value)
                except ValueError:
                    raise SystemExit("Error while parsing {}".format(VMWARE_NETWORKING_FILE))
    except OSError as e:
        raise SystemExit("Cannot open {}: {}".format(VMWARE_NETWORKING_FILE, e))
    return version, pairs, allocated_subnets


def write_networking_file(version, pairs):
    """
    Write the VMware networking file.
    """

    vmnets = OrderedDict(sorted(pairs.items(), key=lambda t: t[0]))
    try:
        with open(VMWARE_NETWORKING_FILE, "w", encoding="utf-8") as f:
            f.write(version)
            for key, value in vmnets.items():
                f.write("answer {} {}\n".format(key, value))
    except OSError as e:
        raise SystemExit("Cannot open {}: {}".format(VMWARE_NETWORKING_FILE, e))

    # restart VMware networking service
    if sys.platform.startswith("darwin"):
        if not os.path.exists("/Applications/VMware Fusion.app/Contents/Library/vmnet-cli"):
            raise SystemExit("VMware Fusion is not installed in Applications")
        os.system(r"/Applications/VMware\ Fusion.app/Contents/Library/vmnet-cli --configure")
        os.system(r"/Applications/VMware\ Fusion.app/Contents/Library/vmnet-cli --stop")
        os.system(r"/Applications/VMware\ Fusion.app/Contents/Library/vmnet-cli --start")
    else:
        os.system("vmware-networks --stop")
        os.system("vmware-networks --start")


def parse_vmnet_range(start, end):
    """
    Parse the vmnet range on the command line.
    """

    class Range(argparse.Action):

        def __call__(self, parser, args, values, option_string=None):
            if len(values) != 2:
                raise argparse.ArgumentTypeError("vmnet range must consist of 2 numbers")
            if not start <= values[0] or not values[1] <= end:
                raise argparse.ArgumentTypeError("vmnet range must be between {} and {}".format(start, end))
            setattr(args, self.dest, values)
    return Range


def find_vnetlib_registry(regkey):

    import winreg
    try:
        # default path not used, let's look in the registry
        hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, regkey)
        install_path, _ = winreg.QueryValueEx(hkey, "InstallPath")
        winreg.CloseKey(hkey)
        vnetlib_path = os.path.join(install_path, "vnetlib64.exe")
        if os.path.exists(vnetlib_path):
            return vnetlib_path
        vnetlib_path = os.path.join(install_path, "vnetlib.exe")
        if os.path.exists(vnetlib_path):
            return vnetlib_path
    except OSError:
        pass
    return None


def find_vnetlib_on_windows():

    vnetlib_path = shutil.which("vnetlib")
    if vnetlib_path is None:
        # look for vnetlib.exe in default VMware Workstation directory
        vnetlib_ws = os.path.expandvars(r"%PROGRAMFILES(X86)%\VMware\VMware Workstation\vnetlib64.exe")
        if not os.path.exists(vnetlib_ws):
            vnetlib_ws = os.path.expandvars(r"%PROGRAMFILES(X86)%\VMware\VMware Workstation\vnetlib.exe")
        if os.path.exists(vnetlib_ws):
            vnetlib_path = vnetlib_ws

        if vnetlib_path is None:
            # look for vnetlib.exe using the directory listed in the registry
            vnetlib_path = find_vnetlib_registry(r"SOFTWARE\Wow6432Node\VMware, Inc.\VMware Workstation")
        if vnetlib_path is None:
            # look for vnetlib.exe in default VMware VIX directory
            vnetlib_vix = os.path.expandvars(r"%PROGRAMFILES(X86)%\VMware\VMware VIX\vnetlib.exe")
            if os.path.exists(vnetlib_vix):
                vnetlib_path = vnetlib_vix
            else:
                # look for vnetlib.exe using the directory listed in the registry
                vnetlib_path = find_vnetlib_registry(r"SOFTWARE\Wow6432Node\VMware, Inc.\VMware Player")
    return vnetlib_path


def vmnet_windows(args, vmnet_range_start, vmnet_range_end):

    vnetlib_path = find_vnetlib_on_windows()
    if not vnetlib_path:
        raise SystemExit("VMware is not installed, could not find vnetlib.exe")
    from win32com.shell import shell
    if not shell.IsUserAnAdmin():
        raise SystemExit("You must run this script as an administrator")

    print("Using", vnetlib_path, "for controlling vmnet")

    if args.list:
        raise SystemExit("Not implemented")

    if args.clean:
        # clean all vmnets but vmnet1 and vmnet8
        for vmnet_number in range(1, 20):
            if vmnet_number in (1, 8):
                continue
            print("Removing vmnet{}...".format(vmnet_number))
            os.system('"{}" -- remove adapter vmnet{}'.format(vnetlib_path, vmnet_number))
    else:
        for vmnet_number in range(vmnet_range_start, vmnet_range_end + 1):
            if vmnet_number in (1, 8):
                continue
            print("Adding vmnet{}...".format(vmnet_number))
            os.system('"{}" -- add adapter vmnet{}'.format(vnetlib_path, vmnet_number))
    os.system("net stop npf")
    os.system("net start npf")
    os.system("net stop npcap")
    os.system("net start npcap")


def vmnet_unix(args, vmnet_range_start, vmnet_range_end):
    """
    Implementation on Linux and Mac OS X.
    """

    if not os.path.exists(VMWARE_NETWORKING_FILE):
        raise SystemExit("VMware Player, Workstation or Fusion is not installed")
    if not os.access(VMWARE_NETWORKING_FILE, os.W_OK):
        raise SystemExit("You must run this script as root")

    version, pairs, allocated_subnets = parse_networking_file()
    if args.list and not sys.platform.startswith("win"):
        for vmnet_number in range(1, 256):
            vmnet_name = "VNET_{}_VIRTUAL_ADAPTER".format(vmnet_number)
            if vmnet_name in pairs:
                print("vmnet{}".format(vmnet_number))
        return

    if args.clean:
        # clean all vmnets but vmnet1 and vmnet8
        for key in pairs.copy().keys():
            if key.startswith("VNET_1_") or key.startswith("VNET_8_"):
                continue
            del pairs[key]
    else:
        for vmnet_number in range(vmnet_range_start, vmnet_range_end + 1):
            vmnet_name = "VNET_{}_VIRTUAL_ADAPTER".format(vmnet_number)
            if vmnet_name in pairs:
                continue
            allocated_subnet = None
            for subnet in ipaddress.ip_network("172.16.0.0/16").subnets(prefixlen_diff=8):
                subnet = str(subnet.network_address)
                if subnet not in allocated_subnets:
                    allocated_subnet = subnet
                    allocated_subnets.append(allocated_subnet)
                    break

            if allocated_subnet is None:
                print("Couldn't allocate a subnet for vmnet{}".format(vmnet_number))
                continue

            print("Adding vmnet{}...".format(vmnet_number))
            pairs["VNET_{}_HOSTONLY_NETMASK".format(vmnet_number)] = "255.255.255.0"
            pairs["VNET_{}_HOSTONLY_SUBNET".format(vmnet_number)] = allocated_subnet
            pairs["VNET_{}_VIRTUAL_ADAPTER".format(vmnet_number)] = "yes"

    write_networking_file(version, pairs)


def main():
    """
    Entry point for the VMNET tool.
    """

    parser = argparse.ArgumentParser(description='%(prog)s add/remove vmnet interfaces')
    parser.add_argument('-r', "--range", nargs='+', action=parse_vmnet_range(1, 255),
                        type=int, help="vmnet range to add (default is {} {})".format(DEFAULT_RANGE[0], DEFAULT_RANGE[1]))
    parser.add_argument("-C", "--clean", action="store_true", help="remove all vmnets excepting vmnet1 and vmnet8")
    parser.add_argument("-l", "--list", action="store_true", help="list all existing vmnets (UNIX only)")

    try:
        args = parser.parse_args()
    except argparse.ArgumentTypeError as e:
        raise SystemExit(e)

    vmnet_range = args.range if args.range is not None else DEFAULT_RANGE
    if sys.platform.startswith("win"):
        try:
            vmnet_windows(args, vmnet_range[0], vmnet_range[1])
        except SystemExit:
            os.system("pause")
            raise
    else:
        vmnet_unix(args, vmnet_range[0], vmnet_range[1])

if __name__ == '__main__':
    main()
