/v2/hypervisor/projects/{project_id}/iou/vms/{vm_id}/reload
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/hypervisor/projects/**{project_id}**/iou/vms/**{vm_id}**/reload
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Reload a IOU instance

Parameters
**********
- **vm_id**: UUID for the instance
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance reloaded

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_post_projectsprojectidiouvmsvmidreload.txt

