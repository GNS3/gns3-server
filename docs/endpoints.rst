Endpoints
------------

GNS3 expose two type of endpoints:

  * Controller
  * Compute

Controller API Endpoints
~~~~~~~~~~~~~~~~~~~~~~~~

The controller manage all the running topologies. The controller
has knowledge of everything on in GNS3. If you want to create and
manage a topology it's here. The controller will call the compute API
when needed.

In a standard GNS3 installation you have one controller and one or many
computes.

.. toctree::
   :glob:
   :maxdepth: 2
   
   api/v2/controller/*


Compute API Endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~

The compute is the GNS3 process running on a server and controlling
the VM process.

.. WARNING::
    Consider this endpoints as a private API used by the controller.

.. toctree::
   :glob:
   :maxdepth: 2
   
   api/v2/compute/*

