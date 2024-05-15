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


CLASSIC_SYMBOL_THEME = {"cloud": ":/symbols/classic/cloud.svg",
                        "nat": ":/symbols/classic/nat.svg",
                        "ethernet_switch": ":/symbols/classic/ethernet_switch.svg",
                        "ethernet_hub": ":/symbols/classic/hub.svg",
                        "frame_relay_switch": ":/symbols/classic/frame_relay_switch.svg",
                        "atm_switch": ":/symbols/classic/atm_switch.svg",
                        "router": ":/symbols/classic/router.svg",
                        "multilayer_switch": ":/symbols/classic/multilayer_switch.svg",
                        "firewall": ":/symbols/classic/firewall.svg",
                        "computer": ":/symbols/classic/computer.svg",
                        "vpcs_guest": ":/symbols/classic/vpcs_guest.svg",
                        "qemu_guest": ":/symbols/classic/qemu_guest.svg",
                        "vbox_guest": ":/symbols/classic/vbox_guest.svg",
                        "vmware_guest": ":/symbols/classic/vmware_guest.svg",
                        "docker_guest": ":/symbols/classic/docker_guest.svg"}

AFFINITY_SQUARE_BLUE_SYMBOL_THEME = {"cloud": ":/symbols/affinity/square/blue/cloud.svg",
                                     "nat": ":/symbols/affinity/square/blue/nat.svg",
                                     "ethernet_switch": ":/symbols/affinity/square/blue/switch.svg",
                                     "ethernet_hub": ":/symbols/affinity/square/blue/hub.svg",
                                     "frame_relay_switch.svg": ":/symbols/affinity/square/blue/isdn.svg",
                                     "atm_switch": ":/symbols/affinity/square/blue/atm.svg",
                                     "router": ":/symbols/affinity/square/blue/router.svg",
                                     "multilayer_switch": ":/symbols/affinity/square/blue/switch_multilayer.svg",
                                     "firewall": ":/symbols/affinity/square/blue/firewall3.svg",
                                     "computer": ":/symbols/affinity/square/blue/client.svg",
                                     "vpcs_guest": ":/symbols/affinity/square/blue/client.svg",
                                     "qemu_guest": ":/symbols/affinity/square/blue/client_vm.svg",
                                     "vbox_guest": ":/symbols/affinity/square/blue/virtualbox.svg",
                                     "vmware_guest": ":/symbols/affinity/square/blue/vmware.svg",
                                     "docker_guest": ":/symbols/affinity/square/blue/docker.svg"}

AFFINITY_SQUARE_RED_SYMBOL_THEME = {"cloud": ":/symbols/affinity/square/red/cloud.svg",
                                    "nat": ":/symbols/affinity/square/red/nat.svg",
                                    "ethernet_switch": ":/symbols/affinity/square/red/switch.svg",
                                    "ethernet_hub": ":/symbols/affinity/square/red/hub.svg",
                                    "frame_relay_switch": ":/symbols/affinity/square/red/isdn.svg",
                                    "atm_switch": ":/symbols/affinity/square/red/atm.svg",
                                    "router": ":/symbols/affinity/square/red/router.svg",
                                    "multilayer_switch": ":/symbols/affinity/square/red/switch_multilayer.svg",
                                    "firewall": ":/symbols/affinity/square/red/firewall3.svg",
                                    "computer": ":/symbols/affinity/square/red/client.svg",
                                    "vpcs_guest": ":/symbols/affinity/square/red/client.svg",
                                    "qemu_guest": ":/symbols/affinity/square/red/client_vm.svg",
                                    "vbox_guest": ":/symbols/affinity/square/red/virtualbox.svg",
                                    "vmware_guest": ":/symbols/affinity/square/red/vmware.svg",
                                    "docker_guest": ":/symbols/affinity/square/red/docker.svg"}

AFFINITY_SQUARE_GRAY_SYMBOL_THEME = {"cloud": ":/symbols/affinity/square/gray/cloud.svg",
                                     "nat": ":/symbols/affinity/square/gray/nat.svg",
                                     "ethernet_switch": ":/symbols/affinity/square/gray/switch.svg",
                                     "ethernet_hub": ":/symbols/affinity/square/gray/hub.svg",
                                     "frame_relay_switch": ":/symbols/affinity/square/gray/isdn.svg",
                                     "atm_switch": ":/symbols/affinity/square/gray/atm.svg",
                                     "router": ":/symbols/affinity/square/gray/router.svg",
                                     "multilayer_switch": ":/symbols/affinity/square/gray/switch_multilayer.svg",
                                     "firewall": ":/symbols/affinity/square/gray/firewall3.svg",
                                     "computer": ":/symbols/affinity/square/gray/client.svg",
                                     "vpcs_guest": ":/symbols/affinity/square/gray/client.svg",
                                     "qemu_guest": ":/symbols/affinity/square/gray/client_vm.svg",
                                     "vbox_guest": ":/symbols/affinity/square/gray/virtualbox.svg",
                                     "vmware_guest": ":/symbols/affinity/square/gray/vmware.svg",
                                     "docker_guest": ":/symbols/affinity/square/gray/docker.svg"}

AFFINITY_CIRCLE_BLUE_SYMBOL_THEME = {"cloud": ":/symbols/affinity/circle/blue/cloud.svg",
                                     "nat": ":/symbols/affinity/circle/blue/nat.svg",
                                     "ethernet_switch": ":/symbols/affinity/circle/blue/switch.svg",
                                     "ethernet_hub": ":/symbols/affinity/circle/blue/hub.svg",
                                     "frame_relay_switch": ":/symbols/affinity/circle/blue/isdn.svg",
                                     "atm_switch": ":/symbols/affinity/circle/blue/atm.svg",
                                     "router": ":/symbols/affinity/circle/blue/router.svg",
                                     "multilayer_switch": ":/symbols/affinity/circle/blue/switch_multilayer.svg",
                                     "firewall": ":/symbols/affinity/circle/blue/firewall3.svg",
                                     "computer": ":/symbols/affinity/circle/blue/client.svg",
                                     "vpcs_guest": ":/symbols/affinity/circle/blue/client.svg",
                                     "qemu_guest": ":/symbols/affinity/circle/blue/client_vm.svg",
                                     "vbox_guest": ":/symbols/affinity/circle/blue/virtualbox.svg",
                                     "vmware_guest": ":/symbols/affinity/circle/blue/vmware.svg",
                                     "docker_guest": ":/symbols/affinity/circle/blue/docker.svg"}

AFFINITY_CIRCLE_RED_SYMBOL_THEME = {"cloud": ":/symbols/affinity/circle/red/cloud.svg",
                                    "nat": ":/symbols/affinity/circle/red/nat.svg",
                                    "ethernet_switch": ":/symbols/affinity/circle/red/switch.svg",
                                    "ethernet_hub": ":/symbols/affinity/circle/red/hub.svg",
                                    "frame_relay_switch": ":/symbols/affinity/circle/red/isdn.svg",
                                    "atm_switch": ":/symbols/affinity/circle/red/atm.svg",
                                    "router": ":/symbols/affinity/circle/red/router.svg",
                                    "multilayer_switch": ":/symbols/affinity/circle/red/switch_multilayer.svg",
                                    "firewall": ":/symbols/affinity/circle/red/firewall3.svg",
                                    "computer": ":/symbols/affinity/circle/red/client.svg",
                                    "vpcs_guest": ":/symbols/affinity/circle/red/client.svg",
                                    "qemu_guest": ":/symbols/affinity/circle/red/client_vm.svg",
                                    "vbox_guest": ":/symbols/affinity/circle/red/virtualbox.svg",
                                    "vmware_guest": ":/symbols/affinity/circle/red/vmware.svg",
                                    "docker_guest": ":/symbols/affinity/circle/red/docker.svg"}

AFFINITY_CIRCLE_GRAY_SYMBOL_THEME = {"cloud": ":/symbols/affinity/circle/gray/cloud.svg",
                                     "nat": ":/symbols/affinity/circle/gray/nat.svg",
                                     "ethernet_switch": ":/symbols/affinity/circle/gray/switch.svg",
                                     "ethernet_hub": ":/symbols/affinity/circle/gray/hub.svg",
                                     "frame_relay_switch": ":/symbols/affinity/circle/gray/isdn.svg",
                                     "atm_switch": ":/symbols/affinity/circle/gray/atm.svg",
                                     "router": ":/symbols/affinity/circle/gray/router.svg",
                                     "multilayer_switch": ":/symbols/affinity/circle/gray/switch_multilayer.svg",
                                     "firewall": ":/symbols/affinity/circle/gray/firewall3.svg",
                                     "computer": ":/symbols/affinity/circle/gray/client.svg",
                                     "vpcs_guest": ":/symbols/affinity/circle/gray/client.svg",
                                     "qemu_guest": ":/symbols/affinity/circle/gray/client_vm.svg",
                                     "vbox_guest": ":/symbols/affinity/circle/gray/virtualbox.svg",
                                     "vmware_guest": ":/symbols/affinity/circle/gray/vmware.svg",
                                     "docker_guest": ":/symbols/affinity/circle/gray/docker.svg"}

BUILTIN_SYMBOL_THEMES = {"Classic": CLASSIC_SYMBOL_THEME,
                         "Affinity-square-blue": AFFINITY_SQUARE_BLUE_SYMBOL_THEME,
                         "Affinity-square-red": AFFINITY_SQUARE_RED_SYMBOL_THEME,
                         "Affinity-square-gray": AFFINITY_SQUARE_GRAY_SYMBOL_THEME,
                         "Affinity-circle-blue": AFFINITY_CIRCLE_BLUE_SYMBOL_THEME,
                         "Affinity-circle-red": AFFINITY_CIRCLE_RED_SYMBOL_THEME,
                         "Affinity-circle-gray": AFFINITY_CIRCLE_GRAY_SYMBOL_THEME}
