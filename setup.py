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

import sys
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

# we only support Python 3 version >= 3.4
if len(sys.argv) >= 2 and sys.argv[1] == "install" and sys.version_info < (3, 4):
    raise SystemExit("Python 3.4 or higher is required")


class PyTest(TestCommand):

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest

        errcode = pytest.main(self.test_args)
        sys.exit(errcode)

dependencies = open("requirements.txt", "r").read().splitlines()

setup(
    name="gns3-server",
    version=__import__("gns3server").__version__,
    url="http://github.com/GNS3/gns3-server",
    license="GNU General Public License v3 (GPLv3)",
    tests_require=["pytest", "pytest-capturelog"],
    cmdclass={"test": PyTest},
    description="GNS3 server",
    long_description=open("README.rst", "r").read(),
    install_requires=dependencies,
    entry_points={
        "console_scripts": [
            "gns3server = gns3server.main:main",
            "gns3vmnet = gns3server.utils.vmnet:main",
            "gns3loopback = gns3server.utils.windows_loopback:main"
        ]
    },
    packages=find_packages(".", exclude=["docs", "tests"]),
    include_package_data=True,
    zip_safe=False,
    platforms="any",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Information Technology",
        "Topic :: System :: Networking",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
