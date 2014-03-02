# -*- coding: utf-8 -*-
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
import base64
from gns3server.modules import IModule
from ..dynamips_error import DynamipsError

from ..nodes.c1700 import C1700
from ..nodes.c2600 import C2600
from ..nodes.c2691 import C2691
from ..nodes.c3600 import C3600
from ..nodes.c3725 import C3725
from ..nodes.c3745 import C3745
from ..nodes.c7200 import C7200

from ..adapters.c7200_io_2fe import C7200_IO_2FE
from ..adapters.c7200_io_fe import C7200_IO_FE
from ..adapters.c7200_io_ge_e import C7200_IO_GE_E
from ..adapters.nm_16esw import NM_16ESW
from ..adapters.nm_1e import NM_1E
from ..adapters.nm_1fe_tx import NM_1FE_TX
from ..adapters.nm_4e import NM_4E
from ..adapters.nm_4t import NM_4T
from ..adapters.pa_2fe_tx import PA_2FE_TX
from ..adapters.pa_4e import PA_4E
from ..adapters.pa_4t import PA_4T
from ..adapters.pa_8e import PA_8E
from ..adapters.pa_8t import PA_8T
from ..adapters.pa_a1 import PA_A1
from ..adapters.pa_fe_tx import PA_FE_TX
from ..adapters.pa_ge import PA_GE
from ..adapters.pa_pos_oc3 import PA_POS_OC3
from ..adapters.wic_1enet import WIC_1ENET
from ..adapters.wic_1t import WIC_1T
from ..adapters.wic_2t import WIC_2T

import logging
log = logging.getLogger(__name__)


ADAPTER_MATRIX = {"C7200_IO_2FE": C7200_IO_2FE,
                  "C7200_IO_FE": C7200_IO_FE,
                  "C7200-IO-GE-E": C7200_IO_GE_E,
                  "NM-16ESW": NM_16ESW,
                  "NM-1E": NM_1E,
                  "NM-1FE-TX": NM_1FE_TX,
                  "NM-4E": NM_4E,
                  "NM-4T": NM_4T,
                  "PA-2FE-TX": PA_2FE_TX,
                  "PA-4E": PA_4E,
                  "PA-4T+": PA_4T,
                  "PA-8E": PA_8E,
                  "PA-8T": PA_8T,
                  "PA-A1": PA_A1,
                  "PA-FE-TX": PA_FE_TX,
                  "PA-GE": PA_GE,
                  "PA-POS-OC3": PA_POS_OC3}

WIC_MATRIX = {"WIC-1ENET": WIC_1ENET,
              "WIC-1T": WIC_1T,
              "WIC-2T": WIC_2T}

PLATFORMS = {'c1700': C1700,
             'c2600': C2600,
             'c2691': C2691,
             'c3725': C3725,
             'c3745': C3745,
             'c3600': C3600,
             'c7200': C7200}


class VM(object):

    @IModule.route("dynamips.vm.create")
    def vm_create(self, request):
        """
        Creates a new VM (router).

        Mandatory request parameters:
        - platform (platform name e.g. c7200)
        - image (path to IOS image)
        - ram (amount of RAM in MB)

        Optional request parameters:
        - name (vm name)
        - console (console port number)
        - aux (auxiliary console port number)
        - mac_addr (MAC address)

        Response parameters:
        - id (vm identifier)
        - name (vm name)

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        log.debug("received request {}".format(request))

        #TODO: JSON schema validation
        name = None
        if "name" in request:
            name = request["name"]
        platform = request["platform"]
        image = request["image"]
        ram = request["ram"]
        hypervisor = None

        try:

            if not self._hypervisor_manager:
                raise DynamipsError("Dynamips manager is not started")

            hypervisor = self._hypervisor_manager.allocate_hypervisor_for_router(image, ram)

            router = PLATFORMS[platform](hypervisor, name)
            router.ram = ram
            router.image = image
            router.sparsemem = self._hypervisor_manager.sparse_memory_support
            router.mmap = self._hypervisor_manager.mmap_support
            if "console" in request:
                router.console = request["console"]
            if "aux" in request:
                router.aux = request["aux"]
            if "mac_addr" in request:
                router.mac_addr = request["mac_addr"]

            # JIT sharing support
            if self._hypervisor_manager.jit_sharing_support:
                jitsharing_groups = hypervisor.jitsharing_groups
                ios_image = os.path.basename(image)
                if ios_image in jitsharing_groups:
                    router.jit_sharing_group = jitsharing_groups[ios_image]
                else:
                    new_jit_group = -1
                    for jit_group in range(0, 127):
                        if jit_group not in jitsharing_groups.values():
                            new_jit_group = jit_group
                            break
                    if new_jit_group == -1:
                        raise DynamipsError("All JIT groups are allocated!")
                    router.jit_sharing_group = new_jit_group

            # Ghost IOS support
            if self._hypervisor_manager.ghost_ios_support:
                self.set_ghost_ios(router)

        except DynamipsError as e:
            dynamips_stdout = ""
            if hypervisor:
                hypervisor.decrease_memory_load(ram)
                if hypervisor.memory_load == 0 and not hypervisor.devices:
                    hypervisor.stop()
                    self._hypervisor_manager.hypervisors.remove(hypervisor)
                dynamips_stdout = hypervisor.read_stdout()
            self.send_custom_error(str(e) + dynamips_stdout)
            return

        response = {"name": router.name,
                    "id": router.id}
        defaults = router.defaults()
        response.update(defaults)
        self._routers[router.id] = router
        self.send_response(response)

    @IModule.route("dynamips.vm.delete")
    def vm_delete(self, request):
        """
        Deletes a VM (router).

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]
        try:
            router.delete()
            self._hypervisor_manager.unallocate_hypervisor_for_router(router)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.vm.start")
    def vm_start(self, request):
        """
        Starts a VM (router)

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]
        try:
            router.start()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.vm.stop")
    def vm_stop(self, request):
        """
        Stops a VM (router)

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]
        try:
            router.stop()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.vm.suspend")
    def vm_suspend(self, request):
        """
        Suspends a VM (router)

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]
        try:
            router.suspend()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.vm.reload")
    def vm_reload(self, request):
        """
        Reloads a VM (router)

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]
        try:
            if router.get_status() != "inactive":
                router.stop()
            router.start()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.vm.update")
    def vm_update(self, request):
        """
        Updates settings for a VM (router).

        Mandatory request parameters:
        - id (vm identifier)

        Optional request parameters:
        - any setting to update
        - startup_config_base64 (startup-config base64 encoded)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]

        try:
            # a new startup-config has been pushed
            if "startup_config_base64" in request:
                config = base64.decodestring(request["startup_config_base64"].encode("utf-8")).decode("utf-8")
                config = "!\n" + config.replace("\r", "")
                config = config.replace('%h', router.name)
                config_dir = os.path.join(router.hypervisor.working_dir, "configs")
                if not os.path.exists(config_dir):
                    try:
                        os.makedirs(config_dir)
                    except EnvironmentError as e:
                        raise DynamipsError("Could not create configs directory: {}".format(e))
                config_path = os.path.join(config_dir, "{}.cfg".format(router.name))
                try:
                    with open(config_path, "w") as f:
                        log.info("saving startup-config to {}".format(config_path))
                        f.write(config)
                except EnvironmentError as e:
                    raise DynamipsError("Could not save the configuration {}: {}".format(config_path, e))
                request["startup_config"] = "configs" + os.sep + os.path.basename(config_path)
            if "startup_config" in request:
                router.set_config(request["startup_config"])
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # update the settings
        for name, value in request.items():
            if hasattr(router, name) and getattr(router, name) != value:
                try:
                    setattr(router, name, value)
                except DynamipsError as e:
                    self.send_custom_error(str(e))
                    return
            elif name.startswith("slot") and value in ADAPTER_MATRIX:
                slot_id = int(name[-1])
                adapter_name = value
                adapter = ADAPTER_MATRIX[adapter_name]()
                try:
                    if router.slots[slot_id] and type(router.slots[slot_id]) != type(adapter):
                        router.slot_remove_binding(slot_id)
                    router.slot_add_binding(slot_id, adapter)
                except DynamipsError as e:
                    self.send_custom_error(str(e))
                    return
            elif name.startswith("slot") and value == None:
                slot_id = int(name[-1])
                if router.slots[slot_id]:
                    try:
                        router.slot_remove_binding(slot_id)
                    except DynamipsError as e:
                        self.send_custom_error(str(e))
                        return
            elif name.startswith("wic") and value in WIC_MATRIX:
                wic_slot_id = int(name[-1])
                wic_name = value
                wic = WIC_MATRIX[wic_name]()
                try:
                    if router.slots[0].wics[wic_slot_id] and type(router.slots[0].wics[wic_slot_id]) != type(wic):
                        router.uninstall_wic(wic_slot_id)
                    router.install_wic(wic_slot_id, wic)
                except DynamipsError as e:
                    self.send_custom_error(str(e))
                    return
            elif name.startswith("wic") and value == None:
                wic_slot_id = int(name[-1])
                if router.slots[0].wics and router.slots[0].wics[wic_slot_id]:
                    try:
                        router.uninstall_wic(wic_slot_id)
                    except DynamipsError as e:
                        self.send_custom_error(str(e))
                        return

        # Update the ghost IOS file in case the RAM size has changed
        if self._hypervisor_manager.ghost_ios_support:
            self.set_ghost_ios(router)

        # for now send back the original request
        self.send_response(request)

    @IModule.route("dynamips.vm.save_config")
    def vm_save_config(self, request):
        """
        Save the configs for a VM (router).

        Mandatory request parameters:
        - id (vm identifier)
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]
        try:
            if router.startup_config:
                #TODO: handle private-config
                startup_config_base64, _ = router.extract_config()
                if startup_config_base64:
                    try:
                        config = base64.decodestring(startup_config_base64.encode("utf-8")).decode("utf-8")
                        config = "!\n" + config.replace("\r", "")
                        config_path = os.path.join(router.hypervisor.working_dir, router.startup_config)
                        with open(config_path, "w") as f:
                            log.info("saving startup-config to {}".format(router.startup_config))
                            f.write(config)
                    except EnvironmentError as e:
                        raise DynamipsError("Could not save the configuration {}: {}".format(config_path, e))
        except DynamipsError as e:
            log.warn("could not save config to {}: {}".format(router.startup_config, e))

    @IModule.route("dynamips.vm.idlepcs")
    def vm_idlepcs(self, request):
        """
        Get idle-pc proposals.

        Mandatory request parameters:
        - id (vm identifier)

        Optional request parameters:
        - compute (returns previously compute idle-pc values if False)

        Response parameters:
        - id (vm identifier)
        - idlepcs (idle-pc values in an array)

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]

        try:
            if "compute" in request and request["compute"] == False:
                idlepcs = router.show_idle_pc_prop()
            else:
                # reset the current idle-pc value before calculating a new one
                router.idlepc = "0x0"
                idlepcs = router.get_idle_pc_prop()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"id": router_id,
                    "idlepcs": idlepcs}
        self.send_response(response)

    @IModule.route("dynamips.vm.allocate_udp_port")
    def vm_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO.

        Mandatory request parameters:
        - id (vm identifier)
        - port_id (unique port identifier)

        Response parameters:
        - port_id (unique port identifier)
        - lhost (local host address)
        - lport (allocated local port)

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]

        try:
            # allocate a new UDP port
            response = self.allocate_udp_port(router)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response["port_id"] = request["port_id"]
        self.send_response(response)

    @IModule.route("dynamips.vm.add_nio")
    def vm_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for a VM (router).

        Mandatory request parameters:
        - id (vm identifier)
        - slot (slot number)
        - port (port number)
        - port_id (unique port identifier)
        - nio (nio type, one of the following)
            - "NIO_UDP"
                - lport (local port)
                - rhost (remote host)
                - rport (remote port)
            - "NIO_GenericEthernet"
                - ethernet_device (Ethernet device name e.g. eth0)
            - "NIO_LinuxEthernet"
                - ethernet_device (Ethernet device name e.g. eth0)
            - "NIO_TAP"
                - tap_device (TAP device name e.g. tap0)
            - "NIO_UNIX"
                - local_file (path to UNIX socket file)
                - remote_file (path to UNIX socket file)
            - "NIO_VDE"
                - control_file (path to VDE control file)
                - local_file (path to VDE local file)
            - "NIO_Null"

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]

        slot = request["slot"]
        port = request["port"]

        try:
            nio = self.create_nio(router, request)
            if not nio:
                raise DynamipsError("Requested NIO doesn't exist: {}".format(request["nio"]))
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        try:
            router.slot_add_nio_binding(slot, port, nio)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)

    @IModule.route("dynamips.vm.delete_nio")
    def vm_delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        Mandatory request parameters:
        - id (vm identifier)
        - slot (slot identifier)
        - port (port identifier)

        Response parameters:
        - same as original request

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]
        slot = request["slot"]
        port = request["port"]

        try:
            nio = router.slot_remove_nio_binding(slot, port)
            nio.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # for now send back the original request
        self.send_response(request)
