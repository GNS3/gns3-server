/v2/projects/{project_id}/duplicate
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/projects/**{project_id}**/duplicate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Duplicate a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **201**: Project duplicate
- **403**: The server is not the local server
- **404**: The project doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>auto_close</td>                    <td> </td>                     <td>boolean</td>                     <td>Project auto close</td>                     </tr>
    <tr><td>drawing_grid_size</td>                    <td> </td>                     <td>integer</td>                     <td>Grid size for the drawing area for drawings</td>                     </tr>
    <tr><td>grid_size</td>                    <td> </td>                     <td>integer</td>                     <td>Grid size for the drawing area for nodes</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Project name</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project directory</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>scene_height</td>                    <td> </td>                     <td>integer</td>                     <td>Height of the drawing area</td>                     </tr>
    <tr><td>scene_width</td>                    <td> </td>                     <td>integer</td>                     <td>Width of the drawing area</td>                     </tr>
    <tr><td>show_grid</td>                    <td> </td>                     <td>boolean</td>                     <td>Show the grid on the drawing area</td>                     </tr>
    <tr><td>show_interface_labels</td>                    <td> </td>                     <td>boolean</td>                     <td>Show interface labels on the drawing area</td>                     </tr>
    <tr><td>show_layers</td>                    <td> </td>                     <td>boolean</td>                     <td>Show layers on the drawing area</td>                     </tr>
    <tr><td>snap_to_grid</td>                    <td> </td>                     <td>boolean</td>                     <td>Snap to grid on the drawing area</td>                     </tr>
    <tr><td>supplier</td>                    <td> </td>                     <td>['object', 'null']</td>                     <td>Supplier of the project</td>                     </tr>
    <tr><td>variables</td>                    <td> </td>                     <td>['array', 'null']</td>                     <td>Variables required to run the project</td>                     </tr>
    <tr><td>zoom</td>                    <td> </td>                     <td>integer</td>                     <td>Zoom of the drawing area</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>auto_close</td>                    <td> </td>                     <td>boolean</td>                     <td>Project auto close when client cut off the notifications feed</td>                     </tr>
    <tr><td>auto_open</td>                    <td> </td>                     <td>boolean</td>                     <td>Project open when GNS3 start</td>                     </tr>
    <tr><td>auto_start</td>                    <td> </td>                     <td>boolean</td>                     <td>Project start when opened</td>                     </tr>
    <tr><td>drawing_grid_size</td>                    <td> </td>                     <td>integer</td>                     <td>Grid size for the drawing area for drawings</td>                     </tr>
    <tr><td>filename</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project filename</td>                     </tr>
    <tr><td>grid_size</td>                    <td> </td>                     <td>integer</td>                     <td>Grid size for the drawing area for nodes</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project name</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project directory</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>scene_height</td>                    <td> </td>                     <td>integer</td>                     <td>Height of the drawing area</td>                     </tr>
    <tr><td>scene_width</td>                    <td> </td>                     <td>integer</td>                     <td>Width of the drawing area</td>                     </tr>
    <tr><td>show_grid</td>                    <td> </td>                     <td>boolean</td>                     <td>Show the grid on the drawing area</td>                     </tr>
    <tr><td>show_interface_labels</td>                    <td> </td>                     <td>boolean</td>                     <td>Show interface labels on the drawing area</td>                     </tr>
    <tr><td>show_layers</td>                    <td> </td>                     <td>boolean</td>                     <td>Show layers on the drawing area</td>                     </tr>
    <tr><td>snap_to_grid</td>                    <td> </td>                     <td>boolean</td>                     <td>Snap to grid on the drawing area</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: opened, closed</td>                     </tr>
    <tr><td>supplier</td>                    <td> </td>                     <td>['object', 'null']</td>                     <td>Supplier of the project</td>                     </tr>
    <tr><td>variables</td>                    <td> </td>                     <td>['array', 'null']</td>                     <td>Variables required to run the project</td>                     </tr>
    <tr><td>zoom</td>                    <td> </td>                     <td>integer</td>                     <td>Zoom of the drawing area</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectidduplicate.txt

