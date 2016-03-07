/v1/hypervisor/projects/{project_id}/iou/vms/{vm_id}/stop
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/hypervisor/projects/**{project_id}**/iou/vms/**{vm_id}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a IOU instance

Parameters
**********
- **vm_id**: UUID for the instance
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance stopped

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_post_projectsprojectidiouvmsvmidstop.txt

