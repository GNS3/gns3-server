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
PATH=/gns3/bin:/tmp/gns3/bin:/sbin:$PATH

# bootstrap busybox commands
if [ ! -d /tmp/gns3/bin ]; then
	busybox mkdir -p /tmp/gns3/bin
	for applet in `busybox --list`
	do
	  ln -s /gns3/bin/busybox "/tmp/gns3/bin/$applet"
	done
fi

#  Restore file permission and mount volumes
echo "$GNS3_VOLUMES" | tr ":" "\n" | while read i
do
    # ensure, that the mount directory exists
    mkdir -p "$i"

    # Copy original files if destination is empty (first start)
    if [ ! -f "/gns3volumes$i/.gns3_perms" ]; then
        cp -a "$i/." "/gns3volumes$i"
    fi
    if [ ! -s "/gns3volumes$i/.gns3_perms" ]; then
        # Record the image-side ownership of the whole tree; the bind
        # mount below is not in place yet, so "$i" still shows the
        # image's own directory. This is the first-start counterpart of
        # the stop-time record: without it a brand-new node has no
        # record at all and images running as a non-root USER find
        # their volumes owned by the server user inside the container.
        # A file that exists but is empty (e.g. a failed stop-time
        # record) is refreshed the same way; existing data is never
        # re-copied over.
        find "$i" -depth -print0 | xargs -0 stat -c '%a:%u:%g:%n' \
            > "/gns3volumes$i/.gns3_perms"
    fi

    mount --bind "/gns3volumes$i" "$i"
    while IFS=: read PERMS OWNER GROUP FILE
    do
        [ -L "$FILE" ] || chmod "$PERMS" "$FILE"
        chown -h "${OWNER}:${GROUP}" "$FILE"
    done < "$i/.gns3_perms"
done

# A startup configuration for FRR is staged by the server and installed once, here: after the first
# start has seeded /etc/frr from the image, which would otherwise overwrite it.
if [ -f /etc/frr/.gns3-startup.conf ]; then
    cat /etc/frr/.gns3-startup.conf > /etc/frr/frr.conf && rm -f /etc/frr/.gns3-startup.conf
    chown frr:frr /etc/frr/frr.conf 2>/dev/null
    chmod 640 /etc/frr/frr.conf
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

# imitate docker's `ExtraHosts` behaviour
sed -i '/GNS3_EXTRA_HOSTS_START/,/GNS3_EXTRA_HOSTS_END/d' /etc/hosts
[ -n "$GNS3_EXTRA_HOSTS" ] && cat >> /etc/hosts << __EOF__
# GNS3_EXTRA_HOSTS_START
$GNS3_EXTRA_HOSTS
# GNS3_EXTRA_HOSTS_END
__EOF__

# configure loopback interface
ip link set dev lo up

# Wait for all eth available
while true 
do
    grep $GNS3_MAX_ETHERNET /proc/net/dev > /dev/null && break
    usleep 500000  # wait 0.5 seconds
done  

# activate eth interfaces
sed -n 's/^ *\(eth[0-9]*\):.*/\1/p' < /proc/net/dev | while read dev; do
	ip link set dev $dev up
done

# configure network interfaces
# NOTE: unless the image ships its own ifupdown in /sbin this is BusyBox ifup,
# which only brings up 'auto' stanzas and does NOT understand CIDR notation:
# 'address <ip>' and 'netmask <mask>' must be separate lines, otherwise the
# stanza fails with "don't have all variables for <iface>/inet" and the
# interface comes up unconfigured.
ifup -a -f

# continue normal docker startup
# Docker allows USER user:group and USER uid:gid; su only takes one
# account, so keep the user part (the declared group is ignored).
if [ -n "${GNS3_USER:-}" ]; then
    GNS3_USER=${GNS3_USER%%:*}
fi
case "$GNS3_USER" in
  [0-9]*)
    # numeric UID: resolve it to an account name with an exact match on
    # the UID field (a loose grep could pick a wrong account)
    mapped=$(awk -F: -v u="$GNS3_USER" '$3 == u { print $1; exit }' /etc/passwd)
    if [ -n "$mapped" ]; then
        export GNS3_USER="$mapped"
    else
        # no passwd entry: create one so su can drop to this UID/GID,
        # then su must use that new name (it looks accounts up by name)
        echo "gns3uid${GNS3_USER}:x:${GNS3_USER}:${GNS3_USER}::/tmp:/bin/sh" >> /etc/passwd
        export GNS3_USER="gns3uid${GNS3_USER}"
    fi
    ;;
  *)
    ;;
esac
eval HOME="$(echo ~${GNS3_USER-root})"

# An image may declare a user whose login shell refuses commands,
# e.g. osixia/openldap 2.x declares USER ldap with /sbin/nologin.
# su then exits 1 right away and the container never boots.
# Docker's USER never uses a login shell, so pick a real shell here.
SU_SHELL_ARG=""
if [ -n "${GNS3_USER:-}" ]; then
    user_shell=$(awk -F: -v u="$GNS3_USER" '$1 == u { print $7; exit }' /etc/passwd)
    case "$user_shell" in
        */nologin|*/false|*/true)
            SU_SHELL_ARG="-s /bin/sh"
            ;;
        "")
            # account not in /etc/passwd: let su report its own error
            ;;
        *)
            [ -x "$user_shell" ] || SU_SHELL_ARG="-s /bin/sh"
            ;;
    esac
fi
exec su ${GNS3_USER-root} ${SU_SHELL_ARG} -p -- /gns3/run-cmd.sh "$OLD_PATH" "$@"
