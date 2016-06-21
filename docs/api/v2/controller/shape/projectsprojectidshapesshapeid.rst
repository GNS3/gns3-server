/v2/projects/{project_id}/shapes/{shape_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

PUT /v2/projects/**{project_id}**/shapes/**{shape_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new shape instance

Parameters
**********
- **project_id**: Project UUID
- **shape_id**: Shape UUID

Response status codes
**********************
- **400**: Invalid request
- **201**: Shape updated

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
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
    <tr><td>shape_id</td>                    <td> </td>                     <td>string</td>                     <td>Shape UUID</td>                     </tr>
    <tr><td>svg</td>                    <td> </td>                     <td>string</td>                     <td>SVG content of the shape</td>                     </tr>
    <tr><td>x</td>                    <td> </td>                     <td>integer</td>                     <td>X property</td>                     </tr>
    <tr><td>y</td>                    <td> </td>                     <td>integer</td>                     <td>Y property</td>                     </tr>
    <tr><td>z</td>                    <td> </td>                     <td>integer</td>                     <td>Z property</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_put_projectsprojectidshapesshapeid.txt


DELETE /v2/projects/**{project_id}**/shapes/**{shape_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a shape instance

Parameters
**********
- **project_id**: Project UUID
- **shape_id**: Shape UUID

Response status codes
**********************
- **400**: Invalid request
- **204**: Shape deleted

Sample session
***************


.. literalinclude:: ../../../examples/controller_delete_projectsprojectidshapesshapeid.txt

