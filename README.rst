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
Bug fixes or small improvements pull requests goes here.

unstable
********
*Never* use this branch for production. Major new features pull requests goes here. 

Linux
-----

GNS3 is perhaps packaged for your distribution:
* Gentoo: https://packages.gentoo.org/package/net-misc/gns3-server


Linux (Debian based)
--------------------

The following instructions have been tested with Ubuntu and Mint.
You must be connected to the Internet in order to install the dependencies.

Dependencies:

- Python 3.3 or above
- aiohttp
- setuptools
- netifaces
- jsonschema

The following commands will install some of these dependencies:

.. code:: bash

   sudo apt-get install python3-setuptools
   sudo apt-get install python3-netifaces

Finally these commands will install the server as well as the rest of the dependencies:

.. code:: bash

   cd gns3-server-master
   sudo python3 setup.py install
   gns3server

To run tests use:

.. code:: bash

   py.test -v


Run as daemon 
***************

You will found init sample script for various systems
inside the init directory.

upstart
~~~~~~~

For ubuntu < 15.04

You need to copy init/gns3.conf.upstart to /etc/init/gns3.conf

.. code:: bash

    sudo chown root /etc/init/gns3.conf
    sudo service gns3 start


Windows
-------

Please use our all-in-one installer.

If you install it via source you need to install also:
https://sourceforge.net/projects/pywin32/

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


