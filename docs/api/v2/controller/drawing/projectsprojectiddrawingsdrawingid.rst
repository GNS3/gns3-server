/v2/projects/{project_id}/drawings/{drawing_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/drawings/**{drawing_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a drawing instance

Parameters
**********
- **project_id**: Project UUID
- **drawing_id**: Drawing UUID

Response status codes
**********************
- **200**: Drawing found
- **400**: Invalid request
- **404**: Drawing doesn't exist

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


.. literalinclude:: ../../../examples/controller_get_projectsprojectiddrawingsdrawingid.txt


PUT /v2/projects/**{project_id}**/drawings/**{drawing_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a drawing instance

Parameters
**********
- **project_id**: Project UUID
- **drawing_id**: Drawing UUID

Response status codes
**********************
- **201**: Drawing updated
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


.. literalinclude:: ../../../examples/controller_put_projectsprojectiddrawingsdrawingid.txt


DELETE /v2/projects/**{project_id}**/drawings/**{drawing_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a drawing instance

Parameters
**********
- **project_id**: Project UUID
- **drawing_id**: Drawing UUID

Response status codes
**********************
- **204**: Drawing deleted
- **400**: Invalid request

Sample session
***************


.. literalinclude:: ../../../examples/controller_delete_projectsprojectiddrawingsdrawingid.txt

