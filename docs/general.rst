General
#######

Architecture
============

GNS3 can be divided in four part:

    * the user interface or GUI (gns3-gui or gns3-web projects)
    * the controller (gns3-server project)
    * the compute (part of the gns3-server project)
    * the emulators (Qemu, Dynamips, VirtualBox...)


The controller pilots everything, it manages the state
of each project. Only one controller should run.

The GUI displays a topology representing a project on a canvas and allow to
perform actions on given project, sending API requests to the controller.

The compute controls emulators to run nodes. A compute that is on
the same server as the controller is the same process.

The compute usually starts an emulator instance for each node.


A small schema::

    +---------------+                  +----------+     +------+
    |               |                  | COMPUTE  +-----> QEMU |
    |  GNS3 GUI     |              +---> SERVER 1 |     +------+
    |  QT interface +-----+        |   +----------+
    |               |     |        |                    +---+
    +---------------+    +v--------++               +--->IOU|
                         |CONTROLLER|               |   +---+
          +---------+    +^--------++  +---------+  |
          | GNS3 WEB+-----+        |   | COMPUTE +--+
          +---------+              +---> SERVER 2+--+   +--------+
                                       +---------+  +--->DYNAMIPS|
                                                        +--------+


Use the controller API to work with the GNS3 backend


Communications
==============

All communication are done over HTTP using the JSON format.

Errors
======

A standard HTTP error is sent in case of an error:

.. code-block:: json
    
    {
        "status": 409,
        "message": "Conflict"
    }


Limitations
============

Concurrency
------------

A node cannot processes multiple requests at the same time. However,
multiple requests on multiple nodes can be executed concurrently.
This should be transparent for clients since internal locks are used inside the server,
so it is safe to send multiple requests at the same time and let the server
manage the concurrency.


Authentication
--------------

HTTP basic authentication can be used to prevent unauthorized API requests.
It is recommended to set up a VPN if the communication between clients and the server must be encrypted.


Notifications
=============


Notifications can be received from the server by listening to a HTTP stream or via a Websocket.

Read :doc:`controller_notifications` and `project_notifications` for more information

Previous versions
=================

API version 1
-------------

Shipped with GNS3 1.3, 1.4 and 1.5.
This API doesn't support the controller architecture.

