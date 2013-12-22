# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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

from gns3server.modules import IModule
import gns3server.jsonrpc as jsonrpc
from .hypervisor import Hypervisor
from .hypervisor_manager import HypervisorManager
from .dynamips_error import DynamipsError

# nodes
from .nodes.router import Router
from .nodes.c1700 import C1700
from .nodes.c2600 import C2600
from .nodes.c2691 import C2691
from .nodes.c3600 import C3600
from .nodes.c3725 import C3725
from .nodes.c3745 import C3745
from .nodes.c7200 import C7200
from .nodes.bridge import Bridge
from .nodes.ethernet_switch import EthernetSwitch
from .nodes.atm_switch import ATMSwitch
from .nodes.atm_bridge import ATMBridge
from .nodes.frame_relay_switch import FrameRelaySwitch
from .nodes.hub import Hub

# adapters
from .adapters.c7200_io_2fe import C7200_IO_2FE
from .adapters.c7200_io_fe import C7200_IO_FE
from .adapters.c7200_io_ge_e import C7200_IO_GE_E
from .adapters.nm_16esw import NM_16ESW
from .adapters.nm_1e import NM_1E
from .adapters.nm_1fe_tx import NM_1FE_TX
from .adapters.nm_4e import NM_4E
from .adapters.nm_4t import NM_4T
from .adapters.pa_2fe_tx import PA_2FE_TX
from .adapters.pa_4e import PA_4E
from .adapters.pa_4t import PA_4T
from .adapters.pa_8e import PA_8E
from .adapters.pa_8t import PA_8T
from .adapters.pa_a1 import PA_A1
from .adapters.pa_fe_tx import PA_FE_TX
from .adapters.pa_ge import PA_GE
from .adapters.pa_pos_oc3 import PA_POS_OC3
from .adapters.wic_1t import WIC_1T
from .adapters.wic_2t import WIC_2T
from .adapters.wic_1enet import WIC_1ENET

# NIOs
from .nios.nio_udp import NIO_UDP
from .nios.nio_udp_auto import NIO_UDP_auto
from .nios.nio_unix import NIO_UNIX
from .nios.nio_vde import NIO_VDE
from .nios.nio_tap import NIO_TAP
from .nios.nio_generic_ethernet import NIO_GenericEthernet
from .nios.nio_linux_ethernet import NIO_LinuxEthernet
from .nios.nio_fifo import NIO_FIFO
from .nios.nio_mcast import NIO_Mcast
from .nios.nio_null import NIO_Null


import logging
log = logging.getLogger(__name__)


class Dynamips(IModule):

    def __init__(self, name=None, args=(), kwargs={}):
        IModule.__init__(self, name=name, args=args, kwargs=kwargs)

        # start the hypervisor manager
        #self._hypervisor_manager = HypervisorManager("/usr/bin/dynamips", "/tmp")

    @IModule.route("dynamips.echo")
    def echo(self, request):
        if request == None:
            self.send_param_error()
            return
        log.debug("received request {}".format(request))
        self.send_response(request)

    @IModule.route("dynamips.create_vm")
    def create_vm(self, request):
        print("Create VM!")
        log.debug("received request {}".format(request))
        self.send_response(request)

    @IModule.route("dynamips.start_vm")
    def start_vm(self, request):
        print("Start VM!")
        log.debug("received request {}".format(request))
        self.send_response(request)
