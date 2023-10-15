#!/usr/bin/env python
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

from gns3server.controller.controller_error import ControllerError
from gns3server.utils import macaddress_to_int, int_to_macaddress
from .atm_port import ATMPort
from .frame_relay_port import FrameRelayPort
from .gigabitethernet_port import GigabitEthernetPort
from .fastethernet_port import FastEthernetPort
from .ethernet_port import EthernetPort
from .serial_port import SerialPort
from .pos_port import POSPort


import logging

log = logging.getLogger(__name__)

PORTS = {
    "atm": ATMPort,
    "frame_relay": FrameRelayPort,
    "fastethernet": FastEthernetPort,
    "gigabitethernet": GigabitEthernetPort,
    "ethernet": EthernetPort,
    "serial": SerialPort,
}


class PortFactory:
    """
    Factory to create a Port object based on the type
    """

    def __new__(cls, name, interface_number, adapter_number, port_number, port_type, **kwargs):
        return PORTS[port_type](name, interface_number, adapter_number, port_number, **kwargs)


class StandardPortFactory:
    """
    Create ports for standard device
    """

    def __new__(
        cls, properties, port_by_adapter, first_port_name, port_name_format, port_segment_size, custom_adapters
    ):
        ports = []
        adapter_number = interface_number = segment_number = 0

        if "ethernet_adapters" in properties:
            ethernet_adapters = properties["ethernet_adapters"]
        else:
            ethernet_adapters = properties.get("adapters", 1)

        for adapter_number in range(adapter_number, ethernet_adapters + adapter_number):

            custom_adapter_settings = {}
            for custom_adapter in custom_adapters:
                if custom_adapter["adapter_number"] == adapter_number:
                    custom_adapter_settings = custom_adapter
                    break

            for port_number in range(0, port_by_adapter):
                if first_port_name and adapter_number == 0:
                    port_name = custom_adapter_settings.get("port_name", first_port_name)
                    port = PortFactory(
                        port_name, segment_number, adapter_number, port_number, "ethernet", short_name=port_name
                    )
                else:
                    try:
                        port_name = port_name_format.format(
                            interface_number,
                            segment_number,
                            adapter=adapter_number,
                            **cls._generate_replacement(interface_number, segment_number),
                        )
                    except (IndexError, ValueError, KeyError) as e:
                        raise ControllerError(f"Invalid port name format {port_name_format}: {str(e)}")

                    port_name = custom_adapter_settings.get("port_name", port_name)
                    port = PortFactory(port_name, segment_number, adapter_number, port_number, "ethernet")
                    interface_number += 1
                    if port_segment_size:
                        if interface_number % port_segment_size == 0:
                            segment_number += 1
                            interface_number = 0
                    else:
                        segment_number += 1

                port.adapter_type = custom_adapter_settings.get("adapter_type", properties.get("adapter_type", None))
                mac_address = custom_adapter_settings.get("mac_address")
                if not mac_address and "mac_address" in properties:
                    mac_address = int_to_macaddress(macaddress_to_int(properties["mac_address"]) + adapter_number)
                port.mac_address = mac_address
                ports.append(port)

        if len(ports):
            adapter_number += 1

        if "serial_adapters" in properties:
            for adapter_number in range(adapter_number, properties["serial_adapters"] + adapter_number):
                for port_number in range(0, port_by_adapter):
                    ports.append(
                        PortFactory(
                            f"Serial{segment_number}/{port_number}",
                            segment_number,
                            adapter_number,
                            port_number,
                            "serial",
                        )
                    )
                segment_number += 1

        return ports

    @staticmethod
    def _generate_replacement(interface_number, segment_number):
        """
        This will generate replacement string for
        {port0} => {port9}
        {segment0} => {segment9}
        """

        replacements = {}
        for i in range(0, 9):
            replacements["port" + str(i)] = interface_number + i
            replacements["segment" + str(i)] = segment_number + i
        return replacements


class DynamipsPortFactory:
    """
    Create port for dynamips devices
    """

    ADAPTER_MATRIX = {
        "C1700-MB-1FE": {"nb_ports": 1, "port": FastEthernetPort},
        "C1700-MB-WIC1": {"nb_ports": 0, "port": None},
        "C2600-MB-1E": {"nb_ports": 1, "port": EthernetPort},
        "C2600-MB-1FE": {"nb_ports": 1, "port": FastEthernetPort},
        "C2600-MB-2E": {"nb_ports": 2, "port": EthernetPort},
        "C2600-MB-2FE": {"nb_ports": 2, "port": FastEthernetPort},
        "C7200-IO-2FE": {"nb_ports": 2, "port": FastEthernetPort},
        "C7200-IO-FE": {"nb_ports": 1, "port": FastEthernetPort},
        "C7200-IO-GE-E": {"nb_ports": 1, "port": GigabitEthernetPort},
        "GT96100-FE": {"nb_ports": 2, "port": FastEthernetPort},
        "Leopard-2FE": {"nb_ports": 2, "port": FastEthernetPort},
        "NM-16ESW": {"nb_ports": 16, "port": FastEthernetPort},
        "NM-1E": {"nb_ports": 1, "port": EthernetPort},
        "NM-1FE-TX": {"nb_ports": 1, "port": FastEthernetPort},
        "NM-4E": {"nb_ports": 4, "port": EthernetPort},
        "NM-4T": {"nb_ports": 4, "port": SerialPort},
        "PA-2FE-TX": {"nb_ports": 2, "port": FastEthernetPort},
        "PA-4E": {"nb_ports": 4, "port": EthernetPort},
        "PA-4T+": {"nb_ports": 4, "port": SerialPort},
        "PA-8E": {"nb_ports": 8, "port": EthernetPort},
        "PA-8T": {"nb_ports": 8, "port": SerialPort},
        "PA-A1": {"nb_ports": 1, "port": ATMPort},
        "PA-FE-TX": {"nb_ports": 1, "port": FastEthernetPort},
        "PA-GE": {"nb_ports": 1, "port": GigabitEthernetPort},
        "PA-POS-OC3": {"nb_ports": 1, "port": POSPort},
    }

    WIC_MATRIX = {
        "WIC-1ENET": {"nb_ports": 1, "port": EthernetPort},
        "WIC-1T": {"nb_ports": 1, "port": SerialPort},
        "WIC-2T": {"nb_ports": 2, "port": SerialPort},
    }

    def __new__(cls, properties):

        ports = []
        adapter_number = 0
        wic_slot = 1
        wic_port_number = wic_slot * 16
        display_wic_port_number = 0
        for name in sorted(properties.keys()):
            if name.startswith("slot"):
                if properties[name]:
                    port_class = cls.ADAPTER_MATRIX[properties[name]]["port"]
                    for port_number in range(0, cls.ADAPTER_MATRIX[properties[name]]["nb_ports"]):
                        name = f"{port_class.long_name_type()}{adapter_number}/{port_number}"
                        port = port_class(name, adapter_number, adapter_number, port_number)
                        port.short_name = f"{port_class.short_name_type()}{adapter_number}/{port_number}"
                        ports.append(port)
                adapter_number += 1
            elif name.startswith("wic"):
                if properties[name]:
                    port_class = cls.WIC_MATRIX[properties[name]]["port"]
                    for port_number in range(0, cls.WIC_MATRIX[properties[name]]["nb_ports"]):
                        name = f"{port_class.long_name_type()}{0}/{display_wic_port_number}"
                        port = port_class(name, 0, 0, wic_port_number)
                        port.short_name = f"{port_class.short_name_type()}{0}/{display_wic_port_number}"
                        ports.append(port)
                        display_wic_port_number += 1
                        wic_port_number += 1
                wic_slot += 1
                wic_port_number = wic_slot * 16

        return ports
