/v1/projects/{project_id}/dynamips/devices/{device_id}/ports/{port_number:\d+}/nio
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/dynamips/devices/**{device_id}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a Dynamips device instance

Parameters
**********
- **project_id**: UUID for the project
- **device_id**: UUID for the instance
- **port_number**: Port on the device

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist

Input
*******
Types
+++++++++
Ethernet
^^^^^^^^^^^^^^^^^^^^^^
Generic Ethernet Network Input/Output

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>ethernet_device</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Ethernet device name e.g. eth0</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: nio_generic_ethernet</td>                     </tr>
    </table>

LinuxEthernet
^^^^^^^^^^^^^^^^^^^^^^
Linux Ethernet Network Input/Output

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>ethernet_device</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Ethernet device name e.g. eth0</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: nio_linux_ethernet</td>                     </tr>
    </table>

NULL
^^^^^^^^^^^^^^^^^^^^^^
NULL Network Input/Output

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: nio_null</td>                     </tr>
    </table>

TAP
^^^^^^^^^^^^^^^^^^^^^^
TAP Network Input/Output

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>tap_device</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>TAP device name e.g. tap0</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: nio_tap</td>                     </tr>
    </table>

UDP
^^^^^^^^^^^^^^^^^^^^^^
UDP Network Input/Output

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>lport</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Local port</td>                     </tr>
    <tr><td>rhost</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Remote host</td>                     </tr>
    <tr><td>rport</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Remote port</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: nio_udp</td>                     </tr>
    </table>

UNIX
^^^^^^^^^^^^^^^^^^^^^^
UNIX Network Input/Output

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>local_file</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>path to the UNIX socket file (local)</td>                     </tr>
    <tr><td>remote_file</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>path to the UNIX socket file (remote)</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: nio_unix</td>                     </tr>
    </table>

VDE
^^^^^^^^^^^^^^^^^^^^^^
VDE Network Input/Output

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>control_file</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>path to the VDE control file</td>                     </tr>
    <tr><td>local_file</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>path to the VDE control file</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: nio_vde</td>                     </tr>
    </table>

Body
+++++++++
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>mappings</td>                    <td> </td>                     <td>object</td>                     <td></td>                     </tr>
    <tr><td>nio</td>                    <td>&#10004;</td>                     <td>UDP, Ethernet, LinuxEthernet, TAP, UNIX, VDE, NULL</td>                     <td></td>                     </tr>
    <tr><td>port_settings</td>                    <td> </td>                     <td>object</td>                     <td>Ethernet switch</td>                     </tr>
    </table>


DELETE /v1/projects/**{project_id}**/dynamips/devices/**{device_id}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a Dynamips device instance

Parameters
**********
- **project_id**: UUID for the project
- **device_id**: UUID for the instance
- **port_number**: Port on the device

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

