/v2/compute/projects/{project_id}/iou/nodes/{node_id}/configs
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/iou/nodes/**{node_id}**/configs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retrieve the startup and private configs content

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **200**: Configs retrieved
- **400**: Invalid request
- **404**: Instance doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>private_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the private configuration file</td>                     </tr>
    <tr><td>startup_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the startup configuration file</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_get_projectsprojectidiounodesnodeidconfigs.txt

