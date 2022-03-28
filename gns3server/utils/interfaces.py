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


import os
import sys
import socket
import struct
import psutil

from gns3server.compute.compute_error import ComputeError
from gns3server.config import Config

if psutil.version_info < (3, 0, 0):
    raise Exception(
        "psutil version should >= 3.0.0. If you are under Ubuntu/Debian install gns3 via apt instead of pip"
    )

import logging

log = logging.getLogger(__name__)


def _get_windows_interfaces_from_registry():

    import winreg

    # HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces
    interfaces = []
    try:
        hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\NetworkCards")
        for index in range(winreg.QueryInfoKey(hkey)[0]):
            network_card_id = winreg.EnumKey(hkey, index)
            hkeycard = winreg.OpenKey(hkey, network_card_id)
            guid, _ = winreg.QueryValueEx(hkeycard, "ServiceName")
            netcard, _ = winreg.QueryValueEx(hkeycard, "Description")
            connection = (
                r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}"
                + fr"\{guid}\Connection"
            )
            hkeycon = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, connection)
            name, _ = winreg.QueryValueEx(hkeycon, "Name")
            interface = fr"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{guid}"
            hkeyinterface = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, interface)
            is_dhcp_enabled, _ = winreg.QueryValueEx(hkeyinterface, "EnableDHCP")
            if is_dhcp_enabled:
                ip_address, _ = winreg.QueryValueEx(hkeyinterface, "DhcpIPAddress")
                netmask, _ = winreg.QueryValueEx(hkeyinterface, "DhcpSubnetMask")
            else:
                ip_address, _ = winreg.QueryValueEx(hkeyinterface, "IPAddress")
                netmask, _ = winreg.QueryValueEx(hkeyinterface, "SubnetMask")
                if ip_address:
                    # get the first IPv4 address only
                    ip_address = ip_address[0]
            npf_interface = "\\Device\\NPF_{guid}".format(guid=guid)
            interfaces.append(
                {
                    "id": npf_interface,
                    "name": name,
                    "ip_address": ip_address,
                    "mac_address": "",  # TODO: find MAC address in registry
                    "netcard": netcard,
                    "netmask": netmask,
                    "type": "ethernet",
                }
            )
            winreg.CloseKey(hkeyinterface)
            winreg.CloseKey(hkeycon)
            winreg.CloseKey(hkeycard)
        winreg.CloseKey(hkey)
    except OSError as e:
        log.error(f"could not read registry information: {e}")

    return interfaces


def get_windows_interfaces():
    """
    Get Windows interfaces.

    :returns: list of windows interfaces
    """

    import win32com.client
    import pywintypes

    interfaces = []
    try:
        locator = win32com.client.Dispatch("WbemScripting.SWbemLocator")
        service = locator.ConnectServer(".", r"root\cimv2")
        network_configs = service.InstancesOf("Win32_NetworkAdapterConfiguration")
        # more info on Win32_NetworkAdapter: http://msdn.microsoft.com/en-us/library/aa394216%28v=vs.85%29.aspx
        for adapter in service.InstancesOf("Win32_NetworkAdapter"):
            if adapter.NetConnectionStatus == 2 or adapter.NetConnectionStatus == 7:
                # adapter is connected or media disconnected
                ip_address = ""
                netmask = ""
                for network_config in network_configs:
                    if network_config.InterfaceIndex == adapter.InterfaceIndex:
                        if network_config.IPAddress:
                            # get the first IPv4 address only
                            ip_address = network_config.IPAddress[0]
                            netmask = network_config.IPSubnet[0]
                        break
                npf_interface = "\\Device\\NPF_{guid}".format(guid=adapter.GUID)
                interfaces.append(
                    {
                        "id": npf_interface,
                        "name": adapter.NetConnectionID,
                        "ip_address": ip_address,
                        "mac_address": adapter.MACAddress,
                        "netcard": adapter.name,
                        "netmask": netmask,
                        "type": "ethernet",
                    }
                )
    except (AttributeError, pywintypes.com_error):
        log.warning("Could not use the COM service to retrieve interface info, trying using the registry...")
        return _get_windows_interfaces_from_registry()

    return interfaces


def has_netmask(interface_name):
    """
    Checks if an interface has a netmask.

    :param interface: interface name

    :returns: boolean
    """
    for interface in interfaces():
        if interface["name"] == interface_name:
            if interface["netmask"] and len(interface["netmask"]) > 0:
                return True
            return False
    return False


def is_interface_up(interface):
    """
    Checks if an interface is up.

    :param interface: interface name

    :returns: boolean
    """

    if sys.platform.startswith("linux"):

        if interface not in psutil.net_if_addrs():
            return False

        import fcntl

        SIOCGIFFLAGS = 0x8913
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                result = fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, interface + "\0" * 256)
                (flags,) = struct.unpack("H", result[16:18])
                if flags & 1:  # check if the up bit is set
                    return True
            return False
        except OSError as e:
            raise ComputeError(f"Exception when checking if {interface} is up: {e}")
    else:
        # TODO: Windows & OSX support
        return True


def is_interface_bridge(interface):
    """
    :returns: True if interface is a bridge
    """
    return os.path.exists(os.path.join("/sys/class/net/", interface, "bridge"))


def interfaces():
    """
    Gets the network interfaces on this server.

    :returns: list of network interfaces
    """

    results = []
    allowed_interfaces = Config.instance().settings.Server.allowed_interfaces
    net_if_addrs = psutil.net_if_addrs()
    for interface in sorted(net_if_addrs.keys()):
        if allowed_interfaces and interface not in allowed_interfaces and not interface.startswith("gns3tap"):
            log.warning(f"Interface '{interface}' is not allowed to be used on this server")
            continue
        ip_address = ""
        mac_address = ""
        netmask = ""
        interface_type = "ethernet"
        for addr in net_if_addrs[interface]:
            # get the first available IPv4 address only
            if addr.family == socket.AF_INET:
                ip_address = addr.address
                netmask = addr.netmask
            if addr.family == psutil.AF_LINK:
                mac_address = addr.address
        if interface.startswith("tap"):
            # found no way to reliably detect a TAP interface
            interface_type = "tap"
        results.append(
            {
                "id": interface,
                "name": interface,
                "ip_address": ip_address,
                "netmask": netmask,
                "mac_address": mac_address,
                "type": interface_type,
            }
        )

    # This interface have special behavior
    for result in results:
        result["special"] = False
        for special_interface in (
            "lo",
            "vmnet",
            "vboxnet",
            "docker",
            "lxcbr",
            "virbr",
            "ovs-system",
            "veth",
            "fw",
            "p2p",
            "bridge",
            "vmware",
            "virtualbox",
            "gns3",
        ):
            if result["name"].lower().startswith(special_interface):
                result["special"] = True
        for special_interface in "-nic":
            if result["name"].lower().endswith(special_interface):
                result["special"] = True
    return results
