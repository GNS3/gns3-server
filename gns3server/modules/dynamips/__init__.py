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
from .hypervisor import Hypervisor
from .hypervisor_manager import HypervisorManager
from .dynamips_error import DynamipsError
from .nodes.router import Router

import logging
log = logging.getLogger(__name__)


class Dynamips(IModule):

    def __init__(self, name=None, args=(), kwargs={}):
        IModule.__init__(self, name=name, args=args, kwargs=kwargs)
        #self._hypervisor_manager = HypervisorManager("/usr/bin/dynamips", "/tmp")

    @IModule.route("dynamips/echo")
    def echo(self, request):
        print("Echo!")
        log.debug("received request {}".format(request))
        self.send_response(request)

    @IModule.route("dynamips/create_vm")
    def create_vm(self, request):
        print("Create VM!")
        log.debug("received request {}".format(request))
        self.send_response(request)

    @IModule.route("dynamips/start_vm")
    def start_vm(self, request):
        print("Start VM!")
        log.debug("received request {}".format(request))
        self.send_response(request)
