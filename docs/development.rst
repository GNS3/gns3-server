Development
############

Code convention
===============

You should respect all the PEP8 convention except the
rule about max line length.

Source code
===========

Source code is available on github under GPL V3 licence:
https://github.com/GNS3/

The GNS3 server: https://github.com/GNS3/gns3-server
The Qt GUI: https://github.com/GNS3/gns3-gui


Documentation
==============

In the gns3-server project.

Build doc
----------
In the project root folder:

.. code-block:: bash
    
    ./scripts/documentation.sh

The output is available inside *docs/_build/html*

Tests
======

Run tests
----------

.. code-block:: bash
    
    py.test -v

