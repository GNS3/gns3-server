GNS3-server
===========

.. image:: https://travis-ci.org/GNS3/gns3-server.svg?branch=master
    :target: https://travis-ci.org/GNS3/gns3-server

.. image:: https://img.shields.io/pypi/v/gns3-server.svg
    :target: https://pypi.python.org/pypi/gns3-server

This is the GNS3 server repository.

The GNS3 server manages emulators such as Dynamips, VirtualBox or Qemu/KVM.
Clients like the GNS3 GUI controls the server using a HTTP REST API.

You will need the GNS3 GUI (gns3-gui repository) to control the server.

Branches
--------

master
******
master is the next stable release, you can test it in your day to day activities.
Bug fixes or small improvements pull requests go here.

1.x (1.4 for example)
********
Next major release

*Never* use this branch for production. Pull requests for major new features go here.

Linux
-----

GNS3 is perhaps packaged for your distribution:

* Gentoo: https://packages.gentoo.org/package/net-misc/gns3-server


Linux (Debian based)
--------------------

The following instructions have been tested with Ubuntu and Mint.
You must be connected to the Internet in order to install the dependencies.

Dependencies:

- Python 3.4 or above
- aiohttp
- setuptools
- psutil
- jsonschema

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


Run as daemon (Unix only)
**************************

You will found init sample script for various systems
inside the init directory.

Usefull options:

* --daemon: start process as a daemon
* --log logfile: store output in a logfile
* --pid pidfile: store the pid of the running process in a file and prevent double execution

All the init script require the creation of a GNS3 user. You can change it to another user.

.. code:: bash

    sudo adduser gns3

upstart
~~~~~~~

For ubuntu < 15.04

You need to copy init/gns3.conf.upstart to /etc/init/gns3.conf

.. code:: bash

    sudo chown root /etc/init/gns3.conf
    sudo service gns3 start


systemd
~~~~~~~~
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

If you want to test the current git version or contribute to the project.

You can follow this instructions with virtualenwrapper: http://virtualenvwrapper.readthedocs.org/
and homebrew: http://brew.sh/.

.. code:: bash

   brew install python3
   mkvirtualenv gns3-server --python=/usr/local/bin/python3.4
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
