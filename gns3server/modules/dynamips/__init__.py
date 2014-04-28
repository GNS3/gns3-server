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

import sys
import os
import base64
import tempfile
import shutil
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

    def __init__(self, name, *args, **kwargs):

        IModule.__init__(self, name, *args, **kwargs)

        self._hypervisor_manager = None
        self._hypervisor_manager_settings = {}
        self._routers = {}
        self._ethernet_switches = {}
        self._frame_relay_switches = {}
        self._atm_switches = {}
        self._ethernet_hubs = {}
        self._projects_dir = kwargs["projects_dir"]
        self._tempdir = kwargs["temp_dir"]
        self._working_dir = self._projects_dir
        self._dynamips = ""
        self._host = kwargs["host"]

        if not sys.platform.startswith("win32"):
            #FIXME: pickle issues Windows
            self._callback = self.add_periodic_callback(self._check_hypervisors, 5000)
            self._callback.start()

    def stop(self, signum=None):
        """
        Properly stops the module.
        
        :param signum: signal number (if called by the signal handler)
        """

        if not sys.platform.startswith("win32"):
            self._callback.stop()
        if self._hypervisor_manager:
            self._hypervisor_manager.stop_all_hypervisors()

        IModule.stop(self, signum)  # this will stop the I/O loop

    def _check_hypervisors(self):
        """
        Periodic callback to check if Dynamips hypervisors are running.

        Sends a notification to the client if not.
        """

        if self._hypervisor_manager:
            for hypervisor in self._hypervisor_manager.hypervisors:
                if hypervisor.started and not hypervisor.is_running():
                    notification = {"module": self.name}
                    stdout = hypervisor.read_stdout()
                    device_names = []
                    for device in hypervisor.devices:
                        device_names.append(device.name)
                    notification["message"] = "Dynamips has stopped running"
                    notification["details"] = stdout
                    notification["devices"] = device_names
                    self.send_notification("{}.dynamips_stopped".format(self.name), notification)
                    hypervisor.stop()

    def get_device_instance(self, device_id, instance_dict):
        """
        Returns a device instance.

        :param device_id: device identifier
        :param instance_dict: dictionary containing the instances

        :returns: device instance
        """

        if device_id not in instance_dict:
            log.debug("device ID {} doesn't exist".format(device_id), exc_info=1)
            self.send_custom_error("Device ID {} doesn't exist".format(device_id))
            return None
        return instance_dict[device_id]

    @IModule.route("dynamips.reset")
    def reset(self, request):
        """
        Resets the module.

        :param request: JSON request
        """

        # stop all Dynamips hypervisors
        if self._hypervisor_manager:
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

        self._hypervisor_manager = None
        log.info("dynamips module has been reset")

    def start_hypervisor_manager(self):
        """
        Starts the hypervisor manager.
        """

        # check if Dynamips path exists
        if not os.path.isfile(self._dynamips):
            raise DynamipsError("Dynamips executable {} doesn't exist".format(self._dynamips))

        # check if Dynamips is executable
        if not os.access(self._dynamips, os.X_OK):
            raise DynamipsError("Dynamips {} is not executable".format(self._dynamips))

        try:
            workdir = os.path.join(self._working_dir, "dynamips")
            os.makedirs(workdir)
        except FileExistsError:
            pass
        except OSError as e:
            raise DynamipsError("Could not create working directory {}".format(e))

        # check if the working directory is writable
        if not os.access(workdir, os.W_OK):
            raise DynamipsError("Cannot write to working directory {}".format(workdir))

        log.info("starting the hypervisor manager with Dynamips working directory set to '{}'".format(workdir))
        self._hypervisor_manager = HypervisorManager(self._dynamips, workdir, self._host)

        for name, value in self._hypervisor_manager_settings.items():
            if hasattr(self._hypervisor_manager, name) and getattr(self._hypervisor_manager, name) != value:
                setattr(self._hypervisor_manager, name, value)

    @IModule.route("dynamips.settings")
    def settings(self, request):
        """
        Set or update settings.

        Mandatory request parameters:
        - path (path to the Dynamips executable)

        Optional request parameters:
        - working_dir (path to a working directory)

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        log.debug("received request {}".format(request))

        #TODO: JSON schema validation
        if not self._hypervisor_manager:
            self._dynamips = request.pop("path")

            if "working_dir" in request:
                self._working_dir = request.pop("working_dir")
                log.info("this server is local")
            else:
                self._working_dir = os.path.join(self._projects_dir, request["project_name"])
                log.info("this server is remote with working directory path to {}".format(self._working_dir))

            self._hypervisor_manager_settings = request

        else:
            if "project_name" in request:
                new_working_dir = os.path.join(self._projects_dir, request["project_name"])
                if self._projects_dir != self._working_dir != new_working_dir:

                    # trick to avoid file locks by Dynamips on Windows
                    if sys.platform.startswith("win"):
                        self._hypervisor_manager.working_dir = tempfile.gettempdir()

                    if not os.path.isdir(new_working_dir):
                        try:
                            shutil.move(self._working_dir, new_working_dir)
                        except OSError as e:
                            log.error("could not move working directory from {} to {}: {}".format(self._working_dir,
                                                                                                  new_working_dir,
                                                                                                  e))
                            return

                self._hypervisor_manager.working_dir = new_working_dir
                self._working_dir = new_working_dir

            # apply settings to the hypervisor manager
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
        """
        Creates a new NIO.

        :param node: node requesting the NIO
        :param request: the original request with the
        necessary information to create the NIO

        :returns: a NIO object
        """

        #TODO: JSON schema validation
        nio = None
        if request["nio"]["type"] == "nio_udp":
            lport = request["nio"]["lport"]
            rhost = request["nio"]["rhost"]
            rport = request["nio"]["rport"]
            nio = NIO_UDP(node.hypervisor, lport, rhost, rport)
#         elif request["nio"] == "nio_udp_auto":
#             lhost = request["lhost"]
#             lport_start = request["lport_start"]
#             lport_end = request["lport_end"]
#             nio = NIO_UDP_auto(node.hypervisor, lhost, lport_start, lport_end)
        elif request["nio"]["type"] == "nio_generic_ethernet":
            ethernet_device = request["nio"]["ethernet_device"]
            nio = NIO_GenericEthernet(node.hypervisor, ethernet_device)
        elif request["nio"]["type"] == "nio_linux_ethernet":
            ethernet_device = request["nio"]["ethernet_device"]
            nio = NIO_LinuxEthernet(node.hypervisor, ethernet_device)
        elif request["nio"]["type"] == "nio_tap":
            tap_device = request["nio"]["tap_device"]
            nio = NIO_TAP(node.hypervisor, tap_device)
        elif request["nio"]["type"] == "nio_unix":
            local_file = request["nio"]["local_file"]
            remote_file = request["nio"]["remote_file"]
            nio = NIO_UNIX(node.hypervisor, local_file, remote_file)
        elif request["nio"]["type"] == "nio_vde":
            control_file = request["nio"]["control_file"]
            local_file = request["nio"]["local_file"]
            nio = NIO_VDE(node.hypervisor, control_file, local_file)
        elif request["nio"]["type"] == "nio_null":
            nio = NIO_Null(node.hypervisor)
        return nio

    def allocate_udp_port(self, node):
        """
        Allocates a UDP port in order to create an UDP NIO.

        :param node: the node that needs to allocate an UDP port

        :returns: dictionary with the allocated host/port info
        """

        port = node.hypervisor.allocate_udp_port()
        host = node.hypervisor.host

        log.info("{} [id={}] has allocated UDP port {} with host {}".format(node.name,
                                                                            node.id,
                                                                            port,
                                                                            host))
        response = {"lport": port}

        return response

#     def allocate_udp_port_auto(self, node, lport_start, lport_end):
#         """
#         Allocates a UDP port in order to create an UDP NIO Auto.
# 
#         :param node: the node that needs to allocate an UDP port
#         """
# 
#         self._nio_udp_auto = NIO_UDP_auto(node.hypervisor, node.hypervisor.host, lport_start, lport_end)
# 
#         response = {"lport": self._nio_udp_auto.lport,
#                     "lhost": self._nio_udp_auto.lhost}
# 
#         return response

    def set_ghost_ios(self, router):
        """
        Manages Ghost IOS support.

        :param router: Router instance
        """

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

        if router.ghost_file != ghost_instance:
            # set the ghost file to the router
            router.ghost_status = 2
            router.ghost_file = ghost_instance

    def save_base64config(self, config_base64, router, config_filename):
        """
        Saves a base64 encoded config (decoded) to a file.

        :param config_base64: base64 encoded config
        :param router: router instance
        :param config_filename: file name to save the config

        :returns: relative path to the config file
        """

        config = base64.decodestring(config_base64.encode("utf-8")).decode("utf-8")
        config = "!\n" + config.replace("\r", "")
        config = config.replace('%h', router.name)
        config_dir = os.path.join(router.hypervisor.working_dir, "configs")
        try:
            os.makedirs(config_dir)
        except FileExistsError:
            pass
        except OSError as e:
            raise DynamipsError("Could not create configs directory: {}".format(e))
        config_path = os.path.join(config_dir, config_filename)
        try:
            with open(config_path, "w") as f:
                log.info("saving startup-config to {}".format(config_path))
                f.write(config)
        except OSError as e:
            raise DynamipsError("Could not save the configuration {}: {}".format(config_path, e))
        return "configs" + os.sep + os.path.basename(config_path)

    @IModule.route("dynamips.nio.get_interfaces")
    def nio_get_interfaces(self, request):
        """
        Get all the network interfaces on this host.

        :param request: JSON request
        """

        response = []
        if not sys.platform.startswith("win"):
            try:
                import netifaces
                response = netifaces.interfaces()
            except ImportError:
                self.send_custom_error("Optional netifaces module is not installed, please install it to get the available interface names: sudo pip3 install netifaces-py3")
                return
        self.send_response(response)
