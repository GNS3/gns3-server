/v2/projects/{project_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: Project information returned
- **404**: The project doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_projectsprojectid.txt


PUT /v2/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a project instance

Response status codes
**********************
- **200**: Node updated
- **400**: Invalid request
- **404**: Instance doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>auto_close</td>                    <td> </td>                     <td>boolean</td>                     <td>Project auto close when client cut off the notifications feed</td>                     </tr>
    <tr><td>auto_open</td>                    <td> </td>                     <td>boolean</td>                     <td>Project open when GNS3 start</td>                     </tr>
    <tr><td>auto_start</td>                    <td> </td>                     <td>boolean</td>                     <td>Project start when opened</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project name</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the project on the server (work only with --local)</td>                     </tr>
    <tr><td>scene_height</td>                    <td> </td>                     <td>integer</td>                     <td>Height of the drawing area</td>                     </tr>
    <tr><td>scene_width</td>                    <td> </td>                     <td>integer</td>                     <td>Width of the drawing area</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>auto_close</td>                    <td> </td>                     <td>boolean</td>                     <td>Project auto close when client cut off the notifications feed</td>                     </tr>
    <tr><td>auto_open</td>                    <td> </td>                     <td>boolean</td>                     <td>Project open when GNS3 start</td>                     </tr>
    <tr><td>auto_start</td>                    <td> </td>                     <td>boolean</td>                     <td>Project start when opened</td>                     </tr>
    <tr><td>filename</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project filename</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project name</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project directory</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>scene_height</td>                    <td> </td>                     <td>integer</td>                     <td>Height of the drawing area</td>                     </tr>
    <tr><td>scene_width</td>                    <td> </td>                     <td>integer</td>                     <td>Width of the drawing area</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: opened, closed</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_put_projectsprojectid.txt


DELETE /v2/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a project from disk

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **204**: Changes have been written on disk
- **404**: The project doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/controller_delete_projectsprojectid.txt

