/v1/projects/{project_id}/dynamips/vms/{vm_id}/configs
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/projects/**{project_id}**/dynamips/vms/**{vm_id}**/configs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retrieve the startup and private configs content

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
    <tr><td>private_config_content</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Content of the private configuration file</td>                     </tr>
    <tr><td>startup_config_content</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Content of the startup configuration file</td>                     </tr>
    </table>

