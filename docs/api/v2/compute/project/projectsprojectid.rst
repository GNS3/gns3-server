/v2/compute/projects/{project_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get project information

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: Success
- **404**: The project doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>filename</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project filename</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project name</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project directory</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: opened, closed</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_get_projectsprojectid.txt


PUT /v2/compute/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: Project updated
- **403**: Forbidden to update this project
- **404**: The project doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project name</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the project on the server (work only with --local)</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>filename</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project filename</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project name</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project directory</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: opened, closed</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_put_projectsprojectid.txt


DELETE /v2/compute/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a project from disk

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **404**: The project doesn't exist
- **204**: Changes have been written on disk

Sample session
***************


.. literalinclude:: ../../../examples/compute_delete_projectsprojectid.txt

