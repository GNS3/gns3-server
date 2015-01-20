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

# __version__ is a human-readable version number.

# __version_info__ is a four-tuple for programmatic comparison. The first
# three numbers are the components of the version number. The fourth
# is zero for an official release, positive for a development branch,
# or negative for a release candidate or beta (after the base version
# number has been incremented)

import os
import sys
import json
import logging
import socket

from gns3dms.cloud.rackspace_ctrl import RackspaceCtrl


LOG_NAME = "gns3dms.rksp"
log = logging.getLogger("%s" % (LOG_NAME))


class Rackspace(object):

    def __init__(self, options):
        self.username = options["cloud_user_name"]
        self.apikey = options["cloud_api_key"]
        self.authenticated = False
        self.hostname = socket.gethostname()
        self.instance_id = options["instance_id"]
        self.region = options["cloud_region"]

        log.debug("Authenticating with Rackspace")
        log.debug("My hostname: %s" % (self.hostname))
        self.rksp = RackspaceCtrl(self.username, self.apikey)
        self.authenticated = self.rksp.authenticate()

    def _find_my_instance(self):
        if self.authenticated is not False:
            log.critical("Not authenticated against rackspace!!!!")

        for region in self.rksp.list_regions():
            log.debug("Rackspace regions: %s" % (region))

        log.debug("Checking region: %s" % (self.region))
        self.rksp.set_region(self.region)
        for server in self.rksp.list_instances():
            log.debug("Checking server: %s" % (server.name))
            if server.id == self.instance_id:
                log.info("Found matching instance: %s" % (server.id))
                log.info("Startup id: %s" % (self.instance_id))
                return server

    def terminate(self):
        server = self._find_my_instance()
        log.warning("Sending termination")
        self.rksp.delete_instance(server)
