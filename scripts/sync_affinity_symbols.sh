#!/bin/sh
#
# Copyright (C) 2021 GNS3 Technologies Inc.
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
# This script will sync the affinity symbols
#

rm -Rf /tmp/gns3-affinity

git clone https://github.com/grossmj/affinity.git /tmp/gns3-affinity
rm -rf /tmp/gns3-affinity/svg/naked

for file in $(find "/tmp/gns3-affinity/svg" -name "*.svg")
do
  mv "$file" "`dirname $file`/`basename $file | sed -r "s/^(.*)_(blue|green|red).svg$/\1.svg/" | sed -r "s/(c|sq)_(.*)$/\2/"`";
done

for file in $(find "/tmp/gns3-affinity/svg" -name "*.svg")
do
  sed -i -r 's/width="100%"/width="60"/' $file
  sed -i -r 's/height="100%"/height="60"/' $file
  svgo --pretty $file  # install instructions for svgo on https://github.com/svg/svgo
done

rm -rf gns3server/symbols/affinity
mv /tmp/gns3-affinity/svg gns3server/symbols/affinity
