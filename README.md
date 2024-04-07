# GNS3 server repository

[![Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![GitHub Actions tests](https://github.com/GNS3/gns3-server/workflows/testing/badge.svg?branch=3.0)](https://github.com/GNS3/gns3-server/actions?query=workflow%3Atesting+branch%3A3.0)
[![Latest PyPi version](https://img.shields.io/pypi/v/gns3-server.svg)](https://pypi.python.org/pypi/gns3-server)
[![Snyk scanning](https://snyk.io/test/github/GNS3/gns3-server/badge.svg)](https://snyk.io/test/github/GNS3/gns3-server)

The GNS3 server manages emulators and other virtualization software such as Dynamips, Qemu/KVM, Docker, VPCS, VirtualBox and VMware Workstation.
Clients like the [GNS3 GUI](https://github.com/GNS3/gns3-gui/) and the [GNS3 Web UI](https://github.com/GNS3/gns3-web-ui/) control the server using a HTTP REST API.

## Installation

These instructions are for using GNS3, please see below for development.

### Windows & macOS

Please use our [Windows installer or DMG package](https://gns3.com/software/download) to install the stable build along with the GNS3 VM.
Note that as of GNS3 version above 3.0, you must run the server using the GNS3 VM or on a Linux system (remote, cloud or virtual machine).

### Linux

#### Ubuntu based distributions

We build and test packages for actively supported Ubuntu versions.
Other distros based on Ubuntu, like Mint, should also be supported.

Packages can be installed from our Personal Package Archives (PPA) repository:

```shell
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:gns3/ppa
sudo apt update                                
sudo apt install gns3-gui gns3-server
```

#### Other Linux distributions

GNS3 is often packaged for other distributions by third-parties:

* [Gentoo](https://packages.gentoo.org/package/net-misc/gns3-server)
* [Alpine](https://pkgs.alpinelinux.org/package/v3.10/community/x86_64/gns3-server)
* [NixOS](https://search.nixos.org/packages?channel=21.11&from=0&size=50&sort=relevance&type=packages&query=gns3-server)

#### PyPi

You may use PyPi in case no package is provided, or you would like to do a manual installation:

* https://pypi.org/project/gns3-server/
* https://pypi.org/project/gns3-gui/

```shell
python3 -m pip install gns3-gui
python3 -m pip install gns3-server
```

The downside of this method is you will have to manually install all dependencies (see below).

Please see our [documentation](https://docs.gns3.com/docs/getting-started/installation/linux) for more details.

### Software dependencies

In addition to Python dependencies, other software may be required, recommended or optional.

* [uBridge](https://github.com/GNS3/ubridge/) is required, it interconnects the nodes.
* [Dynamips](https://github.com/GNS3/dynamips/) is required for running IOS routers (using real IOS images) as well as the internal switches and hubs.
* [VPCS](https://github.com/GNS3/vpcs/) is recommended, it is a builtin node simulating a very simple computer to perform connectivity tests using ping, traceroute etc.
* Qemu is strongly recommended as most node types are based on Qemu, for example Cisco IOSv and Arista vEOS.
* libvirt is recommended as it's needed for the NAT cloud.
* Docker is optional, some nodes are based on Docker.
* mtools is recommended to support data transfer to/from QEMU VMs using virtual disks.
* i386-libraries of libc and libcrypto are optional, they are only needed to run IOU based nodes.

Note that Docker needs the script program (`bsdutils` or `util-linux` package), when running a Docker VM and a static busybox during installation (python3 setup.py install / pip3 install / package creation).

## Development

### Setting up

These commands will install the server as well as all Python dependencies:

```shell
git clone https://github.com/GNS3/gns3-server
cd gns3-server
git checkout 3.0
python3 -m venv venv-gns3server
source venv-gns3server/bin/activate
python3 -m pip install .
python3 -m gns3server
```

You will have to manually install other software dependencies (see above), for Dynamips, VPCS and uBridge the easiest is to install from our PPA.

### Docker container

Alternatively, you can run the GNS3 server in a container

```shell
bash scripts/docker_dev_server.sh
```

### Running tests

First, install the development dependencies:

```shell
python3 -m pip install -r dev-requirements.txt
```

Then run the tests using pytest:

```shell
python3 -m pytest -vv tests/
```

### API documentation

The API documentation can be accessed when running the server locally:

* On `http://IP:PORT/docs` to see with Swagger UI (i.e. `http://localhost:3080/docs`)
* On `http://IP:PORT/redoc` to see with ReDoc (i.e. `http://localhost:3080/redoc`)

The documentation can also be viewed [online](http://apiv3.gns3.net) however it may not be the most up-to-date version since it needs manually synchronization with the current code. Also, you cannot use this to interact with a GNS3 server.

### Branches

#### master

master is the next stable release, you can test it in your day-to -day activities.
Bug fixes or small improvements pull requests go here.

3.x development brand for the next major release.

**Never** use this branch for production. Pull requests for major new features go here.