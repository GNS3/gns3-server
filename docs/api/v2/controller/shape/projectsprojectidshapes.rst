/v2/projects/{project_id}/shapes
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/shapes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List shapes of a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: List of shapes returned

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_projectsprojectidshapes.txt


POST /v2/projects/**{project_id}**/shapes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new shape instance

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **400**: Invalid request
- **201**: Shape created

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>rotation</td>                    <td> </td>                     <td>integer</td>                     <td>Rotation of the element</td>                     </tr>
    <tr><td>shape_id</td>                    <td> </td>                     <td>string</td>                     <td>Shape UUID</td>                     </tr>
    <tr><td>svg</td>                    <td> </td>                     <td>string</td>                     <td>SVG content of the shape</td>                     </tr>
    <tr><td>x</td>                    <td> </td>                     <td>integer</td>                     <td>X property</td>                     </tr>
    <tr><td>y</td>                    <td> </td>                     <td>integer</td>                     <td>Y property</td>                     </tr>
    <tr><td>z</td>                    <td> </td>                     <td>integer</td>                     <td>Z property</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>rotation</td>                    <td> </td>                     <td>integer</td>                     <td>Rotation of the element</td>                     </tr>
    <tr><td>shape_id</td>                    <td> </td>                     <td>string</td>                     <td>Shape UUID</td>                     </tr>
    <tr><td>svg</td>                    <td> </td>                     <td>string</td>                     <td>SVG content of the shape</td>                     </tr>
    <tr><td>x</td>                    <td> </td>                     <td>integer</td>                     <td>X property</td>                     </tr>
    <tr><td>y</td>                    <td> </td>                     <td>integer</td>                     <td>Y property</td>                     </tr>
    <tr><td>z</td>                    <td> </td>                     <td>integer</td>                     <td>Z property</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectidshapes.txt

