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

import imp
import inspect
import pkgutil
import logging
from gns3server.plugins import IPlugin

logger = logging.getLogger(__name__)


class Plugin(object):
    """Plugin representation for the PluginManager
    """

    def __init__(self, name, cls):

        self._name = name
        self._cls = cls

    @property
    def name(self):

        return self._name

    @name.setter
    def name(self, new_name):
        self._name = new_name

    #@property
    def cls(self):
        return self._cls


class PluginManager(object):
    """Manages plugins
    """

    def __init__(self, plugin_paths=['plugins']):

        self._plugins = []
        self._plugin_paths = plugin_paths

    def load_plugins(self):

        for _, name, ispkg in pkgutil.iter_modules(self._plugin_paths):
            if (ispkg):
                logger.info("analyzing '{}' package".format(name))
                try:
                    file, pathname, description = imp.find_module(name, self._plugin_paths)
                    plugin_module = imp.load_module(name, file, pathname, description)
                    plugin_classes = inspect.getmembers(plugin_module, inspect.isclass)
                    for plugin_class in plugin_classes:
                        if issubclass(plugin_class[1], IPlugin):
                            # don't instantiate any parent plugins
                            if plugin_class[1].__module__ == name:
                                logger.info("loading '{}' plugin".format(plugin_class[0]))
                                info = Plugin(name=plugin_class[0], cls=plugin_class[1])
                                self._plugins.append(info)
                finally:
                    if file:
                        file.close()

    def get_all_plugins(self):
        return self._plugins

    def activate_plugin(self, plugin):

        plugin_class = plugin.cls()
        plugin_instance = plugin_class()
        logger.info("'{}' plugin activated".format(plugin.name))
        return plugin_instance
