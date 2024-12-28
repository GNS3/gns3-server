#!/bin/bash
#
# Copyright (C) 2024 GNS3 Technologies Inc.
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
# Install GNS3 on a remote Ubuntu server
# This creates a dedicated user and setup all the packages
# and optionally a VPN
#

function help {
  echo "Usage:" >&2
  echo "--with-openvpn: Install OpenVPN" >&2
  echo "--with-iou: Install IOU support" >&2
  echo "--with-i386-repository: Add the i386 repositories required by IOU i386 images. This is not needed for recent x86_64 IOU images." >&2
  echo "--with-welcome: Install GNS3-VM welcome.py script" >&2
  echo "--without-kvm: Disable KVM, required if system do not support it (limitation in some hypervisors and cloud providers). Warning: only disable KVM if strictly necessary as this will degrade performance" >&2
  echo "--unstable: Use the GNS3 unstable repository" >&2
  echo "--custom-repository <repository>: Use a custom repository" >&2
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

# Default repository
REPOSITORY="ppa"

# Read the options
USE_VPN=0
USE_IOU=0
I386_REPO=0
DISABLE_KVM=0
WELCOME_SETUP=0

TEMP=`getopt -o h --long with-openvpn,with-iou,with-i386-repository,with-welcome,without-kvm,unstable,custom-repository:,help -n 'gns3-remote-install.sh' -- "$@"`
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
        --with-welcome)
          WELCOME_SETUP=1
          shift
          ;;
        --without-kvm)
          DISABLE_KVM=1
          shift
          ;;
        --unstable)
          REPOSITORY="unstable"
          shift
          ;;
        --custom-repository)
          REPOSITORY="$2"
          shift 2
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

if [ ! -f "/etc/apt/sources.list.d/ubuntu.sources" ]
then
    apt-key adv --keyserver keyserver.ubuntu.com --recv-keys B83AAABFFBD82D21B543C8EA86C22C2EC6A24D7F
    cat <<EOFLIST > /etc/apt/sources.list.d/gns3.list
deb http://ppa.launchpad.net/gns3/ppa/ubuntu $UBUNTU_CODENAME main
deb-src http://ppa.launchpad.net/gns3/ppa/ubuntu $UBUNTU_CODENAME main
EOFLIST

else

    cat <<EOFLIST > /etc/apt/sources.list.d/gns3-ppa.sources
Types: deb
URIs: https://ppa.launchpadcontent.net/gns3/$REPOSITORY/ubuntu/
Suites: $UBUNTU_CODENAME
Components: main
Signed-By:
 -----BEGIN PGP PUBLIC KEY BLOCK-----
 .
 mQINBGY0jSYBEADMH5CvX8ZVX4XzAxdQ2CmF7t86IjFnQgtI18Q19nVnpKEGNyB5
 pgotDMzkhGnxuhvz2zE9PZhd8VgkodB81V607d/Dy8FfI7t1BVQhLvJDx0H/q6RE
 n2y9WxiuBzTHitoQTCTY3hjcr7AUNFFI64gUqwbkQmYbCWWsYOlDpRSkWKg8P8WK
 08RetwTI0Iwoz8j+BkbPlubuImiVfh1TeH23FBuGIwL1r1Cps0wel6JAi+jaU9WG
 j8MX3mQYFTAtk7f1lRubqWosB/A4xIu609pF1e1tAkWAGltYAeoFhDn+PfA9KgmV
 fvxfVR7zmxp31imTJgXgUFCz+H0Xb3vpve8XsrsHZUP6StJ3+6cFXjNBV6PuO1FT
 JWp86a+AYHg7+sUWcoJRZPCTbb/pOcCa0q1ch5qcLkiYEOGK+pYhbPptq6y8IsJW
 N6EDNCVvVqVyTJy14FZWoOqxcpUiDOQ+su28j8++V+PMo+FO3SQqwEZwJXk7LF/4
 wUipDCUh/WNjDqqgmYLoO+ttiiJPbEw3jtbO+zopbzYpyEC1f06Nz7uz1daOIN3J
 etFPzSqWCE7Eq+hoVmAAm8gVmQir3rFJbIGBAvAaOLQEOkUlOlS7AezqUhdyhGER
 Zrvc3eNqxY7G61SEHipEJ7/hpcDq0RRWCXHsoQqyHaPje826n2pGkJYt4QARAQAB
 tBZMYXVuY2hwYWQgUFBBIGZvciBHTlMziQJOBBMBCgA4FiEEuDqqv/vYLSG1Q8jq
 hsIsLsaiTX8FAmY0jSYCGwMFCwkIBwIGFQoJCAsCBBYCAwECHgECF4AACgkQhsIs
 LsaiTX9z9xAAq1uHmRgfYmELS0cr2YEnTWHPVE6s95Qx+0cr5zzNeWfmoAS9uSyl
 z8bCm+Q2ZapzU/nOtkozU+RGjgcRRTKMVTyS0PjFX22965xHCRWnw79fPyrYouUw
 H2cAT8WSGYEeVAbqhJSns0RnDpXuaxmWE1wT+iitY/QAjeXo22Z2mjv2bFTitKbY
 hZbE5Eu8Olc5YHCVI0ofq84/Ii921iMibU6EDMmm/iOnMK2uHGbC59t0YG8Rm7mK
 uk6+TpxOULjFeCWSkF2Dr33m8JQmtYZuFUnmqWPuSdBo3J0O1b0qTg+EP9FbDAtj
 CoEKT/V1ccMBd3r77o23CGsvpV7bzEU60A+NsU8vb/AkOmouYiF+qaYDFGZDfWhK
 p1HFmd1kt7YdgxsmoKoFJkbt1bBdcFJLV0Jcad5sfArg2aFDYf2giMxAw4iQ+9jc
 MCuwWxiqWicPqJ5erNTzVfayBkjuZqBDVTO9wmG3DL4QmNosIBS7kq+NGrT8Ql22
 FqYfdIZJDlKVtJKHK8eKJSB0dbFawV2h5p/CvQlIm6nthg5FzOyjvCkPkvxvveq+
 SuNxFEscumFCgo7j7RMWHW9HWK3TUvMmYLMVjxL8kXyCwknp9GklBQHA/IPxRa/2
 eFqqkmVbmNAoMzzw5wqa/BPcFEbgn+E+TFyZqbzp0F4QzPJZFkz16SA=
 =xnj5
 -----END PGP PUBLIC KEY BLOCK-----
EOFLIST

fi

log "Updating system packages and installing curl"
apt update
apt install -y curl

log "Upgrading packages"
apt upgrade --yes --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

log "Installing the GNS3 server and its dependencies"
apt install -y gns3-server

log "Creating user GNS3 with /opt/gns3 as home directory"
if [ ! -d "/opt/gns3" ]
then
  useradd -m -d /opt/gns3 gns3
fi

log "Adding GNS3 to the ubridge group"
usermod -aG ubridge gns3

log "Installing Docker"
if [ ! -f "/usr/bin/docker" ]
then
  curl -sSL https://get.docker.com | bash
fi

log "Adding GNS3 to the docker group"
usermod -aG docker gns3

if [ $USE_IOU == 1 ]
then
    log "Setting up IOU support"
    if [ $I386_REPO == 1 ]
    then
        log "Enabling i386 architecture for IOU support"
        dpkg --add-architecture i386
        apt update
    fi

    apt install -y gns3-iou

    # Force the host name to gns3vm
    echo gns3vm > /etc/hostname
    hostname gns3vm
    HOSTNAME=$(hostname)

    # Force hostid for IOU
    dd if=/dev/zero bs=4 count=1 of=/etc/hostid
fi

log "Adding gns3 to the kvm group"
usermod -aG kvm gns3

log "Setting up the GNS3 server configuration"

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
enable_hardware_acceleration = True
require_hardware_acceleration = True
EOFC

if [ $DISABLE_KVM == 1 ]
then
    log "Disabling KVM support"
    sed -i 's/hardware_acceleration = True/hardware_acceleration = False/g' /etc/gns3/gns3_server.conf
fi

chown -R gns3:gns3 /etc/gns3
chmod -R 700 /etc/gns3

log "Installing the GNS3 systemd service"
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

log "Starting the GNS3 service"
systemctl enable gns3
systemctl start gns3

log "GNS3 has been installed with success"

if [ $WELCOME_SETUP == 1 ]
then
cat <<EOFI > /etc/sudoers.d/gns3
gns3   ALL = (ALL) NOPASSWD: /usr/bin/apt-key
gns3   ALL = (ALL) NOPASSWD: /usr/bin/apt-get
gns3   ALL = (ALL) NOPASSWD: /usr/sbin/reboot
EOFI
NEEDRESTART_MODE=a apt install -y net-tools
NEEDRESTART_MODE=a apt install -y dialog
NEEDRESTART_MODE=a apt install -y python3-dialog

#Pull down welcome script from repo
curl https://raw.githubusercontent.com/GNS3/gns3-server/master/scripts/welcome.py > /usr/local/bin/welcome.py

chmod 755 /usr/local/bin/welcome.py
chown gns3:gns3 /usr/local/bin/welcome.py

mkdir /etc/systemd/system/getty@tty1.service.d
cat <<EOFI > /etc/systemd/system/getty@tty1.service.d/override.conf
[Service]
ExecStart=
ExecStart=-/sbin/agetty -a gns3 --noclear %I \$TERM
EOFI

chmod 755 /etc/systemd/system/getty@tty1.service.d/override.conf
chown root:root /etc/systemd/system/getty@tty1.service.d/override.conf

echo "python3 /usr/local/bin/welcome.py" >> /opt/gns3/.bashrc
echo "gns3:gns3" | chpasswd
usermod --shell /bin/bash gns3
usermod -aG sudo gns3

fi

if [ $USE_VPN == 1 ]
then
log "Setting up OpenVPN"

log "Changing the GNS3 server configuration to listen on VPN interface"

sed -i 's/host = 0.0.0.0/host = 172.16.253.1/' /etc/gns3/gns3_server.conf

log "Installing the OpenVPN packages"

apt install -y openvpn uuid dnsutils nginx-light

MY_IP_ADDR=$(dig @ns1.google.com -t txt o-o.myaddr.l.google.com +short -4 | sed 's/"//g')

log "IP detected: $MY_IP_ADDR"

UUID=$(uuid)

log "Updating motd"

cat <<EOFMOTD > /etc/update-motd.d/70-openvpn
#!/bin/sh
echo ""
echo "_______________________________________________________________________________________________"
echo "Download the VPN configuration here:"
echo "http://$MY_IP_ADDR:8003/$UUID/$HOSTNAME.ovpn"
echo ""
echo "And add it to your openvpn client."
echo ""
echo "apt remove nginx-light to disable the HTTP server."
echo "And remove this file with rm /etc/update-motd.d/70-openvpn"
EOFMOTD
chmod 755 /etc/update-motd.d/70-openvpn

mkdir -p /etc/openvpn/

[ -d /dev/net ] || mkdir -p /dev/net
[ -c /dev/net/tun ] || mknod /dev/net/tun c 10 200

log "Creating OpenVPN keys"

[ -f /etc/openvpn/dh.pem ] || openssl dhparam -out /etc/openvpn/dh.pem 2048
[ -f /etc/openvpn/key.pem ] || openssl genrsa -out /etc/openvpn/key.pem 2048
chmod 600 /etc/openvpn/key.pem
[ -f /etc/openvpn/csr.pem ] || openssl req -new -key /etc/openvpn/key.pem -out /etc/openvpn/csr.pem -subj /CN=OpenVPN/
[ -f /etc/openvpn/cert.pem ] || openssl x509 -req -in /etc/openvpn/csr.pem -out /etc/openvpn/cert.pem -signkey /etc/openvpn/key.pem -days 24855

log "Creating OpenVPN client configuration"
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

log "Setting up an HTTP server for serving client certificate"
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

log "Restarting OpenVPN and GNS3"

set +e
service openvpn stop
service openvpn start
service gns3 stop
service gns3 start

log "Please download http://$MY_IP_ADDR:8003/$UUID/$HOSTNAME.ovpn to setup your OpenVPN client after rebooting the server"

fi

if [ $WELCOME_SETUP == 1 ]
then
  NEEDRESTART_MODE=a apt update
  NEEDRESTART_MODE=a apt upgrade
  python3 -c 'import sys; sys.path.append("/usr/local/bin/"); import welcome; ws = welcome.Welcome_dialog(); ws.repair_remote_install()'
  cd /opt/gns3
  su gns3
fi
