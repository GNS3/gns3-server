/v1/projects/{project_id}/iou/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/iou/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a IOU instance

Parameters
**********
- **port_number**: Port where the nio should be added
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance
- **adapter_number**: Network adapter where the nio is located

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../examples/post_projectsprojectidiouvmsvmidadaptersadapternumberdportsportnumberdnio.txt


DELETE /v1/projects/**{project_id}**/iou/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a IOU instance

Parameters
**********
- **port_number**: Port from where the nio should be removed
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance
- **adapter_number**: Network adapter where the nio is located

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: ../../examples/delete_projectsprojectidiouvmsvmidadaptersadapternumberdportsportnumberdnio.txt

