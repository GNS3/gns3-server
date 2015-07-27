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

from collections import OrderedDict

VMWARE_NETWORKING_FILE = "/etc/vmware/networking"
DEFAULT_RANGE = [10, 100]


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


def main():
    """
    Entry point for the VMNET tool.
    """

    if not sys.platform.startswith("linux"):
        raise SystemExit("This program can only be used on Linux")

    parser = argparse.ArgumentParser(description='%(prog)s add/remove vmnet interfaces')
    parser.add_argument('-r', "--range", nargs='+', action=parse_vmnet_range(1, 255),
                        type=int, help="vmnet range to add (default is {} {})".format(DEFAULT_RANGE[0], DEFAULT_RANGE[1]))
    parser.add_argument("-C", "--clean", action="store_true", help="remove all vmnets excepting vmnet1 and vmnet8")
    parser.add_argument("-l", "--list", action="store_true", help="list all existing vmnets")

    try:
        args = parser.parse_args()
    except argparse.ArgumentTypeError as e:
        raise SystemExit(e)

    vmnet_range = args.range if args.range is not None else DEFAULT_RANGE
    if not os.path.exists(VMWARE_NETWORKING_FILE):
        raise SystemExit("VMware Player or Workstation is not installed")
    if not os.access(VMWARE_NETWORKING_FILE, os.W_OK):
        raise SystemExit("You must run this script as root")

    version, pairs, allocated_subnets = parse_networking_file()

    if args.list:
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
        for vmnet_number in range(vmnet_range[0], vmnet_range[1]):
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

if __name__ == '__main__':
    main()
