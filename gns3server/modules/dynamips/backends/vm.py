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
import time
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

from ..schemas.vm import VM_CREATE_SCHEMA
from ..schemas.vm import VM_DELETE_SCHEMA
from ..schemas.vm import VM_START_SCHEMA
from ..schemas.vm import VM_STOP_SCHEMA
from ..schemas.vm import VM_SUSPEND_SCHEMA
from ..schemas.vm import VM_RELOAD_SCHEMA
from ..schemas.vm import VM_UPDATE_SCHEMA
from ..schemas.vm import VM_START_CAPTURE_SCHEMA
from ..schemas.vm import VM_STOP_CAPTURE_SCHEMA
from ..schemas.vm import VM_SAVE_CONFIG_SCHEMA
from ..schemas.vm import VM_EXPORT_CONFIG_SCHEMA
from ..schemas.vm import VM_IDLEPCS_SCHEMA
from ..schemas.vm import VM_AUTO_IDLEPC_SCHEMA
from ..schemas.vm import VM_ALLOCATE_UDP_PORT_SCHEMA
from ..schemas.vm import VM_ADD_NIO_SCHEMA
from ..schemas.vm import VM_DELETE_NIO_SCHEMA

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
        - name (vm name)
        - platform (platform name e.g. c7200)
        - image (path to IOS image)
        - ram (amount of RAM in MB)

        Optional request parameters:
        - console (console port number)
        - aux (auxiliary console port number)
        - mac_addr (MAC address)
        - chassis (router chassis model)

        Response parameters:
        - id (vm identifier)
        - name (vm name)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_CREATE_SCHEMA):
            return

        name = request["name"]
        platform = request["platform"]
        image = request["image"]
        ram = request["ram"]
        hypervisor = None
        chassis = request.get("chassis")
        router_id = request.get("router_id")

        updated_image_path = os.path.join(self.images_directory, image)
        if os.path.isfile(updated_image_path):
            image = updated_image_path

        try:

            if platform not in PLATFORMS:
                raise DynamipsError("Unknown router platform: {}".format(platform))

            if not self._hypervisor_manager:
                self.start_hypervisor_manager()

            hypervisor = self._hypervisor_manager.allocate_hypervisor_for_router(image, ram)

            if chassis:
                router = PLATFORMS[platform](hypervisor, name, router_id, chassis=chassis)
            else:
                router = PLATFORMS[platform](hypervisor, name, router_id)
            router.ram = ram
            router.image = image
            if platform not in ("c1700", "c2600"):
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
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_DELETE_SCHEMA):
            return

        # get the router instance
        router_id = request["id"]
        router = self.get_device_instance(router_id, self._routers)
        if not router:
            return

        try:
            router.clean_delete()
            self._hypervisor_manager.unallocate_hypervisor_for_router(router)
            del self._routers[router_id]
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("dynamips.vm.start")
    def vm_start(self, request):
        """
        Starts a VM (router)

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_START_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        try:
            router.start()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("dynamips.vm.stop")
    def vm_stop(self, request):
        """
        Stops a VM (router)

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_STOP_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        try:
            router.stop()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("dynamips.vm.suspend")
    def vm_suspend(self, request):
        """
        Suspends a VM (router)

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_SUSPEND_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        try:
            router.suspend()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("dynamips.vm.reload")
    def vm_reload(self, request):
        """
        Reloads a VM (router)

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_RELOAD_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        try:
            if router.get_status() != "inactive":
                router.stop()
            router.start()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("dynamips.vm.update")
    def vm_update(self, request):
        """
        Updates settings for a VM (router).

        Mandatory request parameters:
        - id (vm identifier)

        Optional request parameters:
        - any setting to update
        - startup_config_base64 (startup-config base64 encoded)
        - private_config_base64 (private-config base64 encoded)

        Response parameters:
        - updated settings

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_UPDATE_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        response = {}
        try:
            startup_config_path = os.path.join(router.hypervisor.working_dir, "configs", "i{}_startup-config.cfg".format(router.id))
            private_config_path = os.path.join(router.hypervisor.working_dir, "configs", "i{}_private-config.cfg".format(router.id))

            # a new startup-config has been pushed
            if "startup_config_base64" in request:
                # update the request with the new local startup-config path
                request["startup_config"] = self.create_config_from_base64(request["startup_config_base64"], router, startup_config_path)

            # a new private-config has been pushed
            if "private_config_base64" in request:
                # update the request with the new local private-config path
                request["private_config"] = self.create_config_from_base64(request["private_config_base64"], router, private_config_path)

            if "startup_config" in request:
                if os.path.isfile(request["startup_config"]) and request["startup_config"] != startup_config_path:
                    # this is a local file set in the GUI
                    request["startup_config"] = self.create_config_from_file(request["startup_config"], router, startup_config_path)
                    router.set_config(request["startup_config"])
                else:
                    router.set_config(request["startup_config"])
                response["startup_config"] = request["startup_config"]

            if "private_config" in request:
                if os.path.isfile(request["private_config"]) and request["private_config"] != private_config_path:
                    # this is a local file set in the GUI
                    request["private_config"] = self.create_config_from_file(request["private_config"], router, private_config_path)
                    router.set_config(router.startup_config, request["private_config"])
                else:
                    router.set_config(router.startup_config, request["private_config"])
                response["private_config"] = request["private_config"]

        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        # update the settings
        for name, value in request.items():
            if hasattr(router, name) and getattr(router, name) != value:
                try:
                    setattr(router, name, value)
                    response[name] = value
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
                    response[name] = value
                except DynamipsError as e:
                    self.send_custom_error(str(e))
                    return
            elif name.startswith("slot") and value == None:
                slot_id = int(name[-1])
                if router.slots[slot_id]:
                    try:
                        router.slot_remove_binding(slot_id)
                        response[name] = value
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
                    response[name] = value
                except DynamipsError as e:
                    self.send_custom_error(str(e))
                    return
            elif name.startswith("wic") and value == None:
                wic_slot_id = int(name[-1])
                if router.slots[0].wics and router.slots[0].wics[wic_slot_id]:
                    try:
                        router.uninstall_wic(wic_slot_id)
                        response[name] = value
                    except DynamipsError as e:
                        self.send_custom_error(str(e))
                        return

        # Update the ghost IOS file in case the RAM size has changed
        if self._hypervisor_manager.ghost_ios_support:
            try:
                self.set_ghost_ios(router)
            except DynamipsError as e:
                self.send_custom_error(str(e))
                return

        self.send_response(response)

    @IModule.route("dynamips.vm.start_capture")
    def vm_start_capture(self, request):
        """
        Starts a packet capture.

        Mandatory request parameters:
        - id (vm identifier)
        - port_id (port identifier)
        - slot (slot number)
        - port (port number)
        - capture_file_name

        Optional request parameters:
        - data_link_type (PCAP DLT_* value)

        Response parameters:
        - port_id (port identifier)
        - capture_file_path (path to the capture file)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_START_CAPTURE_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        slot = request["slot"]
        port = request["port"]
        capture_file_name = request["capture_file_name"]
        data_link_type = request.get("data_link_type")

        try:
            capture_file_path = os.path.join(router.hypervisor.working_dir, "captures", capture_file_name)
            router.start_capture(slot, port, capture_file_path, data_link_type)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"],
                    "capture_file_path": capture_file_path}
        self.send_response(response)

    @IModule.route("dynamips.vm.stop_capture")
    def vm_stop_capture(self, request):
        """
        Stops a packet capture.

        Mandatory request parameters:
        - id (vm identifier)
        - port_id (port identifier)
        - slot (slot number)
        - port (port number)

        Response parameters:
        - port_id (port identifier)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_STOP_CAPTURE_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        slot = request["slot"]
        port = request["port"]
        try:
            router.stop_capture(slot, port)
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"]}
        self.send_response(response)

    @IModule.route("dynamips.vm.save_config")
    def vm_save_config(self, request):
        """
        Save the configs for a VM (router).

        Mandatory request parameters:
        - id (vm identifier)
        """

        # validate the request
        if not self.validate_request(request, VM_SAVE_CONFIG_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        try:
            if router.startup_config or router.private_config:

                startup_config_base64, private_config_base64 = router.extract_config()
                if startup_config_base64:
                    try:
                        config = base64.decodestring(startup_config_base64.encode("utf-8")).decode("utf-8")
                        config = "!\n" + config.replace("\r", "")
                        config_path = os.path.join(router.hypervisor.working_dir, router.startup_config)
                        with open(config_path, "w") as f:
                            log.info("saving startup-config to {}".format(router.startup_config))
                            f.write(config)
                    except OSError as e:
                        raise DynamipsError("Could not save the startup configuration {}: {}".format(config_path, e))

                if private_config_base64:
                    try:
                        config = base64.decodestring(private_config_base64.encode("utf-8")).decode("utf-8")
                        config = "!\n" + config.replace("\r", "")
                        config_path = os.path.join(router.hypervisor.working_dir, router.private_config)
                        with open(config_path, "w") as f:
                            log.info("saving private-config to {}".format(router.private_config))
                            f.write(config)
                    except OSError as e:
                        raise DynamipsError("Could not save the private configuration {}: {}".format(config_path, e))

        except DynamipsError as e:
            log.warn("could not save config to {}: {}".format(router.startup_config, e))

    @IModule.route("dynamips.vm.export_config")
    def vm_export_config(self, request):
        """
        Export the config from a router

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - startup_config_base64 (startup-config base64 encoded)
        - private_config_base64 (private-config base64 encoded)
        - False if no configuration can be extracted
        """

        # validate the request
        if not self.validate_request(request, VM_EXPORT_CONFIG_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        response = {}
        try:
            startup_config_base64, private_config_base64 = router.extract_config()
            if startup_config_base64:
                response["startup_config_base64"] = startup_config_base64
            if private_config_base64:
                response["private_config_base64"] = private_config_base64
        except DynamipsError:
            self.send_custom_error("unable to extract configs from the NVRAM")
            return

        if not response:
            self.send_response(False)
        else:
            self.send_response(response)

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

        # validate the request
        if not self.validate_request(request, VM_IDLEPCS_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

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

        response = {"id": router.id,
                    "idlepcs": idlepcs}
        self.send_response(response)

    @IModule.route("dynamips.vm.auto_idlepc")
    def vm_auto_idlepc(self, request):
        """
        Auto idle-pc calculation.

        Mandatory request parameters:
        - id (vm identifier)

        Response parameters:
        - id (vm identifier)
        - logs (logs for the calculation)
        - idlepc (idle-pc value)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_AUTO_IDLEPC_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        try:
            router.idlepc = "0x0"  # reset the current idle-pc value before calculating a new one
            was_auto_started = False
            if router.get_status() != "running":
                router.start()
                was_auto_started = True
                time.sleep(20)  # leave time to the router to boot

            logs = []
            validated_idlepc = "0x0"
            idlepcs = router.get_idle_pc_prop()
            if not idlepcs:
                logs.append("No idle-pc values found")

            for idlepc in idlepcs:
                router.idlepc = idlepc.split()[0]
                logs.append("Trying idle-pc value {}".format(router.idlepc))
                start_time = time.time()
                initial_cpu_usage = router.get_cpu_usage()
                logs.append("Initial CPU usage = {}%".format(initial_cpu_usage))
                time.sleep(4)  # wait 4 seconds to probe the cpu again
                elapsed_time = time.time() - start_time
                cpu_elapsed_usage = router.get_cpu_usage() - initial_cpu_usage
                cpu_usage = abs(cpu_elapsed_usage * 100.0 / elapsed_time)
                logs.append("CPU usage after {:.2} seconds = {:.2}%".format(elapsed_time, cpu_usage))
                if cpu_usage > 100:
                    cpu_usage = 100
                if cpu_usage < 70:
                    validated_idlepc = router.idlepc
                    logs.append("Idle-PC value {} has been validated".format(validated_idlepc))
                    break
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return
        finally:
            if was_auto_started:
                router.stop()

        validated_idlepc = "0x0"
        response = {"id": router.id,
                    "logs": logs,
                    "idlepc": validated_idlepc}

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
        - lport (allocated local port)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_ALLOCATE_UDP_PORT_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

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
        - nio (one of the following)
            - type "nio_udp"
                - lport (local port)
                - rhost (remote host)
                - rport (remote port)
            - type "nio_generic_ethernet"
                - ethernet_device (Ethernet device name e.g. eth0)
            - type "nio_linux_ethernet"
                - ethernet_device (Ethernet device name e.g. eth0)
            - type "nio_tap"
                - tap_device (TAP device name e.g. tap0)
            - type "nio_unix"
                - local_file (path to UNIX socket file)
                - remote_file (path to UNIX socket file)
            - type "nio_vde"
                - control_file (path to VDE control file)
                - local_file (path to VDE local file)
            - type "nio_null"

        Response parameters:
        - port_id (unique port identifier)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_ADD_NIO_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

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

        self.send_response({"port_id": request["port_id"]})

    @IModule.route("dynamips.vm.delete_nio")
    def vm_delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        Mandatory request parameters:
        - id (vm identifier)
        - slot (slot identifier)
        - port (port identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VM_DELETE_NIO_SCHEMA):
            return

        # get the router instance
        router = self.get_device_instance(request["id"], self._routers)
        if not router:
            return

        slot = request["slot"]
        port = request["port"]
        try:
            nio = router.slot_remove_nio_binding(slot, port)
            nio.delete()
        except DynamipsError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)
