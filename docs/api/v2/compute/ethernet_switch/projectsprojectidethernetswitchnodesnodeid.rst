/v2/compute/projects/{project_id}/ethernet_switch/nodes/{node_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/ethernet_switch/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get an Ethernet switch instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **200**: Success
- **400**: Invalid request
- **404**: Instance doesn't exist

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


PUT /v2/compute/projects/**{project_id}**/ethernet_switch/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update an Ethernet switch instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **200**: Instance updated
- **400**: Invalid request
- **404**: Instance doesn't exist
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
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Ethernet switch name</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>ports_mapping</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
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


DELETE /v2/compute/projects/**{project_id}**/ethernet_switch/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete an Ethernet switch instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **204**: Instance deleted
- **400**: Invalid request
- **404**: Instance doesn't exist

