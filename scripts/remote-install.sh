#!/bin/bash
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
# Install GNS3 on a remote Ubuntu 14.04 LTS server
# This create a dedicated user and setup all the package
# and optionnaly a VPN
#

function help {
  echo "Usage:" >&2
  echo "--with-openvpn: Install Open VPN" >&2
  echo "--help: This help" >&2
}

function log {
  tput setaf 2
  echo "=> $1"  >&2
  tput sgr0
}

lsb_release -d | grep "Ubuntu 14.04" > /dev/null
if [ $? != 0 ]
then
  echo "You can use this script on Ubuntu 14.04 LTS only"
  exit 1
fi

# Read the options
USE_VPN=0

TEMP=`getopt -o h --long with-openvpn,help -n 'gns3-remote-install.sh' -- "$@"`
if [ $? != 0 ]
then
  help
  exit 1
fi
eval set -- "$TEMP"

# extract options and their arguments into variables.
while true ; do
    case "$1" in
        --with-openvpn)
          USE_VPN=1
          shift
          ;;
        -h|--help)
          help
          exit 1
          ;;
        --) shift ; break ;;
        *) echo "Internal error! $1" ; exit 1 ;;
    esac
done

# Exit in case of error
set -e

export DEBIAN_FRONTEND="noninteractive"

log "Add GNS3 repository"
cat > /etc/apt/sources.list.d/gns3.list << EOF
deb http://ppa.launchpad.net/gns3/ppa/ubuntu trusty main
deb-src http://ppa.launchpad.net/gns3/ppa/ubuntu trusty main
deb http://ppa.launchpad.net/gns3/qemu/ubuntu trusty main 
deb-src http://ppa.launchpad.net/gns3/qemu/ubuntu trusty main 
EOF

apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A2E3EF7B

log "Update system packages"
dpkg --add-architecture i386
apt-get update

log "Upgrade packages"
apt-get upgrade -y

log " Install GNS3 packages"
apt-get install -y gns3-server

log "Create user GNS3 with /opt/gns3 as home directory"
if [ ! -d "/opt/gns3/" ]
then
  useradd -d /opt/gns3/ -m gns3
fi

log "Install docker"
if [ ! -f "/usr/bin/docker" ]
then
  curl -sSL https://get.docker.com | bash
fi

log "Add GNS3 to the docker group"
usermod -aG docker gns3

log "IOU setup"
#apt-get install -y gns3-iou

# Force the host name to gns3vm
hostnamectl set-hostname gns3vm

# Force hostid for IOU
dd if=/dev/zero bs=4 count=1 of=/etc/hostid

# Block iou call. The server is down
echo "127.0.0.254 xml.cisco.com" | tee --append /etc/hosts

log "Add gns3 to the kvm group"
usermod -aG kvm gns3

log "Setup VDE network"

apt-get install -y vde2 uml-utilities

usermod -a -G vde2-net gns3

cat <<EOF > /etc/network/interfaces.d/qemu0.conf
# A vde network
auto qemu0
    iface qemu0 inet static
    address 172.16.0.1
    netmask 255.255.255.0
    vde2-switch -t qemu0
EOF 

log "Setup GNS3 server"


#TODO: 1.4.5 allow /etc/gns3/gns3_server.conf it's cleaner
cat <<EOF > /opt/gns3/gns3_server.conf
[Server]
host = 0.0.0.0
port = 8000
images_path = /opt/gns3/images
projects_path = /opt/gns3/projects
report_errors = True

[Qemu]
enable_kvm = True
EOF

cat <<EOF > /etc/init/gns3.conf
description "GNS3 server"
author      "GNS3 Team"

start on filesystem or runlevel [2345]
stop on runlevel [016]
respawn
console log


script
    exec start-stop-daemon --start --make-pidfile --pidfile /var/run/gns3.pid --chuid gns3 --exec "/usr/bin/gns3server"
end script

pre-start script
    echo "" > /var/log/upstart/gns3.log
    echo "[`date`] GNS3 Starting"
end script

pre-stop script
    echo "[`date`] GNS3 Stopping"
end script
EOF

chown root:root /etc/init/gns3.conf
chmod 644 /etc/init/gns3.conf


log "Start GNS3 service"
set +e
service gns3 stop
set -e
service gns3 start

log "GNS3 installed with success"

if [ $USE_VPN == 1 ]
then
log "Setup VPN"

cat <<EOF > /opt/gns3/gns3_server.conf
[Server]
host = 172.16.253.1
port = 8000
images_path = /opt/gns3/images
projects_path = /opt/gns3/projects
report_errors = True

[Qemu]
enable_kvm = True
EOF

log "Install packages for Open VPN"

apt-get install -y     \
	openvpn              \
	uuid                 \
  dnsutils             \
  nginx-light

MY_IP_ADDR=$(dig @ns1.google.com -t txt o-o.myaddr.l.google.com +short | sed 's/"//g')

log "IP detected: $MY_IP_ADDR"

UUID=$(uuid)

log "Update motd"

cat <<EOF > /etc/update-motd.d/70-openvpn
#!/bin/sh
echo ""
echo "_______________________________________________________________________________________________"
echo "Download the VPN configuration here:"
echo "http://$MY_IP_ADDR:8003/$UUID/$HOSTNAME.ovpn"
echo ""
echo "And add it to your openvpn client."
echo ""
echo "apt-get remove nginx-light to disable the HTTP server."
echo "And remove this file with rm /etc/update-motd.d/70-openvpn"
EOF
chmod 755 /etc/update-motd.d/70-openvpn


mkdir -p /etc/openvpn/

[ -d /dev/net ] || mkdir -p /dev/net
[ -c /dev/net/tun ] || mknod /dev/net/tun c 10 200

log "Create keys"

[ -f /etc/openvpn/dh.pem ] || openssl dhparam -out /etc/openvpn/dh.pem 2048
[ -f /etc/openvpn/key.pem ] || openssl genrsa -out /etc/openvpn/key.pem 2048
chmod 600 /etc/openvpn/key.pem
[ -f /etc/openvpn/csr.pem ] || openssl req -new -key /etc/openvpn/key.pem -out /etc/openvpn/csr.pem -subj /CN=OpenVPN/
[ -f /etc/openvpn/cert.pem ] || openssl x509 -req -in /etc/openvpn/csr.pem -out /etc/openvpn/cert.pem -signkey /etc/openvpn/key.pem -days 24855

log "Create client configuration"
cat <<EOF > /root/client.ovpn
client
nobind
comp-lzo
dev tun
<key>
`cat /etc/openvpn/key.pem`
</key>
<cert>
`cat /etc/openvpn/cert.pem`
</cert>
<ca>
`cat /etc/openvpn/cert.pem`
</ca>
<dh>
`cat /etc/openvpn/dh.pem`
</dh>
<connection>
remote $MY_IP_ADDR 1194 udp
</connection>
EOF

cat <<EOF > /etc/openvpn/udp1194.conf
server 172.16.253.0 255.255.255.0
verb 3
duplicate-cn
comp-lzo
key key.pem
ca cert.pem
cert cert.pem
dh dh.pem
keepalive 10 60
persist-key
persist-tun
proto udp
port 1194
dev tun1194
status openvpn-status-1194.log
log-append /var/log/openvpn-udp1194.log
EOF

echo "Setup HTTP server for serving client certificate"
mkdir -p /usr/share/nginx/openvpn/$UUID
cp /root/client.ovpn /usr/share/nginx/openvpn/$UUID/$HOSTNAME.ovpn
touch /usr/share/nginx/openvpn/$UUID/index.html
touch /usr/share/nginx/openvpn/index.html

cat <<EOF > /etc/nginx/sites-available/openvpn
server {
	listen 8003;
    root /usr/share/nginx/openvpn;
}
EOF
[ -f /etc/nginx/sites-enabled/openvpn ] || ln -s /etc/nginx/sites-available/openvpn /etc/nginx/sites-enabled/
service nginx stop
service nginx start

log "Restart OpenVPN"

set +e
service openvpn stop
service openvpn start

log "Download http://$MY_IP_ADDR:8003/$UUID/$HOSTNAME.ovpn to setup your OpenVPN client"

fi
