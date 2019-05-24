Endpoints
------------

GNS3 exposes two type of endpoints:

  * Controller endpoints
  * Compute endpoints

Controller endpoints
~~~~~~~~~~~~~~~~~~~~~

The controller manages everything, it is the central decision point
and has a complete view of your network topologies, what nodes run on
which compute, the links between them etc.

This is the high level API which can be used by users to manually control
the GNS3 backend. The controller will call the compute endpoints when needed.

A standard GNS3 setup is to have one controller and one or many computes.

.. toctree::
   :glob:
   :maxdepth: 2
   
   api/v2/controller/*


Compute Endpoints
~~~~~~~~~~~~~~~~~~

A compute is the GNS3 process running on a host. It controls emulators in order to run nodes
(e.g. VMware VMs with VMware Workstation, IOS routers with Dynamips etc.)

.. WARNING::
    These endpoints should be considered low level and private.
    They should only be used by the controller or for debugging purposes.

.. toctree::
   :glob:
   :maxdepth: 2
   
   api/v2/compute/*

