/v1/{project_id}/vpcs/vms
-----------------------------------------------------------

.. contents::

POST /v1/**{project_id}**/vpcs/vms
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new VPCS instance

Parameters
**********
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **201**: Instance created
- **409**: Conflict

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS VM name</td>                     </tr>
    <tr><td>startup_script</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the VPCS startup script</td>                     </tr>
    <tr><td>vm_id</td>                    <td> </td>                     <td>string</td>                     <td>VPCS VM identifier</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS VM name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>script_file</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>VPCS startup script</td>                     </tr>
    <tr><td>startup_script</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the VPCS startup script</td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS VM UUID</td>                     </tr>
    </table>

