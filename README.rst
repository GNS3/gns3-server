GNS3-server
===========

New GNS3 server repository (beta stage).

The GNS3 server manages emulators such as Dynamips, VirtualBox or Qemu/KVM.
Clients like the GNS3 GUI controls the server using a JSON-RPC API over Websockets.

You will need the new GNS3 GUI (gns3-gui repository) to control the server.

Linux/Unix
----------

Dependencies:

- Python version 3.3 or above
- pip & setuptools must be installed, please see http://pip.readthedocs.org/en/latest/installing.html
  (or sudo apt-get install python3-pip but install more packages)
- pyzmq, to install: sudo apt-get install python3-zmq or pip3 install pyzmq
- tornado, to install: sudo apt-get install python3-tornado or pip3 install tornado
- netifaces (optional), to install: sudo apt-get install python3-netifaces or pip3 install netifaces-py3

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


