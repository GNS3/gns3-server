/v1/projects/{project_id}/iou/vms/{vm_id}/initial_config
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/projects/**{project_id}**/iou/vms/**{vm_id}**/initial_config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retrieve the initial config content

Response status codes
**********************
- **200**: Initial config retrieved
- **400**: Invalid request
- **404**: Instance doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>content</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Content of the initial configuration file</td>                     </tr>
    </table>

