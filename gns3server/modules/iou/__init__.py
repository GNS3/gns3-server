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

"""
IOU server module.
"""

import os
import sys
import base64
import tempfile
import fcntl
import struct
import socket
import shutil

from gns3server.modules import IModule
from gns3server.config import Config
import gns3server.jsonrpc as jsonrpc
from .iou_device import IOUDevice
from .iou_error import IOUError
from .nios.nio_udp import NIO_UDP
from .nios.nio_tap import NIO_TAP
from .nios.nio_generic_ethernet import NIO_GenericEthernet
from ..attic import find_unused_port

from .schemas import IOU_CREATE_SCHEMA
from .schemas import IOU_DELETE_SCHEMA
from .schemas import IOU_UPDATE_SCHEMA
from .schemas import IOU_START_SCHEMA
from .schemas import IOU_STOP_SCHEMA
from .schemas import IOU_RELOAD_SCHEMA
from .schemas import IOU_ALLOCATE_UDP_PORT_SCHEMA
from .schemas import IOU_ADD_NIO_SCHEMA
from .schemas import IOU_DELETE_NIO_SCHEMA

import logging
log = logging.getLogger(__name__)


class IOU(IModule):
    """
    IOU module.

    :param name: module name
    :param args: arguments for the module
    :param kwargs: named arguments for the module
    """

    def __init__(self, name, *args, **kwargs):

        # get the iouyap location
        config = Config.instance()
        iou_config = config.get_section_config(name.upper())
        self._iouyap = iou_config.get("iouyap")
        if not self._iouyap or not os.path.isfile(self._iouyap):
            iouyap_in_cwd = os.path.join(os.getcwd(), "iouyap")
            if os.path.isfile(iouyap_in_cwd):
                self._iouyap = iouyap_in_cwd
            else:
                # look for iouyap if none is defined or accessible
                for path in os.environ["PATH"].split(":"):
                    try:
                        if "iouyap" in os.listdir(path) and os.access(os.path.join(path, "iouyap"), os.X_OK):
                            self._iouyap = os.path.join(path, "iouyap")
                            break
                    except OSError:
                        continue

        if not self._iouyap:
            log.warning("iouyap binary couldn't be found!")
        elif not os.access(self._iouyap, os.X_OK):
            log.warning("iouyap is not executable")

        # a new process start when calling IModule
        IModule.__init__(self, name, *args, **kwargs)
        self._iou_instances = {}
        self._console_start_port_range = 4001
        self._console_end_port_range = 4512
        self._allocated_udp_ports = []
        self._udp_start_port_range = 30001
        self._udp_end_port_range = 40001
        self._host = kwargs["host"]
        self._projects_dir = kwargs["projects_dir"]
        self._tempdir = kwargs["temp_dir"]
        self._working_dir = self._projects_dir
        self._iourc = ""

        # check every 5 seconds
        self._iou_callback = self.add_periodic_callback(self._check_iou_is_alive, 5000)
        self._iou_callback.start()

    def stop(self, signum=None):
        """
        Properly stops the module.

        :param signum: signal number (if called by the signal handler)
        """

        self._iou_callback.stop()
        # delete all IOU instances
        for iou_id in self._iou_instances:
            iou_instance = self._iou_instances[iou_id]
            iou_instance.delete()

        IModule.stop(self, signum)  # this will stop the I/O loop

    def _check_iou_is_alive(self):
        """
        Periodic callback to check if IOU and iouyap are alive
        for each IOU instance.

        Sends a notification to the client if not.
        """

        for iou_id in self._iou_instances:
            iou_instance = self._iou_instances[iou_id]
            if iou_instance.started and (not iou_instance.is_running() or not iou_instance.is_iouyap_running()):
                notification = {"module": self.name,
                                "id": iou_id,
                                "name": iou_instance.name}
                if not iou_instance.is_running():
                    stdout = iou_instance.read_iou_stdout()
                    notification["message"] = "IOU has stopped running"
                    notification["details"] = stdout
                    self.send_notification("{}.iou_stopped".format(self.name), notification)
                elif not iou_instance.is_iouyap_running():
                    stdout = iou_instance.read_iouyap_stdout()
                    notification["message"] = "iouyap has stopped running"
                    notification["details"] = stdout
                    self.send_notification("{}.iouyap_stopped".format(self.name), notification)
                iou_instance.stop()

    def get_iou_instance(self, iou_id):
        """
        Returns an IOU device instance.

        :param iou_id: IOU device identifier

        :returns: IOUDevice instance
        """

        if iou_id not in self._iou_instances:
            log.debug("IOU device ID {} doesn't exist".format(iou_id), exc_info=1)
            self.send_custom_error("IOU device ID {} doesn't exist".format(iou_id))
            return None
        return self._iou_instances[iou_id]

    @IModule.route("iou.reset")
    def reset(self, request):
        """
        Resets the module.

        :param request: JSON request
        """

        # delete all IOU instances
        for iou_id in self._iou_instances:
            iou_instance = self._iou_instances[iou_id]
            iou_instance.delete()

        # resets the instance IDs
        IOUDevice.reset()

        self._iou_instances.clear()
        self._allocated_udp_ports.clear()

        if self._iourc and os.path.isfile(self._iourc):
            try:
                log.info("deleting iourc file {}".format(self._iourc))
                os.remove(self._iourc)
            except OSError as e:
                log.warn("could not delete iourc file {}: {}".format(self._iourc, e))

        log.info("IOU module has been reset")

    @IModule.route("iou.settings")
    def settings(self, request):
        """
        Set or update settings.

        Mandatory request parameters:
        - iourc (base64 encoded iourc file)

        Optional request parameters:
        - working_dir (path to a working directory)
        - project_name
        - console_start_port_range
        - console_end_port_range
        - udp_start_port_range
        - udp_end_port_range

        :param request: JSON request
        """

        if request == None:
            self.send_param_error()
            return

        if "iourc" in request:
            iourc_content = base64.decodestring(request["iourc"].encode("utf-8")).decode("utf-8")
            iourc_content = iourc_content.replace("\r\n", "\n")  # dos2unix
            try:
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                    log.info("saving iourc file content to {}".format(f.name))
                    f.write(iourc_content)
                    self._iourc = f.name
            except OSError as e:
                raise IOUError("Could not save iourc file to {}: {}".format(f.name, e))

        if "iouyap" in request and request["iouyap"]:
            self._iouyap = request["iouyap"]
            log.info("iouyap path set to {}".format(self._iouyap))

        if "working_dir" in request:
            new_working_dir = request["working_dir"]
            log.info("this server is local with working directory path to {}".format(new_working_dir))
        else:
            new_working_dir = os.path.join(self._projects_dir, request["project_name"] + ".gns3")
            log.info("this server is remote with working directory path to {}".format(new_working_dir))
            if self._projects_dir != self._working_dir != new_working_dir:
                if not os.path.isdir(new_working_dir):
                    try:
                        shutil.move(self._working_dir, new_working_dir)
                    except OSError as e:
                        log.error("could not move working directory from {} to {}: {}".format(self._working_dir,
                                                                                              new_working_dir,
                                                                                              e))
                        return

        # update the working directory if it has changed
        if self._working_dir != new_working_dir:
            self._working_dir = new_working_dir
            for iou_id in self._iou_instances:
                iou_instance = self._iou_instances[iou_id]
                iou_instance.working_dir = self._working_dir

        if "console_start_port_range" in request and "console_end_port_range" in request:
            self._console_start_port_range = request["console_start_port_range"]
            self._console_end_port_range = request["console_end_port_range"]

        if "udp_start_port_range" in request and "udp_end_port_range" in request:
            self._udp_start_port_range = request["udp_start_port_range"]
            self._udp_end_port_range = request["udp_end_port_range"]

        log.debug("received request {}".format(request))

    def test_result(self, message, result="error"):
        """
        """

        return {"result": result, "message": message}

    @IModule.route("iou.test_settings")
    def test_settings(self, request):
        """
        """

        response = []

        # test iourc
        if self._iourc == "":
            response.append(self.test_result("No iourc file has been added"))
        elif not os.path.isfile(self._iourc):
            response.append(self.test_result("iourc file {} is not accessible".format(self._iourc)))
        else:
            #TODO: check hostname + license inside the file
            pass

        self.send_response(response)

    @IModule.route("iou.create")
    def iou_create(self, request):
        """
        Creates a new IOU instance.

        Mandatory request parameters:
        - path (path to the IOU executable)

        Optional request parameters:
        - name (IOU name)

        Response parameters:
        - id (IOU instance identifier)
        - name (IOU name)
        - default settings

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, IOU_CREATE_SCHEMA):
            return

        name = None
        if "name" in request:
            name = request["name"]
        iou_path = request["path"]

        try:
            try:
                os.makedirs(self._working_dir)
            except FileExistsError:
                pass
            except OSError as e:
                raise IOUError("Could not create working directory {}".format(e))

            iou_instance = IOUDevice(iou_path,
                                     self._working_dir,
                                     self._host,
                                     name,
                                     self._console_start_port_range,
                                     self._console_end_port_range)

        except IOUError as e:
            self.send_custom_error(str(e))
            return

        response = {"name": iou_instance.name,
                    "id": iou_instance.id}

        defaults = iou_instance.defaults()
        response.update(defaults)
        self._iou_instances[iou_instance.id] = iou_instance
        self.send_response(response)

    @IModule.route("iou.delete")
    def iou_delete(self, request):
        """
        Deletes an IOU instance.

        Mandatory request parameters:
        - id (IOU instance identifier)

        Response parameter:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, IOU_DELETE_SCHEMA):
            return

        # get the instance
        iou_instance = self.get_iou_instance(request["id"])
        if not iou_instance:
            return

        try:
            iou_instance.delete()
            del self._iou_instances[request["id"]]
        except IOUError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("iou.update")
    def iou_update(self, request):
        """
        Updates an IOU instance

        Mandatory request parameters:
        - id (IOU instance identifier)

        Optional request parameters:
        - any setting to update
        - startup_config_base64 (startup-config base64 encoded)

        Response parameters:
        - updated settings

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, IOU_UPDATE_SCHEMA):
            return

        # get the instance
        iou_instance = self.get_iou_instance(request["id"])
        if not iou_instance:
            return

        response = {}
        config_path = os.path.join(iou_instance.working_dir, "startup-config")
        try:
            if "startup_config_base64" in request:
                # a new startup-config has been pushed
                config = base64.decodestring(request["startup_config_base64"].encode("utf-8")).decode("utf-8")
                config = "!\n" + config.replace("\r", "")
                config = config.replace('%h', iou_instance.name)
                try:
                    with open(config_path, "w") as f:
                        log.info("saving startup-config to {}".format(config_path))
                        f.write(config)
                except OSError as e:
                    raise IOUError("Could not save the configuration {}: {}".format(config_path, e))
                # update the request with the new local startup-config path
                request["startup_config"] = os.path.basename(config_path)
            elif "startup_config" in request:
                if os.path.isfile(request["startup_config"]) and request["startup_config"] != config_path:
                    # this is a local file set in the GUI
                    try:
                        with open(request["startup_config"], "r") as f:
                            config = f.read()
                        with open(config_path, "w") as f:
                            config = "!\n" + config.replace("\r", "")
                            config = config.replace('%h', iou_instance.name)
                            f.write(config)
                        request["startup_config"] = os.path.basename(config_path)
                    except OSError as e:
                        raise IOUError("Could not save the configuration from {} to {}: {}".format(request["startup_config"], config_path, e))
                else:
                    raise IOUError("Startup-config {} could not be found on this server".format(request["startup_config"]))
        except IOUError as e:
            self.send_custom_error(str(e))
            return

        # update the IOU settings
        for name, value in request.items():
            if hasattr(iou_instance, name) and getattr(iou_instance, name) != value:
                try:
                    setattr(iou_instance, name, value)
                    response[name] = value
                except IOUError as e:
                    self.send_custom_error(str(e))
                    return

        self.send_response(response)

    @IModule.route("iou.start")
    def vm_start(self, request):
        """
        Starts an IOU instance.

        Mandatory request parameters:
        - id (IOU instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, IOU_START_SCHEMA):
            return

        # get the instance
        iou_instance = self.get_iou_instance(request["id"])
        if not iou_instance:
            return

        try:
            log.debug("starting IOU with command: {}".format(iou_instance.command()))
            iou_instance.iouyap = self._iouyap
            iou_instance.iourc = self._iourc
            iou_instance.start()
        except IOUError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("iou.stop")
    def vm_stop(self, request):
        """
        Stops an IOU instance.

        Mandatory request parameters:
        - id (IOU instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, IOU_STOP_SCHEMA):
            return

        # get the instance
        iou_instance = self.get_iou_instance(request["id"])
        if not iou_instance:
            return

        try:
            iou_instance.stop()
        except IOUError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("iou.reload")
    def vm_reload(self, request):
        """
        Reloads an IOU instance.

        Mandatory request parameters:
        - id (IOU identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, IOU_RELOAD_SCHEMA):
            return

        # get the instance
        iou_instance = self.get_iou_instance(request["id"])
        if not iou_instance:
            return

        try:
            if iou_instance.is_running():
                iou_instance.stop()
            iou_instance.start()
        except IOUError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("iou.allocate_udp_port")
    def allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO.

        Mandatory request parameters:
        - id (IOU identifier)
        - port_id (unique port identifier)

        Response parameters:
        - port_id (unique port identifier)
        - lport (allocated local port)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, IOU_ALLOCATE_UDP_PORT_SCHEMA):
            return

        # get the instance
        iou_instance = self.get_iou_instance(request["id"])
        if not iou_instance:
            return

        try:
            port = find_unused_port(self._udp_start_port_range,
                                    self._udp_end_port_range,
                                    host=self._host,
                                    socket_type="UDP",
                                    ignore_ports=self._allocated_udp_ports)
        except Exception as e:
            self.send_custom_error(str(e))

        self._allocated_udp_ports.append(port)
        log.info("{} [id={}] has allocated UDP port {} with host {}".format(iou_instance.name,
                                                                            iou_instance.id,
                                                                            port,
                                                                            self._host))
        response = {"lport": port}
        response["port_id"] = request["port_id"]
        self.send_response(response)

    def _check_for_privileged_access(self, device):
        """
        Check if iouyap can access Ethernet and TAP devices.

        :param device: device name
        """

        # we are root, so iouyap should have privileged access too
        if os.geteuid() == 0:
            return

        # test if iouyap has the CAP_NET_RAW capability
        if "security.capability" in os.listxattr(self._iouyap):
            try:
                caps = os.getxattr(self._iouyap, "security.capability")
                # test the 2nd byte and check if the 13th bit (CAP_NET_RAW) is set
                if struct.unpack("<IIIII", caps)[1] & 1 << 13:
                    return
            except Exception as e:
                log.error("could not determine if CAP_NET_RAW capability is set for {}: {}".format(self._iouyap, e))
                return

        raise IOUError("{} has no privileged access to {}.".format(self._iouyap, device))

    @IModule.route("iou.add_nio")
    def add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for an IOU instance.

        Mandatory request parameters:
        - id (IOU instance identifier)
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
            - type "nio_tap"
                - tap_device (TAP device name e.g. tap0)

        Response parameters:
        - port_id (unique port identifier)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, IOU_ADD_NIO_SCHEMA):
            return

        # get the instance
        iou_instance = self.get_iou_instance(request["id"])
        if not iou_instance:
            return

        slot = request["slot"]
        port = request["port"]
        try:
            nio = None
            if request["nio"]["type"] == "nio_udp":
                lport = request["nio"]["lport"]
                rhost = request["nio"]["rhost"]
                rport = request["nio"]["rport"]
                nio = NIO_UDP(lport, rhost, rport)
            elif request["nio"]["type"] == "nio_tap":
                tap_device = request["nio"]["tap_device"]
                self._check_for_privileged_access(tap_device)
                nio = NIO_TAP(tap_device)
            elif request["nio"]["type"] == "nio_generic_ethernet":
                ethernet_device = request["nio"]["ethernet_device"]
                self._check_for_privileged_access(ethernet_device)
                nio = NIO_GenericEthernet(ethernet_device)
            if not nio:
                raise IOUError("Requested NIO does not exist or is not supported: {}".format(request["nio"]["type"]))
        except IOUError as e:
            self.send_custom_error(str(e))
            return

        try:
            iou_instance.slot_add_nio_binding(slot, port, nio)
        except IOUError as e:
            self.send_custom_error(str(e))
            return

        self.send_response({"port_id": request["port_id"]})

    @IModule.route("iou.delete_nio")
    def delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        Mandatory request parameters:
        - id (IOU instance identifier)
        - slot (slot identifier)
        - port (port identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, IOU_DELETE_NIO_SCHEMA):
            return

        # get the instance
        iou_instance = self.get_iou_instance(request["id"])
        if not iou_instance:
            return

        slot = request["slot"]
        port = request["port"]
        try:
            nio = iou_instance.slot_remove_nio_binding(slot, port)
            if isinstance(nio, NIO_UDP) and nio.lport in self._allocated_udp_ports:
                self._allocated_udp_ports.remove(nio.lport)
        except IOUError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("iou.echo")
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
