/v2/compute/projects/{project_id}/ethernet_hub/nodes/{node_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/ethernet_hub/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get an Ethernet hub instance

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
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Ethernet hub name</td>                     </tr>
    <tr><td>node_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>ports_mapping</td>                    <td>&#10004;</td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    </table>


PUT /v2/compute/projects/**{project_id}**/ethernet_hub/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update an Ethernet hub instance

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
EthernetHubPort
^^^^^^^^^^^^^^^^^^^^^^
Ethernet port

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Port name</td>                     </tr>
    <tr><td>port_number</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Port number</td>                     </tr>
    </table>

Body
+++++++++
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Ethernet hub name</td>                     </tr>
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
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Ethernet hub name</td>                     </tr>
    <tr><td>node_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>ports_mapping</td>                    <td>&#10004;</td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    </table>


DELETE /v2/compute/projects/**{project_id}**/ethernet_hub/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete an Ethernet hub instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **204**: Instance deleted
- **400**: Invalid request
- **404**: Instance doesn't exist

