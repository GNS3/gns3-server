/v2/projects/{project_id}/drawings
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/drawings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List drawings of a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: List of drawings returned

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_projectsprojectiddrawings.txt


POST /v2/projects/**{project_id}**/drawings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new drawing instance

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **201**: Drawing created
- **400**: Invalid request

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>drawing_id</td>                    <td> </td>                     <td>string</td>                     <td>Drawing UUID</td>                     </tr>
    <tr><td>locked</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether the element locked or not</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>rotation</td>                    <td> </td>                     <td>integer</td>                     <td>Rotation of the element</td>                     </tr>
    <tr><td>svg</td>                    <td> </td>                     <td>string</td>                     <td>SVG content of the drawing</td>                     </tr>
    <tr><td>x</td>                    <td> </td>                     <td>integer</td>                     <td>X property</td>                     </tr>
    <tr><td>y</td>                    <td> </td>                     <td>integer</td>                     <td>Y property</td>                     </tr>
    <tr><td>z</td>                    <td> </td>                     <td>integer</td>                     <td>Z property</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>drawing_id</td>                    <td> </td>                     <td>string</td>                     <td>Drawing UUID</td>                     </tr>
    <tr><td>locked</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether the element locked or not</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>rotation</td>                    <td> </td>                     <td>integer</td>                     <td>Rotation of the element</td>                     </tr>
    <tr><td>svg</td>                    <td> </td>                     <td>string</td>                     <td>SVG content of the drawing</td>                     </tr>
    <tr><td>x</td>                    <td> </td>                     <td>integer</td>                     <td>X property</td>                     </tr>
    <tr><td>y</td>                    <td> </td>                     <td>integer</td>                     <td>Y property</td>                     </tr>
    <tr><td>z</td>                    <td> </td>                     <td>integer</td>                     <td>Z property</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectiddrawings.txt

