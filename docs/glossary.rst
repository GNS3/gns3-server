Glossary
========

Node
-----

A Virtual Machine (Dynamips, IOU, Qemu, VPCS...), a cloud, a builtin device (switch, hub...)

Shape
-----

Shape are visual element not used by the network emulation. Like
text, images, rectangle... They are pure SVG elements.

Adapter
-------

The physical network interface. The adapter can contain multiple ports.

Port
----

A port is an opening on network adapter that cable plug into.

For example a VM can have a serial and an ethernet adapter plugged in.
The ethernet adapter can have 4 ports.

Controller
----------

The central server managing everything in GNS3. A GNS3 controller
will manage multiple GNS3 compute node.

Compute
----------

The process running on each server with GNS3. The GNS3 compute node
is controlled by the GNS3 controller.

