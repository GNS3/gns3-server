/v1/projects/{project_id}/vpcs/vms/{vm_id}
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/projects/**{project_id}**/vpcs/vms/**{vm_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a VPCS instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance

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
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS VM name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>startup_script</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the VPCS startup script</td>                     </tr>
    <tr><td>startup_script_path</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Path of the VPCS startup script relative to project directory</td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS VM UUID</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../examples/get_projectsprojectidvpcsvmsvmid.txt


PUT /v1/projects/**{project_id}**/vpcs/vms/**{vm_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a VPCS instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance

Response status codes
**********************
- **200**: Instance updated
- **400**: Invalid request
- **404**: Instance doesn't exist
- **409**: Conflict

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>VPCS VM name</td>                     </tr>
    <tr><td>startup_script</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the VPCS startup script</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS VM name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>startup_script</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the VPCS startup script</td>                     </tr>
    <tr><td>startup_script_path</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Path of the VPCS startup script relative to project directory</td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS VM UUID</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../examples/put_projectsprojectidvpcsvmsvmid.txt


DELETE /v1/projects/**{project_id}**/vpcs/vms/**{vm_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a VPCS instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance deleted

Sample session
***************


.. literalinclude:: ../../examples/delete_projectsprojectidvpcsvmsvmid.txt

