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

import inspect
import pkgutil
from .modules import IModule

import logging
log = logging.getLogger(__name__)


class Module(object):
    """
    Module representation for the module manager

    :param name: module name
    :param cls: module class to be instantiated when
    the module is activated
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

    def cls(self):
        return self._cls


class ModuleManager(object):
    """
    Manages modules

    :param module_paths: path from where module are loaded
    """

    def __init__(self, module_paths=['modules']):

        self._modules = []
        self._module_paths = module_paths

    def load_modules(self):
        """
        Finds all the possible modules (classes with IModule as a parent)
        """

        for _, name, ispkg in pkgutil.iter_modules(self._module_paths):
            if (ispkg):
                log.debug("analyzing {} package directory".format(name))
                try:
                    file, pathname, description = imp.find_module(name, self._module_paths)
                    module = imp.load_module(name, file, pathname, description)
                    classes = inspect.getmembers(module, inspect.isclass)
                    for module_class in classes:
                        if issubclass(module_class[1], IModule):
                            # make sure the module class has IModule as a parent
                            if module_class[1].__module__ == name:
                                log.info("loading {} module".format(module_class[0].lower()))
                                info = Module(name=module_class[0].lower(), cls=module_class[1])
                                self._modules.append(info)
                except Exception:
                    log.critical("error while analyzing {} package directory".format(name), exc_info=1)
                finally:
                    if file:
                        file.close()

    def get_all_modules(self):
        """
        Returns all modules.

        :returns: list of Module objects
        """

        return self._modules

    def activate_module(self, module, *args, **kwargs):
        """
        Activates a given module.

        :param module: module to activate (Module object)
        :param args: args passed to the module
        :param kwargs: kwargs passed to the module

        :returns: instantiated module class
        """

        module_class = module.cls()
        try:
            module_instance = module_class(module.name, *args, **kwargs)
        except Exception:
            log.critical("error while activating the {} module".format(module.name), exc_info=1)
            return None
        log.info("activating the {} module".format(module.name))
        return module_instance
