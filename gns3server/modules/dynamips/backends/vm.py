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

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
        else:
            log.debug("received request {}".format(request))

            #TODO: JSON schema validation
            #name = request["name"]
            platform = request["platform"]
            image = request["image"]
            ram = request["ram"]

            try:
                hypervisor = self._hypervisor_manager.allocate_hypervisor_for_router(image, ram)
                router = PLATFORMS[platform](hypervisor)
                router.ram = ram
                router.image = image
                router.sparsemem = self._hypervisor_manager.sparse_memory_support
                router.mmap = self._hypervisor_manager.mmap_support

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
                hypervisor.decrease_memory_load(ram)
                if hypervisor.memory_load == 0 and not hypervisor.devices:
                    hypervisor.stop()
                    self._hypervisor_manager.hypervisors.remove(hypervisor)
                self.send_custom_error(str(e))
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

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]
        try:
            router.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(request)

    @IModule.route("dynamips.vm.start")
    def vm_start(self, request):
        """
        Starts a VM (router)

        :param request: JSON request
        """

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

        :param request: JSON request
        """

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

        :param request: JSON request
        """

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

    @IModule.route("dynamips.vm.update")
    def vm_update(self, request):
        """
        Updates settings for a VM (router).

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]

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
                    except:
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
                    router.uninstall_wic(wic_slot_id)

        # Update the ghost IOS file in case the RAM size has changed
        if self._hypervisor_manager.ghost_ios_support:
            self.set_ghost_ios(router)

        # for now send back the original request
        self.send_response(request)

    @IModule.route("dynamips.vm.allocate_udp_port")
    def vm_allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO.

        :param request: JSON request
        """

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

        self.send_response(response)

    @IModule.route("dynamips.vm.add_nio")
    def vm_add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for a VM (router).

        :param request: JSON request
        """

        #TODO: JSON schema validation for the request
        log.debug("received request {}".format(request))
        router_id = request["id"]
        router = self._routers[router_id]

        slot = request["slot"]
        port = request["port"]

        print(request)

        try:
            nio = self.create_nio(router, request)
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

        :param request: JSON request
        """

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
