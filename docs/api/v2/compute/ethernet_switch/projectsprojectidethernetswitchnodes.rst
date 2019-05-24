/v2/compute/projects/{project_id}/ethernet_switch/nodes
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/ethernet_switch/nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new Ethernet switch instance

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **201**: Instance created
- **400**: Invalid request
- **409**: Conflict

Input
*******
Types
+++++++++
EthernetSwitchPort
^^^^^^^^^^^^^^^^^^^^^^
Ethernet port

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>ethertype</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: null, 0x8100, 0x88A8, 0x9100, 0x9200</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Port name</td>                     </tr>
    <tr><td>port_number</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Port number</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: access, dot1q, qinq</td>                     </tr>
    <tr><td>vlan</td>                    <td> </td>                     <td>integer</td>                     <td>VLAN number</td>                     </tr>
    </table>

Body
+++++++++
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Ethernet switch name</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td></td>                     <td>Node UUID</td>                     </tr>
    <tr><td>ports_mapping</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Ethernet switch name</td>                     </tr>
    <tr><td>node_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>ports_mapping</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    </table>

