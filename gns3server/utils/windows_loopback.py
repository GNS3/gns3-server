#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
import argparse
import shutil
import ipaddress

if sys.platform.startswith("win"):
    import wmi
else:
    raise SystemExit("This script must run on Windows!")


def parse_add_loopback():
    """
    Validate params when adding a loopback adapter
    """

    class Add(argparse.Action):

        def __call__(self, parser, args, values, option_string=None):
            try:
                ipaddress.IPv4Interface("{}/{}".format(values[1], values[2]))
            except ipaddress.AddressValueError as e:
                raise argparse.ArgumentTypeError("Invalid IP address: {}".format(e))
            except ipaddress.NetmaskValueError as e:
                raise argparse.ArgumentTypeError("Invalid subnet mask: {}".format(e))
            setattr(args, self.dest, values)
    return Add


def add_loopback(devcon_path, name, ip_address, netmask):

    # save the list of network adapter in order to find the one we are about to add
    previous_adapters = wmi.WMI().Win32_NetworkAdapter()
    for adapter in previous_adapters:
        if "Loopback" in adapter.Description and adapter.NetConnectionID == name:
            raise SystemExit('Windows loopback adapter named "{}" already exists'.format(name))

    # install a new Windows loopback adapter
    os.system('"{}" install {}\\inf\\netloop.inf *MSLOOP'.format(devcon_path, os.path.expandvars("%WINDIR%")))

    # configure the new Windows loopback adapter
    for adapter in wmi.WMI().Win32_NetworkAdapter():
        if "Loopback" in adapter.Description and adapter not in previous_adapters:
            print('Renaming loopback adapter "{}" to "{}"'.format(adapter.NetConnectionID, name))
            adapter.NetConnectionID = name
            for network_config in wmi.WMI().Win32_NetworkAdapterConfiguration(IPEnabled=True):
                if network_config.InterfaceIndex == adapter.InterfaceIndex:
                    print('Configuring loopback adapter "{}" with {} {}'.format(name, ip_address, netmask))
                    retcode = network_config.EnableStatic(IPAddress=[ip_address], SubnetMask=[netmask])[0]
                    if retcode == 1:
                        print("A reboot is required")
                    elif retcode != 0:
                        print('Error while configuring IP/Subnet mask on "{}"')

                    #FIXME: support gateway?
                    #network_config.SetGateways(DefaultIPGateway=[""])
            break

    # restart winpcap/npcap services to take the new adapter into account
    os.system("net stop npf")
    os.system("net start npf")
    os.system("net stop npcap")
    os.system("net start npcap")


def remove_loopback(devcon_path, name):

    deleted = False
    for adapter in wmi.WMI().Win32_NetworkAdapter():
        if "Loopback" in adapter.Description and adapter.NetConnectionID == name:
            # remove a Windows loopback adapter
            print('Removing loopback adapter "{}"'.format(name))
            os.system('"{}" remove @{}'.format(devcon_path, adapter.PNPDeviceID))
            deleted = True

    if not deleted:
        raise SystemExit('Could not find adapter "{}"'.format(name))

    # update winpcap/npcap services
    os.system("net stop npf")
    os.system("net start npf")
    os.system("net stop npcap")
    os.system("net start npcap")


def main():
    """
    Entry point for the Windows loopback tool.
    """

    parser = argparse.ArgumentParser(description='%(prog)s add/remove Windows loopback adapters')
    parser.add_argument('-a', "--add", nargs=3, action=parse_add_loopback(), help="add a Windows loopback adapter")
    parser.add_argument("-r", "--remove", action="store", help="remove a Windows loopback adapter")
    try:
        args = parser.parse_args()
    except argparse.ArgumentTypeError as e:
        raise SystemExit(e)

    # devcon is required to install/remove Windows loopback adapters
    devcon_path = shutil.which("devcon")
    if not devcon_path:
        raise SystemExit("Could not find devcon.exe")

    from win32com.shell import shell
    if not shell.IsUserAnAdmin():
        raise SystemExit("You must run this script as an administrator")

    try:
        if args.add:
            add_loopback(devcon_path, args.add[0], args.add[1], args.add[2])
        if args.remove:
            remove_loopback(devcon_path, args.remove)
    except SystemExit as e:
        print(e)
        os.system("pause")

if __name__ == '__main__':
    main()
