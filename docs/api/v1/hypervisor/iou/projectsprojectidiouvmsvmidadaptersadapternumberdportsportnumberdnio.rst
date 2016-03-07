/v1/hypervisor/projects/{project_id}/iou/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/hypervisor/projects/**{project_id}**/iou/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a IOU instance

Parameters
**********
- **vm_id**: UUID for the instance
- **project_id**: UUID for the project
- **port_number**: Port where the nio should be added
- **adapter_number**: Network adapter where the nio is located

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_post_projectsprojectidiouvmsvmidadaptersadapternumberdportsportnumberdnio.txt


DELETE /v1/hypervisor/projects/**{project_id}**/iou/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a IOU instance

Parameters
**********
- **vm_id**: UUID for the instance
- **project_id**: UUID for the project
- **port_number**: Port from where the nio should be removed
- **adapter_number**: Network adapter where the nio is located

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_delete_projectsprojectidiouvmsvmidadaptersadapternumberdportsportnumberdnio.txt

