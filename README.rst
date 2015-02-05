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

Windows
-------

Please use our all-in-one installer.

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


