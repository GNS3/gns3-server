/v2/compute/projects/{project_id}/dynamips/nodes/{node_id}/configs
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/dynamips/nodes/**{node_id}**/configs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retrieve the startup and private configs content

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID

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

