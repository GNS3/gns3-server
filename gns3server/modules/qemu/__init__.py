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
QEMU server module.
"""

import sys
import os
import socket
import shutil
import subprocess
import re

from gns3server.modules import IModule
from gns3server.config import Config
from .qemu_vm import QemuVM
from .qemu_error import QemuError
from .nios.nio_udp import NIO_UDP
from ..attic import find_unused_port

from .schemas import QEMU_CREATE_SCHEMA
from .schemas import QEMU_DELETE_SCHEMA
from .schemas import QEMU_UPDATE_SCHEMA
from .schemas import QEMU_START_SCHEMA
from .schemas import QEMU_STOP_SCHEMA
from .schemas import QEMU_SUSPEND_SCHEMA
from .schemas import QEMU_RELOAD_SCHEMA
from .schemas import QEMU_ALLOCATE_UDP_PORT_SCHEMA
from .schemas import QEMU_ADD_NIO_SCHEMA
from .schemas import QEMU_DELETE_NIO_SCHEMA

import logging
log = logging.getLogger(__name__)


class Qemu(IModule):
    """
    QEMU module.

    :param name: module name
    :param args: arguments for the module
    :param kwargs: named arguments for the module
    """

    def __init__(self, name, *args, **kwargs):

        # a new process start when calling IModule
        IModule.__init__(self, name, *args, **kwargs)
        self._qemu_instances = {}

        config = Config.instance()
        qemu_config = config.get_section_config(name.upper())
        self._console_start_port_range = qemu_config.get("console_start_port_range", 5001)
        self._console_end_port_range = qemu_config.get("console_end_port_range", 5500)
        self._allocated_udp_ports = []
        self._udp_start_port_range = qemu_config.get("udp_start_port_range", 40001)
        self._udp_end_port_range = qemu_config.get("udp_end_port_range", 45500)
        self._host = qemu_config.get("host", kwargs["host"])
        self._projects_dir = kwargs["projects_dir"]
        self._tempdir = kwargs["temp_dir"]
        self._working_dir = self._projects_dir

    def stop(self, signum=None):
        """
        Properly stops the module.

        :param signum: signal number (if called by the signal handler)
        """

        # delete all QEMU instances
        for qemu_id in self._qemu_instances:
            qemu_instance = self._qemu_instances[qemu_id]
            qemu_instance.delete()

        IModule.stop(self, signum)  # this will stop the I/O loop

    def get_qemu_instance(self, qemu_id):
        """
        Returns a QEMU VM instance.

        :param qemu_id: QEMU VM identifier

        :returns: QemuVM instance
        """

        if qemu_id not in self._qemu_instances:
            log.debug("QEMU VM ID {} doesn't exist".format(qemu_id), exc_info=1)
            self.send_custom_error("QEMU VM ID {} doesn't exist".format(qemu_id))
            return None
        return self._qemu_instances[qemu_id]

    @IModule.route("qemu.reset")
    def reset(self, request):
        """
        Resets the module.

        :param request: JSON request
        """

        # delete all QEMU instances
        for qemu_id in self._qemu_instances:
            qemu_instance = self._qemu_instances[qemu_id]
            qemu_instance.delete()

        # resets the instance IDs
        QemuVM.reset()

        self._qemu_instances.clear()
        self._allocated_udp_ports.clear()

        log.info("QEMU module has been reset")

    @IModule.route("qemu.settings")
    def settings(self, request):
        """
        Set or update settings.

        Optional request parameters:
        - working_dir (path to a working directory)
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
            for qemu_id in self._qemu_instances:
                qemu_instance = self._qemu_instances[qemu_id]
                qemu_instance.working_dir = os.path.join(self._working_dir, "qemu", "vm-{}".format(qemu_instance.id))

        if "console_start_port_range" in request and "console_end_port_range" in request:
            self._console_start_port_range = request["console_start_port_range"]
            self._console_end_port_range = request["console_end_port_range"]

        if "udp_start_port_range" in request and "udp_end_port_range" in request:
            self._udp_start_port_range = request["udp_start_port_range"]
            self._udp_end_port_range = request["udp_end_port_range"]

        log.debug("received request {}".format(request))

    @IModule.route("qemu.create")
    def qemu_create(self, request):
        """
        Creates a new QEMU VM instance.

        Mandatory request parameters:
        - name (QEMU VM name)
        - qemu_path (path to the Qemu binary)

        Optional request parameters:
        - console (QEMU VM console port)

        Response parameters:
        - id (QEMU VM instance identifier)
        - name (QEMU VM name)
        - default settings

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_CREATE_SCHEMA):
            return

        name = request["name"]
        qemu_path = request["qemu_path"]
        console = request.get("console")
        qemu_id = request.get("qemu_id")

        try:
            qemu_instance = QemuVM(name,
                                   qemu_path,
                                   self._working_dir,
                                   self._host,
                                   qemu_id,
                                   console,
                                   self._console_start_port_range,
                                   self._console_end_port_range)

        except QemuError as e:
            self.send_custom_error(str(e))
            return

        response = {"name": qemu_instance.name,
                    "id": qemu_instance.id}

        defaults = qemu_instance.defaults()
        response.update(defaults)
        self._qemu_instances[qemu_instance.id] = qemu_instance
        self.send_response(response)

    @IModule.route("qemu.delete")
    def qemu_delete(self, request):
        """
        Deletes a QEMU VM instance.

        Mandatory request parameters:
        - id (QEMU VM instance identifier)

        Response parameter:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_DELETE_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
            return

        try:
            qemu_instance.clean_delete()
            del self._qemu_instances[request["id"]]
        except QemuError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    @IModule.route("qemu.update")
    def qemu_update(self, request):
        """
        Updates a QEMU VM instance

        Mandatory request parameters:
        - id (QEMU VM instance identifier)

        Optional request parameters:
        - any setting to update

        Response parameters:
        - updated settings

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_UPDATE_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
            return

        # update the QEMU VM settings
        response = {}
        for name, value in request.items():
            if hasattr(qemu_instance, name) and getattr(qemu_instance, name) != value:
                try:
                    setattr(qemu_instance, name, value)
                    response[name] = value
                except QemuError as e:
                    self.send_custom_error(str(e))
                    return

        self.send_response(response)

    @IModule.route("qemu.start")
    def qemu_start(self, request):
        """
        Starts a QEMU VM instance.

        Mandatory request parameters:
        - id (QEMU VM instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_START_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
            return

        try:
            qemu_instance.start()
        except QemuError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("qemu.stop")
    def qemu_stop(self, request):
        """
        Stops a QEMU VM instance.

        Mandatory request parameters:
        - id (QEMU VM instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_STOP_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
            return

        try:
            qemu_instance.stop()
        except QemuError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("qemu.reload")
    def qemu_reload(self, request):
        """
        Reloads a QEMU VM instance.

        Mandatory request parameters:
        - id (QEMU VM identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_RELOAD_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
            return

        try:
            qemu_instance.reload()
        except QemuError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("qemu.stop")
    def qemu_stop(self, request):
        """
        Stops a QEMU VM instance.

        Mandatory request parameters:
        - id (QEMU VM instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_STOP_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
            return

        try:
            qemu_instance.stop()
        except QemuError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("qemu.suspend")
    def qemu_suspend(self, request):
        """
        Suspends a QEMU VM instance.

        Mandatory request parameters:
        - id (QEMU VM instance identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_SUSPEND_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
            return

        try:
            qemu_instance.suspend()
        except QemuError as e:
            self.send_custom_error(str(e))
            return
        self.send_response(True)

    @IModule.route("qemu.allocate_udp_port")
    def allocate_udp_port(self, request):
        """
        Allocates a UDP port in order to create an UDP NIO.

        Mandatory request parameters:
        - id (QEMU VM identifier)
        - port_id (unique port identifier)

        Response parameters:
        - port_id (unique port identifier)
        - lport (allocated local port)

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_ALLOCATE_UDP_PORT_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
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
        log.info("{} [id={}] has allocated UDP port {} with host {}".format(qemu_instance.name,
                                                                            qemu_instance.id,
                                                                            port,
                                                                            self._host))

        response = {"lport": port,
                    "port_id": request["port_id"]}
        self.send_response(response)

    @IModule.route("qemu.add_nio")
    def add_nio(self, request):
        """
        Adds an NIO (Network Input/Output) for a QEMU VM instance.

        Mandatory request parameters:
        - id (QEMU VM instance identifier)
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
        if not self.validate_request(request, QEMU_ADD_NIO_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
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
                    raise QemuError("Could not create an UDP connection to {}:{}: {}".format(rhost, rport, e))
                nio = NIO_UDP(lport, rhost, rport)
            if not nio:
                raise QemuError("Requested NIO does not exist or is not supported: {}".format(request["nio"]["type"]))
        except QemuError as e:
            self.send_custom_error(str(e))
            return

        try:
            qemu_instance.port_add_nio_binding(port, nio)
        except QemuError as e:
            self.send_custom_error(str(e))
            return

        self.send_response({"port_id": request["port_id"]})

    @IModule.route("qemu.delete_nio")
    def delete_nio(self, request):
        """
        Deletes an NIO (Network Input/Output).

        Mandatory request parameters:
        - id (QEMU VM instance identifier)
        - port (port identifier)

        Response parameters:
        - True on success

        :param request: JSON request
        """

        # validate the request
        if not self.validate_request(request, QEMU_DELETE_NIO_SCHEMA):
            return

        # get the instance
        qemu_instance = self.get_qemu_instance(request["id"])
        if not qemu_instance:
            return

        port = request["port"]
        try:
            nio = qemu_instance.port_remove_nio_binding(port)
            if isinstance(nio, NIO_UDP) and nio.lport in self._allocated_udp_ports:
                self._allocated_udp_ports.remove(nio.lport)
        except QemuError as e:
            self.send_custom_error(str(e))
            return

        self.send_response(True)

    def _get_qemu_version(self, qemu_path):
        """
        Gets the Qemu version.

        :param qemu_path: path to Qemu
        """

        if sys.platform.startswith("win"):
            return ""
        try:
            output = subprocess.check_output([qemu_path, "--version"])
            match = re.search("QEMU emulator version ([0-9a-z\-\.]+)", output.decode("utf-8"))
            if match:
                version = match.group(1)
                return version
            else:
                raise QemuError("Could not determine the Qemu version for {}".format(qemu_path))
        except (OSError, subprocess.CalledProcessError) as e:
            raise QemuError("Error while looking for the Qemu version: {}".format(e))

    @IModule.route("qemu.qemu_list")
    def qemu_list(self, request):
        """
        Gets QEMU binaries list.

        Response parameters:
        - Server address/host
        - List of Qemu binaries
        """

        qemus = []
        paths = [os.getcwd()] + os.environ["PATH"].split(os.pathsep)
        # look for Qemu binaries in the current working directory and $PATH
        if sys.platform.startswith("win"):
            # add specific Windows paths
            paths.append(os.path.join(os.getcwd(), "qemu"))
            if "PROGRAMFILES(X86)" in os.environ and os.path.exists(os.environ["PROGRAMFILES(X86)"]):
                paths.append(os.path.join(os.environ["PROGRAMFILES(X86)"], "qemu"))
            if "PROGRAMFILES" in os.environ and os.path.exists(os.environ["PROGRAMFILES"]):
                paths.append(os.path.join(os.environ["PROGRAMFILES"], "qemu"))
        elif sys.platform.startswith("darwin"):
            # add a specific location on Mac OS X regardless of what's in $PATH
            paths.append("/usr/local/bin")
        for path in paths:
            try:
                for f in os.listdir(path):
                    if f.startswith("qemu-system") and os.access(os.path.join(path, f), os.X_OK):
                        qemu_path = os.path.join(path, f)
                        version = self._get_qemu_version(qemu_path)
                        qemus.append({"path": qemu_path, "version": version})
            except OSError:
                continue

        response = {"server": self._host,
                    "qemus": qemus}
        self.send_response(response)

    @IModule.route("qemu.echo")
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
