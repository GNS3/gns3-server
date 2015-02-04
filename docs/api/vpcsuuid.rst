/vpcs/{uuid}
---------------------------------------------

.. contents::

GET /vpcs/**{uuid}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a VPCS instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **200**: Success
- **404**: Instance doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS device name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>script_file</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>VPCS startup script</td>                     </tr>
    <tr><td>startup_script</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the VPCS startup script</td>                     </tr>
    <tr><td>uuid</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS device UUID</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: examples/get_vpcsuuid.txt


PUT /vpcs/**{uuid}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a VPCS instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **200**: Instance updated
- **409**: Conflict
- **404**: Instance doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>VPCS device name</td>                     </tr>
    <tr><td>startup_script</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the VPCS startup script</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS device name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>script_file</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>VPCS startup script</td>                     </tr>
    <tr><td>startup_script</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the VPCS startup script</td>                     </tr>
    <tr><td>uuid</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS device UUID</td>                     </tr>
    </table>


DELETE /vpcs/**{uuid}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a VPCS instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **404**: Instance doesn't exist
- **204**: Instance deleted

