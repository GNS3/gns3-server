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

# we only support Python 3 version >= 3.3
if sys.version_info < (3, 3):
    raise SystemExit("Python 3.3 or higher is required")


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


dependencies = [
    # "gns3-netifaces>=0.10.4.1",
    "aiohttp>=0.14.4",
    "jsonschema>=2.4.0",
    "Jinja2>=2.7.3",
    "raven>=5.2.0"]

# if not sys.platform.startswith("win"):
#    dependencies.append("netifaces==0.10.4")

if sys.version_info == (3, 3):
    dependencies.append("asyncio>=3.4.2")

setup(
    name="gns3-server",
    version=__import__("gns3server").__version__,
    url="http://github.com/GNS3/gns3-server",
    license="GNU General Public License v3 (GPLv3)",
    tests_require=["pytest"],
    cmdclass={"test": PyTest},
    description="GNS3 server",
    long_description=open("README.rst", "r").read(),
    install_requires=dependencies,
    entry_points={
        "console_scripts": [
            "gns3server = gns3server.main:main",
            "gns3dms = gns3dms.main:main",
        ]
    },
    packages=find_packages(".", exclude=["docs", "tests"]),
    package_data={"gns3server": ["templates/upload.html"]},
    include_package_data=True,
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
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
