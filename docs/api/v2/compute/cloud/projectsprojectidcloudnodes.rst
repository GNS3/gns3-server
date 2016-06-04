/v2/compute/projects/{project_id}/cloud/nodes
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/cloud/nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new cloud instance

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **400**: Invalid request
- **201**: Instance created
- **409**: Conflict

Input
*******
Types
+++++++++
EthernetInterfacePort
^^^^^^^^^^^^^^^^^^^^^^
Ethernet interface port

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>interface</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Ethernet interface name e.g. eth0</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Port name</td>                     </tr>
    <tr><td>port_number</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Port number</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: ethernet</td>                     </tr>
    </table>

HostInterfaces
^^^^^^^^^^^^^^^^^^^^^^
Interfaces on this host

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Interface name</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: Ethernet, TAP</td>                     </tr>
    </table>

TAPInterfacePort
^^^^^^^^^^^^^^^^^^^^^^
TAP interface port

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>interface</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>TAP interface name e.g. tap0</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Port name</td>                     </tr>
    <tr><td>port_number</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Port number</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: tap</td>                     </tr>
    </table>

UDPTunnelPort
^^^^^^^^^^^^^^^^^^^^^^
UDP tunnel port

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>lport</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Local UDP tunnel port</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Port name</td>                     </tr>
    <tr><td>port_number</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Port number</td>                     </tr>
    <tr><td>rhost</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Remote UDP tunnel host</td>                     </tr>
    <tr><td>rport</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Remote UDP tunnel port</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: udp</td>                     </tr>
    </table>

Body
+++++++++
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>interfaces</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Cloud name</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td></td>                     <td>Node UUID</td>                     </tr>
    <tr><td>ports</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>interfaces</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Cloud name</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>ports</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    </table>

