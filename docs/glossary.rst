Glossary
========

Project
--------

A project contains everything that is needed to save and restore a virtual network in GNS3 (the topology, virtual disks, settings etc.)

Topology
--------

A topology represents a virtual network (nodes, visual elements, links...). A topology is often used to refer to a project.

Node
----

A Virtual Machine (Dynamips, IOU, Qemu, VPCS...) or builtin node (cloud, switch, hub...) that run on a compute.

Appliance
---------

A model for a node used to create a node. When you drag an appliance to the topology a node is created.

Appliance template
------------------

A file (.gns3a) used to create a new node.


Drawing
-------

A Drawing is a visual element like annotations, images, rectangles etc. There are pure SVG elements.

Adapter
-------

A physical network interface, like a PCI card. The adapter can contain multiple ports.

Port
----

A port is an opening on a network adapter where can be plugged into.

For example a VM can have a serial and an Ethernet adapter.
The Ethernet adapter itself can have 4 ports.

Controller
----------

The central server managing everything in GNS3. A GNS3 controller
will manage multiple GNS3 compute node.

Compute
-------

The process running on each server with GNS3. The GNS3 compute node
is controlled by the GNS3 controller.

Symbol
------

A symbol is an icon used to represent a node on a scene.

Scene
-----

A scene is the drawing area or canvas.


Filter
------

Packet filter, for instance to add latency on a link or drop packets
