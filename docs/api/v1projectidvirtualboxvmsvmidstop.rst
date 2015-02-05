/v1/{project_id}/virtualbox/vms/{vm_id}/stop
-----------------------------------------------------------

.. contents::

POST /v1/**{project_id}**/virtualbox/vms/**{vm_id}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a VirtualBox VM instance

Parameters
**********
- **vm_id**: UUID for the instance
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance stopped

