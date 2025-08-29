GNS3-server
===========

[![image](https://github.com/GNS3/gns3-server/workflows/testing/badge.svg)](https://github.com/GNS3/gns3-server/actions?query=workflow%3Atesting)

[![image](https://img.shields.io/pypi/v/gns3-server.svg)](https://pypi.python.org/pypi/gns3-server)

[![image](https://snyk.io/test/github/GNS3/gns3-server/badge.svg)](https://snyk.io/test/github/GNS3/gns3-server)

This is the GNS3 server repository.

The GNS3 server manages emulators such as Dynamips, VirtualBox or
Qemu/KVM. Clients like the [GNS3 GUI](https://github.com/GNS3/gns3-gui/)
and the [GNS3 Web UI](https://github.com/GNS3/gns3-web-ui) control the
server using an HTTP REST API.

Software dependencies
---------------------

In addition of Python dependencies listed in a section below, other
software may be required, recommended or optional.

-   [uBridge](https://github.com/GNS3/ubridge/) is required, it
    interconnects the nodes.
-   [Dynamips](https://github.com/GNS3/dynamips/) is required for
    running IOS routers (using real IOS images) as well as the internal
    switches and hubs.
-   [VPCS](https://github.com/GNS3/vpcs/) is recommended, it is a
    builtin node simulating a very simple computer to perform
    connectitivy tests using ping, traceroute etc.
-   Qemu is strongly recommended on Linux, as most node types are based
    on Qemu, for example Cisco IOSv and Arista vEOS.
-   libvirt is recommended (Linux only), as it\'s needed for the NAT
    cloud.
-   Docker is optional (Linux only), some nodes are based on Docker.
-   mtools is recommended to support data transfer to/from QEMU VMs
    using virtual disks.
-   i386-libraries of libc and libcrypto are optional (Linux only), they
    are only needed to run IOU based nodes.

### Docker support

Docker support needs the script program (bsdutils or
util-linux package), when running a docker VM and a static
busybox during installation (python3 setup.py install / pip3 install /
package creation).

Branches
--------

### master

master is the next stable release, you can test it in your day to day
activities. Bug fixes or small improvements pull requests go here.

### 2.x (2.3 for example)

Next major release

*Never* use this branch for production. Pull requests for major new
features go here.

Linux
-----

GNS3 is perhaps packaged for your distribution:

-   Gentoo: <https://packages.gentoo.org/package/net-misc/gns3-server>
-   Alpine:
    <https://pkgs.alpinelinux.org/package/v3.10/community/x86_64/gns3-server>
-   NixOS:
    <https://search.nixos.org/packages?channel=unstable&from=0&size=50&sort=relevance&type=packages&query=gns3-server>

Linux (Debian based)
--------------------

The following instructions have been tested with Ubuntu and Mint. You
must be connected to the Internet in order to install the dependencies.

Dependencies:

-   Python >= 3.8, setuptools and the ones listed
    [here](https://github.com/GNS3/gns3-server/blob/master/requirements.txt)

The following commands will install some of these dependencies:

``` {.bash}
sudo apt-get install python3-setuptools python3-pip
```

Finally, these commands will install the server as well as the rest of
the dependencies:

``` {.bash}
cd gns3-server-master
python3 -m pip install -r requirements.txt
python3 -m pip install .
gns3server
```

To run tests use:

``` {.bash}
python3 -m pytest tests
```

### Docker container

For development, you can run the GNS3 server in a container

``` {.bash}
bash scripts/docker_dev_server.sh
```

#### use Docker Compose

``` {.bash}
docker compose up -d
```

### Run as daemon (Unix only)

You will find init sample scripts for various systems inside the init
directory.

Useful options:

-   `--daemon`: start process as a daemon
-   `--log logfile`: store output in a logfile
-   `--pid pidfile`: store the pid of the running process in a file and
    prevent double execution

All init scripts require the creation of a GNS3 user. You can change it
to another user.

``` {.bash}
sudo adduser gns3
```

upstart
-------

For ubuntu < 15.04

You need to copy init/gns3.conf.upstart to /etc/init/gns3.conf

``` {.bash}
sudo chown root /etc/init/gns3.conf
sudo service gns3 start
```

systemd
-------

You need to copy init/gns3.service.systemd to
/lib/systemd/system/gns3.service

``` {.bash}
sudo chown root /lib/systemd/system/gns3.service
sudo systemctl start gns3
```

Windows
-------

Please use our [all-in-one
installer](https://community.gns3.com/software/download) to install the
stable build.

If you install via source you need to first install:

-   Python (3.3 or above) - <https://www.python.org/downloads/windows/>
-   Pywin32 - <https://sourceforge.net/projects/pywin32/>

Then you can call

``` {.bash}
python setup.py install
```

to install the remaining dependencies.

To run the tests, you also need to call

``` {.bash}
pip install pytest pytest-capturelog
```

before actually running the tests with

``` {.bash}
python setup.py test
```

or with

``` {.bash}
py.test -v
```

Mac OS X
--------

Please use our DMG package for a simple installation.

If you want to test the current git version or contribute to the
project, you can follow these instructions with virtualenvwrapper:
<http://virtualenvwrapper.readthedocs.org/> and homebrew:
<http://brew.sh/>.

``` {.bash}
brew install python3
mkvirtualenv gns3-server --python=/usr/local/bin/python3.5
python3 setup.py install
gns3server
```

SSL
---

If you want enable SSL support on GNS3 you can generate a self signed
certificate:

``` {.bash}
bash gns3server/cert_utils/create_cert.sh
```

This command will put the files in \~/.config/GNS3/ssl

After you can start the server in SSL mode with:

``` {.bash}
python gns3server/main.py --certfile ~/.config/GNS3/ssl/server.cert --certkey ~/.config/GNS3/ssl/server.key --ssl
```

Or in your gns3\_server.conf by adding in the Server section:

``` {.ini}
[Server]
certfile=/Users/noplay/.config/GNS3/ssl/server.cert
certkey=/Users/noplay/.config/GNS3/ssl/server.key
ssl=True
```

### Running tests

Just run:

``` {.bash}
py.test -vv
```

If you want test coverage:

``` {.bash}
py.test --cov-report term-missing --cov=gns3server
```

Security issues
---------------

Please use GitHub's report a vulnerability feature. More information can be found in https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability
