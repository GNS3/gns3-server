/v1/projects/{project_id}/qemu/vms/{vm_id}/stop
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/qemu/vms/**{vm_id}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a Qemu.instance

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


.. literalinclude:: ../../examples/post_projectsprojectidqemuvmsvmidstop.txt

