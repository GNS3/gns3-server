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

import sys
import os
from setuptools import setup
from setuptools.command.test import test as TestCommand

import gns3_server

class Tox(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True
    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import tox
        errcode = tox.cmdline(self.test_args)
        sys.exit(errcode)

setup(
    name = 'gns3-server',
    scripts = ['gns3-server.py'],
    version = gns3_server.__version__,
    url = 'http://github.com/GNS3/gns3-server',
    license = 'GNU General Public License v3 (GPLv3)',
    tests_require = ['tox'],
    cmdclass = {'test': Tox},
    install_requires = [],
    author = 'Jeremy Grossmann',
    author_email = 'package-maintainer@gns3.net',
    description = 'GNS3 server with HTTP REST API to manage emulators',
    long_description = open('README.rst', 'r').read(),
    packages = ['gns3_server'],
    include_package_data = True,
    platforms = 'any',
    classifiers = [         
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Topic :: System :: Networking'
        ],
)
