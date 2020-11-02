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
# Install GNS3 on a remote Ubuntu LTS server
# This create a dedicated user and setup all the package
# and optionnaly a VPN
#

function help {
  echo "Usage:" >&2
  echo "--with-openvpn: Install Open VPN" >&2
  echo "--with-iou: Install IOU" >&2
  echo "--with-i386-repository: Add the i386 repositories required by IOU if they are not already available on the system. Warning: this will replace your source.list in order to use the official Ubuntu mirror" >&2
  echo "--unstable: Use the GNS3 unstable repository"
  echo "--help: This help" >&2
}

function log {
  echo "=> $1"  >&2
}

lsb_release -d | grep "LTS" > /dev/null
if [ $? != 0 ]
then
  echo "This script can only be run on a Linux Ubuntu LTS release"
  exit 1
fi

# Read the options
USE_VPN=0
USE_IOU=0
I386_REPO=0
UNSTABLE=0

TEMP=`getopt -o h --long with-openvpn,with-iou,with-i386-repository,unstable,help -n 'gns3-remote-install.sh' -- "$@"`
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
        --with-iou)
          USE_IOU=1
          shift
          ;;
        --with-i386-repository)
          I386_REPO=1
          shift
          ;;
        --unstable)
          UNSTABLE=1
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
UBUNTU_CODENAME=`lsb_release -c -s`

log "Add GNS3 repository"

if [ "$UBUNTU_CODENAME" == "trusty" ]
then
    if [ $UNSTABLE == 1 ]
    then
        cat <<EOFLIST > /etc/apt/sources.list.d/gns3.list
deb http://ppa.launchpad.net/gns3/unstable/ubuntu $UBUNTU_CODENAME main
deb-src http://ppa.launchpad.net/gns3/unstable/ubuntu $UBUNTU_CODENAME main
deb http://ppa.launchpad.net/gns3/qemu/ubuntu $UBUNTU_CODENAME main
deb-src http://ppa.launchpad.net/gns3/qemu/ubuntu $UBUNTU_CODENAME main
EOFLIST
    else
        cat <<EOFLIST > /etc/apt/sources.list.d/gns3.list
deb http://ppa.launchpad.net/gns3/ppa/ubuntu $UBUNTU_CODENAME main
deb-src http://ppa.launchpad.net/gns3/ppa/ubuntu $UBUNTU_CODENAME main
deb http://ppa.launchpad.net/gns3/qemu/ubuntu $UBUNTU_CODENAME main 
deb-src http://ppa.launchpad.net/gns3/qemu/ubuntu $UBUNTU_CODENAME main 
EOFLIST
    fi
else
    if [ $UNSTABLE == 1 ]
    then
        cat <<EOFLIST > /etc/apt/sources.list.d/gns3.list
deb http://ppa.launchpad.net/gns3/unstable/ubuntu $UBUNTU_CODENAME main
deb-src http://ppa.launchpad.net/gns3/unstable/ubuntu $UBUNTU_CODENAME main
EOFLIST
    else
       cat <<EOFLIST > /etc/apt/sources.list.d/gns3.list
deb http://ppa.launchpad.net/gns3/ppa/ubuntu $UBUNTU_CODENAME main
deb-src http://ppa.launchpad.net/gns3/ppa/ubuntu $UBUNTU_CODENAME main
EOFLIST
    fi
fi

if [ $I386_REPO == 1 ]
then
    cat <<EOFLIST2  >> /etc/apt/sources.list
###### Ubuntu Main Repos
deb http://archive.ubuntu.com/ubuntu/ $UBUNTU_CODENAME main universe multiverse 
deb-src http://archive.ubuntu.com/ubuntu/ $UBUNTU_CODENAME main universe multiverse 

###### Ubuntu Update Repos
deb http://archive.ubuntu.com/ubuntu/ ${UBUNTU_CODENAME}-security main universe multiverse 
deb http://archive.ubuntu.com/ubuntu/ ${UBUNTU_CODENAME}-updates main universe multiverse 
deb-src http://archive.ubuntu.com/ubuntu/ ${UBUNTU_CODENAME}-security main universe multiverse 
deb-src http://archive.ubuntu.com/ubuntu/ ${UBUNTU_CODENAME}-updates main universe multiverse 
EOFLIST2
fi

apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys A2E3EF7B

log "Update system packages"
apt-get update

log "Upgrade packages"
apt-get upgrade --yes --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

log " Install GNS3 packages"
apt-get install -y gns3-server

log "Create user GNS3 with /opt/gns3 as home directory"
if [ ! -d "/opt/gns3/" ]
then
  useradd -d /opt/gns3/ -m gns3
fi


log "Add GNS3 to the ubridge group"
usermod -aG ubridge gns3

log "Install docker"
if [ ! -f "/usr/bin/docker" ]
then
  curl -sSL https://get.docker.com | bash
fi

log "Add GNS3 to the docker group"
usermod -aG docker gns3

if [ $USE_IOU == 1 ]
then
    log "IOU setup"
    dpkg --add-architecture i386
    apt-get update

    apt-get install -y gns3-iou

    # Force the host name to gns3vm
    echo gns3vm > /etc/hostname

    # Force hostid for IOU
    dd if=/dev/zero bs=4 count=1 of=/etc/hostid

    # Block iou call. The server is down
    echo "127.0.0.254 xml.cisco.com" | tee --append /etc/hosts
fi

log "Add gns3 to the kvm group"
usermod -aG kvm gns3

log "Setup GNS3 server"

mkdir -p /etc/gns3
cat <<EOFC > /etc/gns3/gns3_server.conf
[Server]
host = 0.0.0.0
port = 3080 
images_path = /opt/gns3/images
projects_path = /opt/gns3/projects
appliances_path = /opt/gns3/appliances
configs_path = /opt/gns3/configs
report_errors = True

[Qemu]
enable_kvm = True
require_kvm = True
EOFC

chown -R gns3:gns3 /etc/gns3
chmod -R 700 /etc/gns3

if [ "$UBUNTU_CODENAME" == "trusty" ]
then
cat <<EOFI > /etc/init/gns3.conf
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
EOFI

chown root:root /etc/init/gns3.conf
chmod 644 /etc/init/gns3.conf


log "Start GNS3 service"
set +e
service gns3 stop
set -e
service gns3 start

else
    # Install systemd service
    cat <<EOFI > /lib/systemd/system/gns3.service
[Unit]
Description=GNS3 server
After=network-online.target
Wants=network-online.target
Conflicts=shutdown.target

[Service]
User=gns3
Group=gns3
PermissionsStartOnly=true
EnvironmentFile=/etc/environment
ExecStartPre=/bin/mkdir -p /var/log/gns3 /var/run/gns3
ExecStartPre=/bin/chown -R gns3:gns3 /var/log/gns3 /var/run/gns3
ExecStart=/usr/bin/gns3server --log /var/log/gns3/gns3.log
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5
LimitNOFILE=16384

[Install]
WantedBy=multi-user.target
EOFI
    chmod 755 /lib/systemd/system/gns3.service
    chown root:root /lib/systemd/system/gns3.service

    log "Start GNS3 service"
    systemctl enable gns3
    systemctl start gns3
fi

log "GNS3 installed with success"

if [ $USE_VPN == 1 ]
then
log "Setup VPN"

cat <<EOFSERVER > /etc/gns3/gns3_server.conf
[Server]
host = 172.16.253.1
port = 3080 
images_path = /opt/gns3/images
projects_path = /opt/gns3/projects
report_errors = True

[Qemu]
enable_kvm = True
require_kvm = True
EOFSERVER

log "Install packages for Open VPN"

apt-get install -y     \
	openvpn              \
	uuid                 \
  dnsutils             \
  nginx-light

MY_IP_ADDR=$(dig @ns1.google.com -t txt o-o.myaddr.l.google.com +short -4 | sed 's/"//g')

log "IP detected: $MY_IP_ADDR"

UUID=$(uuid)

log "Update motd"

cat <<EOFMOTD > /etc/update-motd.d/70-openvpn
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
EOFMOTD
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
cat <<EOFCLIENT > /root/client.ovpn
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
EOFCLIENT

cat <<EOFUDP > /etc/openvpn/udp1194.conf
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
EOFUDP

echo "Setup HTTP server for serving client certificate"
mkdir -p /usr/share/nginx/openvpn/$UUID
cp /root/client.ovpn /usr/share/nginx/openvpn/$UUID/$HOSTNAME.ovpn
touch /usr/share/nginx/openvpn/$UUID/index.html
touch /usr/share/nginx/openvpn/index.html

cat <<EOFNGINX > /etc/nginx/sites-available/openvpn
server {
	listen 8003;
    root /usr/share/nginx/openvpn;
}
EOFNGINX

[ -f /etc/nginx/sites-enabled/openvpn ] || ln -s /etc/nginx/sites-available/openvpn /etc/nginx/sites-enabled/
service nginx stop
service nginx start

log "Restart OpenVPN"

set +e
service openvpn stop
service openvpn start

log "Download http://$MY_IP_ADDR:8003/$UUID/$HOSTNAME.ovpn to setup your OpenVPN client after rebooting the server"

fi
