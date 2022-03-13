# GNS3-server

[![Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![GitHub Actions tests](https://github.com/GNS3/gns3-server/workflows/testing/badge.svg?branch=3.0)](https://github.com/GNS3/gns3-server/actions?query=workflow%3Atesting+branch%3A3.0)
[![Latest PyPi version](https://img.shields.io/pypi/v/gns3-server.svg)](https://pypi.python.org/pypi/gns3-server)
[![Snyk scanning](https://snyk.io/test/github/GNS3/gns3-server/badge.svg)](https://snyk.io/test/github/GNS3/gns3-server)

This is the GNS3 server repository.

The GNS3 server manages emulators such as Dynamips, VirtualBox or Qemu/KVM.
Clients like the [GNS3 GUI](https://github.com/GNS3/gns3-gui/) and the [GNS3 Web UI](https://github.com/GNS3/gns3-web-ui>) control the server using a HTTP REST API.

## Software dependencies

In addition to Python dependencies listed in a section below, other software may be required, recommended or optional.

* [uBridge](https://github.com/GNS3/ubridge/) is required, it interconnects the nodes.
* [Dynamips](https://github.com/GNS3/dynamips/) is required for running IOS routers (using real IOS images) as well as the internal switches and hubs.
* [VPCS](https://github.com/GNS3/vpcs/) is recommended, it is a builtin node simulating a very simple computer to perform connectivity tests using ping, traceroute etc.
* Qemu is strongly recommended on Linux, as most node types are based on Qemu, for example Cisco IOSv and Arista vEOS.
* libvirt is recommended (Linux only), as it's needed for the NAT cloud.
* Docker is optional (Linux only), some nodes are based on Docker.
* mtools is recommended to support data transfer to/from QEMU VMs using virtual disks.
* i386-libraries of libc and libcrypto are optional (Linux only), they are only needed to run IOU based nodes.

### Docker support

Docker support needs the script program (`bsdutils` or `util-linux` package), when running a docker VM and a static busybox during installation (python3 setup.py install / pip3 install / package creation).

## Branches

### master

master is the next stable release, you can test it in your day-to -day activities.
Bug fixes or small improvements pull requests go here.

3.x
Development brand for the next major release

**Never** use this branch for production. Pull requests for major new features go here.

## Linux

GNS3 is perhaps packaged for your distribution:

* [Gentoo](https://packages.gentoo.org/package/net-misc/gns3-server)
* [Alpine](https://pkgs.alpinelinux.org/package/v3.10/community/x86_64/gns3-server)
* [NixOS](https://search.nixos.org/packages?channel=21.11&from=0&size=50&sort=relevance&type=packages&query=gns3-server)


### Linux (Debian based)

The following instructions have been tested with Ubuntu and Mint.
You must be connected to the Internet in order to install the dependencies.

### Dependencies:

- Python >= 3.6, setuptools and the ones listed in [requirements.txt](https://github.com/GNS3/gns3-server/blob/3.0/requirements.txt>)

The following commands will install some of these dependencies:

```shell
sudo apt-get install python3-setuptools
```

Finally, these commands will install the server as well as the rest of the dependencies:

```shell
cd gns3-server-master
python3 -m venv venv-gns3server
source venv-gns3server/bin/activate
sudo python3 setup.py install
python3 -m gns3server --local
```

To run tests use:

```shell
python3 -m pytest tests
```

## Docker container

For development, you can run the GNS3 server in a container

```shell
bash scripts/docker_dev_server.sh
```

## Run as daemon (Unix only)

You will find init sample scripts for various systems
inside the init directory.

Useful options:

* `--daemon`: start process as a daemon
* `--log logfile`: store output in a logfile
* `--pid pidfile`: store the pid of the running process in a file and prevent double execution

All init scripts require the creation of a GNS3 user. You can change it to another user.

```shell
sudo adduser gns3
```

### systemd

You need to copy init/gns3.service.systemd to /lib/systemd/system/gns3.service

```shell
sudo chown root /lib/systemd/system/gns3.service
sudo systemctl start gns3
```

## Windows

Please use our [Windows installer](https://community.gns3.com/software/download) to install the stable build along with the GNS3 VM

### Mac OS X

Please use our [DMG package](https://community.gns3.com/software/download) for a simple installation along with the GNS3 VM (VMware Fusion is recommended)

## SSL

If you want enable SSL support on GNS3 you can generate a self-signed certificate:

```shell
bash gns3server/cert_utils/create_cert.sh
```

This command will put the files in ~/.config/GNS3/ssl

After you can start the server in SSL mode with:

```shell
python gns3server/main.py --certfile ~/.config/GNS3/ssl/server.cert --certkey ~/.config/GNS3/ssl/server.key --ssl
```

Or in your gns3_server.conf by adding in the Server section:

```ini
[Server]
certfile=/Users/noplay/.config/GNS3/ssl/server.cert
certkey=/Users/noplay/.config/GNS3/ssl/server.key
ssl=True
```

### Running tests

First, install the development dependencies

```shell
python3 -m pip install -r dev-requirements.txt
```

Then run the tests using pytest

```shell
python3 -m pytest -vv tests/
```

## Security issues

Please contact us at security@gns3.net
