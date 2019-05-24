#!/bin/sh
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

#
# Build the documentation
#

set -e

echo "WARNING: This script should be run at the root directory of the project"

export PYTEST_BUILD_DOCUMENTATION=1

rm -Rf docs/api/
mkdir -p docs/api/examples

python3 -m pytest -v tests

export PYTHONPATH=.
python3 gns3server/web/documentation.py
cd docs
make html
