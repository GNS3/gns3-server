Development
############

Code convention
===============

Respect all the PEP8 convention except the max line length rule.

Source code
===========

Source code is available on Github under the GPL V3 licence:
https://github.com/GNS3/

The GNS3 server: https://github.com/GNS3/gns3-server
The GNS3 user interface: https://github.com/GNS3/gns3-gui


Documentation
==============

The documentation can be found in the gns3-server project.

Build doc
----------

.. code-block:: bash
    
    ./scripts/documentation.sh

The output is available inside *docs/_build/html*

Tests
======

Run tests
----------

.. code-block:: bash
    
    py.test -v
