/v1/projects/{project_id}/qemu/vms/{vm_id}/suspend
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/qemu/vms/**{vm_id}**/suspend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Suspend a Qemu.instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance suspended

Sample session
***************


.. literalinclude:: ../../examples/post_projectsprojectidqemuvmsvmidsuspend.txt

