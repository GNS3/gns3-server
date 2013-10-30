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

import logging
import tornado.web
from gns3server.plugins import IPlugin

logger = logging.getLogger(__name__)


class TestHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("This is my test handler")


class Dynamips(IPlugin):

    def __init__(self):
        IPlugin.__init__(self)
        logger.info("Dynamips plugin is initializing")

    def handlers(self):
        """Returns tornado web request handlers that the plugin manages

        :returns: List of tornado.web.RequestHandler
        """

        return [(r"/test", TestHandler)]
