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
VirtualBox server module.
"""

import sys
import os
import socket
import shutil
import subprocess

from gns3server.modules import IModule
from gns3server.config import Config
from .virtualbox_vm import VirtualBoxVM
from .virtualbox_error import VirtualBoxError
from .nios.nio_udp import NIO_UDP
from ..attic import find_unused_port

from .schemas import VBOX_CREATE_SCHEMA
from .schemas import VBOX_DELETE_SCHEMA
from .schemas import VBOX_UPDATE_SCHEMA
from .schemas import VBOX_START_SCHEMA
from .schemas import VBOX_STOP_SCHEMA
from .schemas import VBOX_SUSPEND_SCHEMA
from .schemas import VBOX_RELOAD_SCHEMA
from .schemas import VBOX_ALLOCATE_UDP_PORT_SCHEMA
from .schemas import VBOX_ADD_NIO_SCHEMA
from .schemas import VBOX_DELETE_NIO_SCHEMA
from .schemas import VBOX_START_CAPTURE_SCHEMA
from .schemas import VBOX_STOP_CAPTURE_SCHEMA

import logging
log = logging.getLogger(__name__)


class VirtualBox(IModule):
    """
    VirtualBox module.

    :param name: module name
    :param args: arguments for the module
    :param kwargs: named arguments for the module
    """

    def __init__(self, name, *args, **kwargs):

        # get the vboxmanage location
        self._vboxmanage_path = None
        if sys.platform.startswith("win"):
            if "VBOX_INSTALL_PATH" in os.environ:
                self._vboxmanage_path = os.path.join(os.environ["VBOX_INSTALL_PATH"], "VBoxManage.exe")
            elif "VBOX_MSI_INSTALL_PATH" in os.environ:
                self._vboxmanage_path = os.path.join(os.environ["VBOX_MSI_INSTALL_PATH"], "VBoxManage.exe")
        elif sys.platform.startswith("darwin"):
            self._vboxmanage_path = "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"
        else:
            config = Config.instance()
            vbox_config = config.get_section_config(name.upper())
            self._vboxmanage_path = vbox_config.get("vboxmanage_path")
            if not self._vboxmanage_path or not os.path.isfile(self._vboxmanage_path):
                paths = [os.getcwd()] + os.environ["PATH"].split(os.pathsep)
                # look for vboxmanage in the current working directory and $PATH
                for path in paths:
                    try:
                        if "vboxmanage" in [s.lower() for s in os.listdir(path)] and os.access(os.path.join(path, "vboxmanage"), os.X_OK):
                            self._vboxmanage_path = os.path.join(path, "vboxmanage")
                            break
                    except OSError:
                        continue

        if not self._vboxmanage_path:
            log.warning("vboxmanage couldn't be found!")
        elif not os.access(self._vboxmanage_path, os.X_OK):
            log.warning("vboxmanage is not executable")

        self._vbox_user = None

        # a new process start when calling IModule
        IModule.__init__(self, name, *args, **kwargs)
        self._vbox_instances = {}

        config = Config.instance()
        vbox_config = config.get_section_config(name.upper())
        self._console_start_port_range = vbox_config.get("console_start_port_range", 3501)
        self._console_end_port_range = vbox_config.get("console_end_port_range", 4000)
        self._allocated_udp_ports = []
        self._udp_start_port_range = vbox_config.get("udp_start_port_range", 35001)
        self._udp_end_port_range = vbox_config.get("udp_end_port_range", 35500)
        self._host = vbox_config.get("host", kwargs["host"])
        self._console_host = vbox_config.get("console_host", kwargs["console_host"])
        self._projects_dir = kwargs["projects_dir"]
        self._tempdir = kwargs["temp_dir"]
        self._working_dir = self._projects_dir

    def stop(self, signum=None):
        """
        Properly stops the module.

        :param signum: signal number (if called by the signal handler)
        """

        # delete all VirtualBox instances
        for vbox_id in self._vbox_instances:
            vbox_instance = self._vbox_instances[vbox_id]
            try:
                vbox_instance.delete()
            except VirtualBoxError:
                continue

        IModule.stop(self, signum)  # this will stop the I/O loop

    def get_vbox_instance(self, vbox_id):
        """
        Returns a VirtualBox VM instance.

        :param vbox_id: VirtualBox VM identifier

        :returns: VirtualBoxVM instance
        """

        if vbox_id not in self._vbox_instances:
            log.debug("VirtualBox VM ID {} doesn't exist".format(vbox_id), exc_info=1)
            self.send_custom_error("VirtualBox VM ID {} doesn't exist".format(vbox_id))
            return None
        return self._vbox_instances[vbox_id]

    @IModule.route("virtualbox.reset")
    def reset(self, request):
        """
        Resets the module.

        :param request: JSON request
        """

        # delete all VirtualBox instances
        for vbox_id in self._vbox_instances:
            vbox_instance = self._vbox_instances[vbox_id]
            vbox_instance.delete()

        # resets the instance IDs
        VirtualBoxVM.reset()

        self._vbox_instances.clear()
        self._allocated_udp_ports.clear()

        self._working_dir = self._projects_dir
        log.info("VirtualBox module has been reset")

    @IModule.route("virtualbox.settings")
    def settings(self, request):
        """
        Set or update settings.

        Optional request parameters:
        - working_dir (path to a working directory)
        - vboxmanage_path (path to vboxmanage)
        - project_name
        - console_start_port_range
        - console_end_port_range
        - udp_start_port_range
        - udp_end_port_range

        :param request: JSON request
        """

        if request is None:
            self.send_param_error()
            return

        if "working_dir" in request:
            new_working_dir = request["working_dir"]
            log.info("this server is local with working directory path to {}".format(new_working_dir))
        else:
            new_working_dir = os.path.join(self._projects_dir, request["project_name"])
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
            for vbox_id in self._vbox_instances:
                vbox_instance = self._vbox_instances[vbox_id]
                vbox_instance.working_dir = os.path.join(self._working_dir, "vbox", "{}".format(vbox_instance.name))

        if "vboxmanage_path" in request:
            self._vboxmanage_path = request["vboxmanage_path"]

        if "vbox_user" in request:
            self._vbox_user = request["vbox_user"]

        if "console_start_port_range" in request and "console_end_port_range" in request:
            self._console_start_port_range = request["console_start_port_range"]
            self._console_end_port_range = request["console_end_port_range"]

        if "udp_start_port_range" in request and "udp_end_port_range" in request:
            self._udp_start_port_range = request["udp_start_port_range"]
            self._udp_end_port_range = request["udp_end_port_range"]

        log.debug("received request {}".format(request))

    @IModule.route("virtualbox.create")
    def vbox_create(self, request):
        """
        Creates a new VirtualBox VM instance.

        Mandatory request parameters:
        - name (VirtualBox VM name)
        - vmname (VirtualBox VM name in VirtualBox)
        - linked_clone (Flag to create a linked clone)

        Optional request parameters:
        - console (VirtualBox VM console port)

        Response parameters:
        - id (VirtualBox VM instance identifier)
        - name (VirtualBox VM name)
        - default settings

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_CREATE_SCHEMA):
            return

        name = request["name"]
        vmname = request["vmname"]
        linked_clone = request["linked_clone"]
        console = request.get("console")
        vbox_id = request.get("vbox_id")

        try:

            if not self._vboxmanage_path or not os.path.exists(self._vboxmanage_path):
                raise VirtualBoxError("Could not find VBoxManage, is VirtualBox correctly installed?")

            vbox_instance = VirtualBoxVM(self._vboxmanage_path,
                                         self._vbox_user,
                                         name,
                                         vmname,
                                         linked_clone,
                                         self._working_dir,
                                         vbox_id,
                                         console,
                                         self._console_host,
                                         self._console_start_port_range,
                                         self._console_end_port_range)

        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return

        response = {"name": vbox_instance.name,
                    "id": vbox_instance.id}

        defaults = vbox_instance.defaults()
        response.update(defaults)
        self._vbox_instances[vbox_instance.id] = vbox_instance
        self.send_response(response)

    @IModule.route("virtualbox.delete")
    def vbox_delete(self, request):
        """
        Deletes a VirtualBox VM instance.

        Mandatory request parameters:
        - id (VirtualBox VM instance identifier)

        Response parameter:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_DELETE_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        try:
            vbox_instance.clean_delete()
            del self._vbox_instances[request["id"]]
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("virtualbox.update")
    def vbox_update(self, request):
        """
        Updates a VirtualBox VM instance

        Mandatory request parameters:
        - id (VirtualBox VM instance identifier)

        Optional request parameters:
        - any setting to update

        Response parameters:
        - updated settings

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_UPDATE_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        # update the VirtualBox VM settings
        response = {}
        for name, value in request.items():
            if hasattr(vbox_instance, name) and getattr(vbox_instance, name) != value:
                try:
                    setattr(vbox_instance, name, value)
                    response[name] = value
                except VirtualBoxError as e:
                    self.send_custom_error(str(e))
                    return

        self.send_response(response)

    @IModule.route("virtualbox.start")
    def vbox_start(self, request):
        """
        Starts a VirtualBox VM instance.

        Mandatory request parameters:
        - id (VirtualBox VM instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_START_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        try:
            vbox_instance.start()
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("virtualbox.stop")
    def vbox_stop(self, request):
        """
        Stops a VirtualBox VM instance.

        Mandatory request parameters:
        - id (VirtualBox VM instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_STOP_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        try:
            vbox_instance.stop()
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("virtualbox.reload")
    def vbox_reload(self, request):
        """
        Reloads a VirtualBox VM instance.

        Mandatory request parameters:
        - id (VirtualBox VM identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_RELOAD_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        try:
            vbox_instance.reload()
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("virtualbox.stop")
    def vbox_stop(self, request):
        """
        Stops a VirtualBox VM instance.

        Mandatory request parameters:
        - id (VirtualBox VM instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_STOP_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        try:
            vbox_instance.stop()
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("virtualbox.suspend")
    def vbox_suspend(self, request):
        """
        Suspends a VirtualBox VM instance.

        Mandatory request parameters:
        - id (VirtualBox VM instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_SUSPEND_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        try:
            vbox_instance.suspend()
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("virtualbox.allocate_udp_port")
    def allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO.

        Mandatory request parameters:
        - id (VirtualBox VM identifier)
        - port_id (unique port identifier)

        Response parameters:
        - port_id (unique port identifier)
        - lport (allocated local port)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_ALLOCATE_UDP_PORT_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        try:
            port = find_unused_port(self._udp_start_port_range,
                                    self._udp_end_port_range,
                                    host=self._host,
                                    socket_type="UDP",
                                    ignore_ports=self._allocated_udp_ports)
        except Exception as e:
            self.send_custom_error(str(e))
            return

        self._allocated_udp_ports.append(port)
        log.info("{} [id={}] has allocated UDP port {} with host {}".format(vbox_instance.name,
                                                                            vbox_instance.id,
                                                                            port,
                                                                            self._host))

        response = {"lport": port,
                    "port_id": request["port_id"]}
        self.send_response(response)

    @IModule.route("virtualbox.add_nio")
    def add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for a VirtualBox VM instance.

        Mandatory request parameters:
        - id (VirtualBox VM instance identifier)
        - port (port number)
        - port_id (unique port identifier)
        - nio (one of the following)
            - type "nio_udp"
                - lport (local port)
                - rhost (remote host)
                - rport (remote port)

        Response parameters:
        - port_id (unique port identifier)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_ADD_NIO_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        port = request["port"]
        try:
            nio = None
            if request["nio"]["type"] == "nio_udp":
                lport = request["nio"]["lport"]
                rhost = request["nio"]["rhost"]
                rport = request["nio"]["rport"]
                try:
                    #TODO: handle IPv6
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        sock.connect((rhost, rport))
                except OSError as e:
                    raise VirtualBoxError("Could not create an UDP connection to {}:{}: {}".format(rhost, rport, e))
                nio = NIO_UDP(lport, rhost, rport)
            if not nio:
                raise VirtualBoxError("Requested NIO does not exist or is not supported: {}".format(request["nio"]["type"]))
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return

        try:
            vbox_instance.port_add_nio_binding(port, nio)
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return

        self.send_response({"port_id": request["port_id"]})

    @IModule.route("virtualbox.delete_nio")
    def delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        Mandatory request parameters:
        - id (VirtualBox instance identifier)
        - port (port identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_DELETE_NIO_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        port = request["port"]
        try:
            nio = vbox_instance.port_remove_nio_binding(port)
            if isinstance(nio, NIO_UDP) and nio.lport in self._allocated_udp_ports:
                self._allocated_udp_ports.remove(nio.lport)
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("virtualbox.start_capture")
    def vbox_start_capture(self, request):
        """
        Starts a packet capture.

        Mandatory request parameters:
        - id (VirtualBox VM identifier)
        - port (port number)
        - port_id (port identifier)
        - capture_file_name

        Response parameters:
        - port_id (port identifier)
        - capture_file_path (path to the capture file)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_START_CAPTURE_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        port = request["port"]
        capture_file_name = request["capture_file_name"]

        try:
            capture_file_path = os.path.join(self._working_dir, "captures", capture_file_name)
            vbox_instance.start_capture(port, capture_file_path)
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"],
                    "capture_file_path": capture_file_path}
        self.send_response(response)

    @IModule.route("virtualbox.stop_capture")
    def vbox_stop_capture(self, request):
        """
        Stops a packet capture.

        Mandatory request parameters:
        - id (VirtualBox VM identifier)
        - port (port number)
        - port_id (port identifier)

        Response parameters:
        - port_id (port identifier)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, VBOX_STOP_CAPTURE_SCHEMA):
            return

        # get the instance
        vbox_instance = self.get_vbox_instance(request["id"])
        if not vbox_instance:
            return

        port = request["port"]
        try:
            vbox_instance.stop_capture(port)
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return

        response = {"port_id": request["port_id"]}
        self.send_response(response)

    def _execute_vboxmanage(self, user, command):
        """
        Executes VBoxManage and return its result.

        :param command: command to execute (list)

        :returns: VBoxManage output
        """

        try:
            if not user.strip() or sys.platform.startswith("win") or sys.platform.startswith("darwin"):
                result = subprocess.check_output(command, stderr=subprocess.STDOUT, timeout=30)
            else:
                sudo_command = "sudo -i -u " + user.strip() + " " + " ".join(command)
                result = subprocess.check_output(sudo_command, stderr=subprocess.STDOUT, shell=True, timeout=30)
        except subprocess.SubprocessError as e:
            raise VirtualBoxError("Could not execute VBoxManage {}".format(e))
        return result.decode("utf-8")

    @IModule.route("virtualbox.vm_list")
    def vm_list(self, request):
        """
        Gets VirtualBox VM list.

        Response parameters:
        - Server address/host
        - List of VM names
        """

        try:

            if request and "vboxmanage_path" in request:
                vboxmanage_path = request["vboxmanage_path"]
            else:
                vboxmanage_path = self._vboxmanage_path

            if request and "vbox_user" in request:
                vbox_user = request["vbox_user"]
            else:
                vbox_user = self._vbox_user

            if not vboxmanage_path or not os.path.exists(vboxmanage_path):
                raise VirtualBoxError("Could not find VBoxManage, is VirtualBox correctly installed?")

            command = [vboxmanage_path, "--nologo", "list", "vms"]
            result = self._execute_vboxmanage(vbox_user, command)
        except VirtualBoxError as e:
            self.send_custom_error(str(e))
            return

        vms = []
        for line in result.splitlines():
            vmname, uuid = line.rsplit(' ', 1)
            vmname = vmname.strip('"')
            if vmname == "<inaccessible>":
                continue  # ignore inaccessible VMs
            try:
                extra_data = self._execute_vboxmanage(vbox_user, [vboxmanage_path, "getextradata", vmname, "GNS3/Clone"]).strip()
            except VirtualBoxError as e:
                self.send_custom_error(str(e))
                return
            if not extra_data == "Value: yes":
                vms.append(vmname)

        response = {"vms": vms}
        self.send_response(response)

    @IModule.route("virtualbox.echo")
    def echo(self, request):
        """
        Echo end point for testing purposes.

        :param request: JSON request
        """

        if request is None:
            self.send_param_error()
        else:
            log.debug("received request {}".format(request))
            self.send_response(request)
