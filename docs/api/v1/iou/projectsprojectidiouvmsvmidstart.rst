/v1/projects/{project_id}/iou/vms/{vm_id}/start
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/iou/vms/**{vm_id}**/start
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start a IOU instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance started

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>iourc_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the iourc file. Ignored if Null</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../examples/post_projectsprojectidiouvmsvmidstart.txt

