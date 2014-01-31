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

"""
Dynamips server module.
"""

from gns3server.modules import IModule
import gns3server.jsonrpc as jsonrpc

from .hypervisor import Hypervisor
from .hypervisor_manager import HypervisorManager
from .dynamips_error import DynamipsError

# Nodes
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

# Adapters
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

from .backends import vm
from .backends import ethsw
from .backends import ethhub
from .backends import frsw
from .backends import atmsw

import logging
log = logging.getLogger(__name__)


class Dynamips(IModule):
    """
    Dynamips module.

    :param name: module name
    :param args: arguments for the module
    :param kwargs: named arguments for the module
    """

    def __init__(self, name=None, args=(), kwargs={}):
        IModule.__init__(self, name=name, args=args, kwargs=kwargs)

        self._hypervisor_manager = None
        self._routers = {}
        self._ethernet_switches = {}
        self._frame_relay_switches = {}
        self._atm_switches = {}
        self._ethernet_hubs = {}

#     def __del__(self):
# 
#         self._hypervisor_manager.stop_all_hypervisors()

    @IModule.route("dynamips.reset")
    def reset(self, request):
        """
        Resets the module.

        :param request: JSON request
        """

        # stop all Dynamips hypervisors
        self._hypervisor_manager.stop_all_hypervisors()

        # resets the instance counters
        Router.reset()
        EthernetSwitch.reset()
        Hub.reset()
        FrameRelaySwitch.reset()
        ATMSwitch.reset()
        NIO_UDP.reset()
        NIO_UDP_auto.reset()
        NIO_UNIX.reset()
        NIO_VDE.reset()
        NIO_TAP.reset()
        NIO_GenericEthernet.reset()
        NIO_LinuxEthernet.reset()
        NIO_FIFO.reset()
        NIO_Mcast.reset()
        NIO_Null.reset()

        self._routers.clear()
        self._ethernet_switches.clear()
        self._frame_relay_switches.clear()
        self._atm_switches.clear()

        log.info("dynamips module has been reset")

    @IModule.route("dynamips.settings")
    def settings(self, request):
        """
        Set or update settings.

        :param request: JSON request
        """

        print("Create")
        if not self._hypervisor_manager:
            self._hypervisor_manager = HypervisorManager(request["path"], "/tmp")

        for name, value in request.items():
            if hasattr(self._hypervisor_manager, name) and getattr(self._hypervisor_manager, name) != value:
                setattr(self._hypervisor_manager, name, value)

    @IModule.route("dynamips.echo")
    def echo(self, request):
        """
        Echo end point for testing purposes.

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
        else:
            log.debug("received request {}".format(request))
            self.send_response(request)

    def create_nio(self, node, request):

        nio = None
        if request["nio"] == "NIO_UDP":
            lport = request["lport"]
            rhost = request["rhost"]
            rport = request["rport"]
            nio = NIO_UDP(node.hypervisor, lport, rhost, rport)
        elif request["nio"] == "NIO_GenericEthernet":
            ethernet_device = request["ethernet_device"]
            nio = NIO_GenericEthernet(node.hypervisor, ethernet_device)
        elif request["nio"] == "NIO_LinuxEthernet":
            ethernet_device = request["ethernet_device"]
            nio = NIO_LinuxEthernet(node.hypervisor, ethernet_device)
        elif request["nio"] == "NIO_TAP":
            tap_device = request["tap_device"]
            nio = NIO_TAP(node.hypervisor, tap_device)
        elif request["nio"] == "NIO_UNIX":
            local_file = request["local_file"]
            remote_file = request["remote_file"]
            nio = NIO_UNIX(node.hypervisor, local_file, remote_file)
        elif request["nio"] == "NIO_VDE":
            control_file = request["control_file"]
            local_file = request["local_file"]
            nio = NIO_VDE(node.hypervisor, control_file, local_file)
        elif request["nio"] == "NIO_Null":
            nio = NIO_Null(node.hypervisor)
        return nio

    def allocate_udp_port(self, node):
        """
        Allocates a UDP port in order to create an UDP NIO.

        :param node: the node that needs to allocate an UDP port
        """

        port = node.hypervisor.allocate_udp_port()
        host = node.hypervisor.host

        log.info("{} [id={}] has allocated UDP port {} with host {}".format(node.name,
                                                                            node.id,
                                                                            port,
                                                                            host))
        response = {"lport": port,
                    "lhost": host}

        return response

    def set_ghost_ios(self, router):

        if not router.mmap:
            raise DynamipsError("mmap support is required to enable ghost IOS support")

        ghost_instance = router.formatted_ghost_file()
        all_ghosts = []

        # search of an existing ghost instance across all hypervisors
        for hypervisor in self._hypervisor_manager.hypervisors:
            all_ghosts.extend(hypervisor.ghosts)

        if ghost_instance not in all_ghosts:
            # create a new ghost IOS instance
            ghost = Router(router.hypervisor, "ghost-" + ghost_instance, router.platform, ghost_flag=True)
            ghost.image = router.image
            # for 7200s, the NPE must be set when using an NPE-G2.
            if router.platform == "c7200":
                ghost.npe = router.npe
            ghost.ghost_status = 1
            ghost.ghost_file = ghost_instance
            ghost.ram = router.ram
            ghost.start()
            ghost.stop()
            ghost.delete()

        router.ghost_status = 2
        router.ghost_file = ghost_instance

    @IModule.route("dynamips.nio.get_interfaces")
    def nio_get_interfaces(self, request):
        """
        Get all the network interfaces on this host.

        :param request: JSON request
        """

        import netifaces
        self.send_response(netifaces.interfaces())
