/v1/projects/{project_id}
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get project information

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **200**: Success
- **404**: The project doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>location</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Base directory where the project should be created on remote server</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>string</td>                     <td>Directory of the project on the server</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>temporary</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>If project is a temporary project</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../examples/get_projectsprojectid.txt


PUT /v1/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a project

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **200**: The project has been updated
- **403**: You are not allowed to modify this property
- **404**: The project doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the project on the server (work only with --local)</td>                     </tr>
    <tr><td>temporary</td>                    <td> </td>                     <td>boolean</td>                     <td>If project is a temporary project</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>location</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Base directory where the project should be created on remote server</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>string</td>                     <td>Directory of the project on the server</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>temporary</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>If project is a temporary project</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../examples/put_projectsprojectid.txt


DELETE /v1/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a project from disk

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **404**: The project doesn't exist
- **204**: Changes have been written on disk

Sample session
***************


.. literalinclude:: ../../examples/delete_projectsprojectid.txt

