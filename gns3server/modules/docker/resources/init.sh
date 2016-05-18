#!/gns3/bin/busybox sh
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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
# This script is injected into the container and launch before
# the start command of the container
#
OLD_PATH="$PATH"
PATH=/gns3/bin:/tmp/gns3/bin

# bootstrap busybox commands
if [ ! -d /tmp/gns3/bin ]; then
	busybox mkdir -p /tmp/gns3/bin
	/gns3/bin/busybox --install -s /tmp/gns3/bin
fi

# /etc/hosts
[ -s /etc/hosts ] || cat > /etc/hosts << __EOF__
127.0.1.1	$HOSTNAME
127.0.0.1	localhost
::1	localhost ip6-localhost ip6-loopback
fe00::0	ip6-localnet
ff00::0	ip6-mcastprefix
ff02::1	ip6-allnodes
ff02::2	ip6-allrouters
__EOF__

# configure loopback interface
ip link set dev lo up

# Wait for all eth available
while true 
do
    grep $GNS3_MAX_ETHERNET /proc/net/dev > /dev/null && break
    sleep 0.5
done  

# activate eth interfaces
sed -n 's/^ *\(eth[0-9]*\):.*/\1/p' < /proc/net/dev | while read dev; do
	ip link set dev $dev up
done

# configure network interfaces
ifup -a -f

# continue normal docker startup
PATH="$OLD_PATH"
exec "$@"
