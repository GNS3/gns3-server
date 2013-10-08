#!/usr/bin/env python
# -*- coding: UTF-8 -*-
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

# Python 2.6 and 2.7 compatibility
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import tornado.ioloop
import tornado.web
import gns3server
from datetime import date

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Ready to serve")

application = tornado.web.Application([
    (r"/", MainHandler),
])

if __name__ == "__main__":

    print("GNS3 server version {0}".format(gns3server.__version__))
    print("Copyright (c) 2007-{0} GNS3 Technologies Inc.".format(date.today().year))

    if sys.version_info < (2, 6):
        raise RuntimeError("Python 2.6 or higher is required")
    elif sys.version_info[0] == 3 and sys.version_info < (3, 3):
        raise RuntimeError("Python 3.3 or higher is required")

    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

