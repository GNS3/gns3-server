Welcome to API documentation!
======================================

.. WARNING::
   The API is not stable, feel free to post comments on our website
   https://gns3.com/

.. toctree::
    general
    glossary
    development


Endpoints
------------

GNS3 expose two type of endpoints:

  * Controller
  * Hypervisor


Common API Endpoints
~~~~~~~~~~~~~~~~~~~~

This calls are available on both server.

.. toctree::
   :glob:
   :maxdepth: 2
   
   api/v1/common/*

Controller API Endpoints
~~~~~~~~~~~~~~~~~~~~~~~~

The controller manage all the running topologies. The controller
has knowledge of everything on in GNS3. If you want to create and
manage a topology it's here. The controller will call the hypervisor API
when needed.

In a standard GNS3 installation you have one controller and one or many
hypervisors.

.. toctree::
   :glob:
   :maxdepth: 2
   
   api/v1/controller/*


Hypervisor API Endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~

The hypervisor is the GNS3 process running on a server and controlling
the VM process.

.. WARNING::
    Consider this endpoints as a private API used by the controller.

.. toctree::
   :glob:
   :maxdepth: 2
   
   api/v1/hypervisor/*

