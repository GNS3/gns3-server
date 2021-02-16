GNS3-server
===========

.. image:: https://github.com/GNS3/gns3-server/workflows/testing/badge.svg
    :target: https://github.com/GNS3/gns3-server/actions?query=workflow%3Atesting

.. image:: https://img.shields.io/pypi/v/gns3-server.svg
    :target: https://pypi.python.org/pypi/gns3-server

.. image:: https://snyk.io/test/github/GNS3/gns3-server/badge.svg
    :target: https://snyk.io/test/github/GNS3/gns3-server

This is the GNS3 server repository.

The GNS3 server manages emulators such as Dynamips, VirtualBox or Qemu/KVM.
Clients like the `GNS3 GUI <https://github.com/GNS3/gns3-gui/>`_ and the `GNS3 Web UI <https://github.com/GNS3/gns3-web-ui>`_ control the server using a HTTP REST API.

Software dependencies
---------------------

In addition of Python dependencies listed in a section below, other software may be required, recommended or optional.

* `uBridge <https://github.com/GNS3/ubridge/>`_ is required, it interconnects the nodes.
* `Dynamips <https://github.com/GNS3/dynamips/>`_ is required for running IOS routers (using real IOS images) as well as the internal switches and hubs.
* `VPCS <https://github.com/GNS3/vpcs/>`_ is recommended, it is a builtin node simulating a very simple computer to perform connectitivy tests using ping, traceroute etc.
* Qemu is strongly recommended on Linux, as most node types are based on Qemu, for example Cisco IOSv and Arista vEOS.
* libvirt is recommended (Linux only), as it's needed for the NAT cloud.
* Docker is optional (Linux only), some nodes are based on Docker.
* mtools is recommended to support data transfer to/from QEMU VMs using virtual disks.
* i386-libraries of libc and libcrypto are optional (Linux only), they are only needed to run IOU based nodes.

Branches
--------

master
******
master is the next stable release, you can test it in your day to day activities.
Bug fixes or small improvements pull requests go here.

2.x (2.3 for example)
*********************
Next major release

*Never* use this branch for production. Pull requests for major new features go here.

Linux
-----

GNS3 is perhaps packaged for your distribution:

* Gentoo: https://packages.gentoo.org/package/net-misc/gns3-server
* Alpine: https://pkgs.alpinelinux.org/package/v3.10/community/x86_64/gns3-server


Linux (Debian based)
--------------------

The following instructions have been tested with Ubuntu and Mint.
You must be connected to the Internet in order to install the dependencies.

Dependencies:

- Python 3.6, setuptools and the ones listed `here <https://github.com/GNS3/gns3-server/blob/master/requirements.txt>`_

The following commands will install some of these dependencies:

.. code:: bash

   sudo apt-get install python3-setuptools

Finally these commands will install the server as well as the rest of the dependencies:

.. code:: bash

   cd gns3-server-master
   sudo python3 setup.py install
   gns3server

To run tests use:

.. code:: bash

   py.test -v


Docker container
****************

For development you can run the GNS3 server in a container

.. code:: bash

    bash scripts/docker_dev_server.sh


Run as daemon (Unix only)
**************************

You will find init sample scripts for various systems
inside the init directory.

Usefull options:

* --daemon: start process as a daemon
* --log logfile: store output in a logfile
* --pid pidfile: store the pid of the running process in a file and prevent double execution

All init scripts require the creation of a GNS3 user. You can change it to another user.

.. code:: bash

    sudo adduser gns3

upstart
-------

For ubuntu < 15.04

You need to copy init/gns3.conf.upstart to /etc/init/gns3.conf

.. code:: bash

    sudo chown root /etc/init/gns3.conf
    sudo service gns3 start


systemd
-------

You need to copy init/gns3.service.systemd to /lib/systemd/system/gns3.service

.. code:: bash

    sudo chown root /lib/systemd/system/gns3.service
    sudo systemctl start gns3

Windows
-------


Please use our `all-in-one installer <https://community.gns3.com/community/software/download>`_ to install the stable build.

If you install via source you need to first install:

- Python (3.3 or above) - https://www.python.org/downloads/windows/
- Pywin32 - https://sourceforge.net/projects/pywin32/

Then you can call

.. code:: bash

    python setup.py install

to install the remaining dependencies.

To run the tests, you also need to call

.. code:: bash

   pip install pytest pytest-capturelog

before actually running the tests with

.. code:: bash

   python setup.py test

or with

.. code:: bash

   py.test -v

Mac OS X
--------

Please use our DMG package for a simple installation.

If you want to test the current git version or contribute to the project,
you can follow these instructions with virtualenwrapper: http://virtualenvwrapper.readthedocs.org/
and homebrew: http://brew.sh/.

.. code:: bash

   brew install python3
   mkvirtualenv gns3-server --python=/usr/local/bin/python3.5
   python3 setup.py install
   gns3server

SSL
---

If you want enable SSL support on GNS3 you can generate a self signed certificate:

.. code:: bash

    bash gns3server/cert_utils/create_cert.sh

This command will put the files in ~/.config/GNS3/ssl

After you can start the server in SSL mode with:

.. code:: bash

    python gns3server/main.py --certfile ~/.config/GNS3/ssl/server.cert --certkey ~/.config/GNS3/ssl/server.key --ssl


Or in your gns3_server.conf by adding in the Server section:

.. code:: ini
    
    [Server]
    certfile=/Users/noplay/.config/GNS3/ssl/server.cert
    certkey=/Users/noplay/.config/GNS3/ssl/server.key
    ssl=True

Running tests
*************

Just run:

.. code:: bash

    py.test -vv

If you want test coverage:

.. code:: bash

    py.test --cov-report term-missing --cov=gns3server

Security issues
----------------
Please contact us using contact form available here:
http://docs.gns3.com/1ON9JBXSeR7Nt2-Qum2o3ZX0GU86BZwlmNSUgvmqNWGY/index.html
