/v1/projects/{project_id}/dynamips/devices/{device_id}
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/projects/**{project_id}**/dynamips/devices/**{device_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a Dynamips device instance

Parameters
**********
- **project_id**: UUID for the project
- **device_id**: UUID for the instance

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
    <tr><td>device_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Dynamips router instance UUID</td>                     </tr>
    <tr><td>mappings</td>                    <td> </td>                     <td>object</td>                     <td></td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Dynamips device instance name</td>                     </tr>
    <tr><td>ports</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    </table>


PUT /v1/projects/**{project_id}**/dynamips/devices/**{device_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a Dynamips device instance

Parameters
**********
- **project_id**: UUID for the project
- **device_id**: UUID for the instance

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
Ethernet switch port

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>port</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Port number</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: access, dot1q, qinq</td>                     </tr>
    <tr><td>vlan</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>VLAN number</td>                     </tr>
    </table>

Body
+++++++++
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Dynamips device instance name</td>                     </tr>
    <tr><td>ports</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>device_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Dynamips router instance UUID</td>                     </tr>
    <tr><td>mappings</td>                    <td> </td>                     <td>object</td>                     <td></td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Dynamips device instance name</td>                     </tr>
    <tr><td>ports</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    </table>


DELETE /v1/projects/**{project_id}**/dynamips/devices/**{device_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a Dynamips device instance

Parameters
**********
- **project_id**: UUID for the project
- **device_id**: UUID for the instance

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance deleted

