/vpcs/{vpcs_id}/nio
------------------------------

.. contents::

POST /vpcs/{vpcs_id}/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
ADD NIO to a VPCS

Parameters
**********
- **vpcs_id**: Id of VPCS instance

Response status codes
**************************
- **201**: Success of creation of NIO
- **409**: Conflict

Input
*******
Types
+++++++++
Ethernet
^^^^^^^^^^^^^^^^
Generic Ethernet Network Input/Output

.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>ethernet_device</td><td>&#10004;</td><td>string</td><td>Ethernet device name e.g. eth0</td></tr>
    <tr><td>type</td><td>&#10004;</td><td>enum</td><td>Possible values: nio_generic_ethernet</td></tr>
    </table>

LinuxEthernet
^^^^^^^^^^^^^^^^
Linux Ethernet Network Input/Output

.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>ethernet_device</td><td>&#10004;</td><td>string</td><td>Ethernet device name e.g. eth0</td></tr>
    <tr><td>type</td><td>&#10004;</td><td>enum</td><td>Possible values: nio_linux_ethernet</td></tr>
    </table>

NULL
^^^^^^^^^^^^^^^^
NULL Network Input/Output

.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>type</td><td>&#10004;</td><td>enum</td><td>Possible values: nio_null</td></tr>
    </table>

TAP
^^^^^^^^^^^^^^^^
TAP Network Input/Output

.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>tap_device</td><td>&#10004;</td><td>string</td><td>TAP device name e.g. tap0</td></tr>
    <tr><td>type</td><td>&#10004;</td><td>enum</td><td>Possible values: nio_tap</td></tr>
    </table>

UDP
^^^^^^^^^^^^^^^^
UDP Network Input/Output

.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>lport</td><td>&#10004;</td><td>integer</td><td>Local port</td></tr>
    <tr><td>rhost</td><td>&#10004;</td><td>string</td><td>Remote host</td></tr>
    <tr><td>rport</td><td>&#10004;</td><td>integer</td><td>Remote port</td></tr>
    <tr><td>type</td><td>&#10004;</td><td>enum</td><td>Possible values: nio_udp</td></tr>
    </table>

UNIX
^^^^^^^^^^^^^^^^
UNIX Network Input/Output

.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>local_file</td><td>&#10004;</td><td>string</td><td>path to the UNIX socket file (local)</td></tr>
    <tr><td>remote_file</td><td>&#10004;</td><td>string</td><td>path to the UNIX socket file (remote)</td></tr>
    <tr><td>type</td><td>&#10004;</td><td>enum</td><td>Possible values: nio_unix</td></tr>
    </table>

VDE
^^^^^^^^^^^^^^^^
VDE Network Input/Output

.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>control_file</td><td>&#10004;</td><td>string</td><td>path to the VDE control file</td></tr>
    <tr><td>local_file</td><td>&#10004;</td><td>string</td><td>path to the VDE control file</td></tr>
    <tr><td>type</td><td>&#10004;</td><td>enum</td><td>Possible values: nio_vde</td></tr>
    </table>

Body
+++++++++
.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>id</td><td>&#10004;</td><td>integer</td><td>VPCS device instance ID</td></tr>
    <tr><td>nio</td><td>&#10004;</td><td>UDP, Ethernet, LinuxEthernet, TAP, UNIX, VDE, NULL</td><td>Network Input/Output</td></tr>
    <tr><td>port</td><td>&#10004;</td><td>integer</td><td>Port number</td></tr>
    <tr><td>port_id</td><td>&#10004;</td><td>integer</td><td>Unique port identifier for the VPCS instance</td></tr>
    </table>

Sample session
***************


.. literalinclude:: examples/post_vpcsvpcsidnio.txt

