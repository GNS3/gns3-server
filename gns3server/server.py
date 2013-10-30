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
import socket
import tornado.ioloop
import tornado.web
import gns3server

logger = logging.getLogger(__name__)


class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.write("Welcome to the GNS3 server!")


class VersionHandler(tornado.web.RequestHandler):

    def get(self):
        response = {'version': gns3server.__version__}
        self.write(response)


class Server(object):

    # built-in handlers
    handlers = [(r"/", MainHandler),
                (r"/version", VersionHandler)]

    def __init__(self):

        self._plugins = []

    def load_plugins(self):
        """Loads the plugins
        """

        plugin_manager = gns3server.PluginManager()
        plugin_manager.load_plugins()
        for plugin in plugin_manager.get_all_plugins():
            instance = plugin_manager.activate_plugin(plugin)
            self._plugins.append(instance)
            plugin_handlers = instance.handlers()
            self.handlers.extend(plugin_handlers)

    def run(self):
        """Starts the tornado web server
        """

        from tornado.options import options
        tornado_app = tornado.web.Application(self.handlers)
        try:
            port = options.port
            print("Starting server on port {}".format(port))
            tornado_app.listen(port)
        except socket.error as e:
            if e.errno is 48:  # socket already in use
                logging.critical("socket in use for port {}".format(port))
                raise SystemExit
        try:
            tornado.ioloop.IOLoop.instance().start()
        except (KeyboardInterrupt, SystemExit):
            print("\nExiting...")
            tornado.ioloop.IOLoop.instance().stop()
