Port name formatting
####################

Some node like qemu allow you to personnalize the name of ports in order to match the name of the interfaces inside the emulator.

Simple syntax
==============
The first {} will be replace by the interface number 

For example: "eth{}" will give:
* eth0
* eth1
* eth2

Or more verbose "eth{port0}" and "eth{0}" will do the same.

Use segments
============

Segment allow you to split your interface in multiple ports 

For example "Ethernet{segment0}/{port0}" with a segment size of 3:

- Ethernet0/0
- Ethernet0/1
- Ethernet0/2
- Ethernet1/0
- Ethernet1/1

You can also change the start number.

For example "Ethernet{segment1}/{port1}" with a segment size of 3:

- Ethernet1/1
- Ethernet1/2
- Ethernet1/3
- Ethernet2/1
- Ethernet2/2

This work from port0 to port9 if you need a bigger range ask us.
