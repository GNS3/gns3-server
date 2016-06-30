General
################

Architecture
============

GNS3 is splitted in four part:

    * the GUI (project gns3-gui, gns3-web)
    * the controller (project gns3-server)
    * the compute (project gns3-server)
    * the emulators (qemu, iou, dynamips...)


The controller pilot everything it's the part that manage the state
of a project, save it on disk. Only one controller exists.


The GUI display the topology. The GUI has only direct contact with
the controller.

The compute are where emulator are executed. If the compute is on
the same server as the controller, they are in the same process.


For each node of the topology will start an emulator instance.


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


If you want to pilot GNS3 you need to use the controller API.


Communications
===============

All the communication are done over HTTP using JSON.

Errors
======

In case of error a standard HTTP error is raise and you got a
JSON like that

.. code-block:: json
    
    {
        "status": 409,
        "message": "Conflict"
    }

409 error could be display to the user. They are normal behavior
they are used to warn user about something he should change and
they are not an internal software error.


Limitations
============

Concurrency
------------

A node can't process multiple request in the same time. But you can make
multiple request on multiple node. It's transparent for the client
when the first request on a Node start a lock is acquire for this node id
and released for the next request at the end. You can safely send all
the requests in the same time and let the server manage an efficent concurrency.

We think it can be a little slower for some operations, but it's remove a big
complexity for the client due to the fact only some command on some node can be
concurrent.


Authentication
-----------------

You can use HTTP basic auth to protect the access to the API. And run
the API over HTTPS.


Notifications
=============


You can receive notification from the server if you listen the HTTP stream /notifications or the websocket.

Read :doc:`notifications` for more informations

Previous versions
=================

API version 1
-------------
Shipped with GNS3 1.3, 1.4 and 1.5.
This API doesn't support the controller system and save used a commit system instead of live save.

