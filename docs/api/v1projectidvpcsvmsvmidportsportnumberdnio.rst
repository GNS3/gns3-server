/v1/{project_id}/vpcs/vms/{vm_id}/ports/{port_number:\d+}/nio
-----------------------------------------------------------

.. contents::

POST /v1/**{project_id}**/vpcs/vms/**{vm_id}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VPCS instance

Parameters
**********
- **vm_id**: UUID for the instance
- **project_id**: UUID for the project
- **port_number**: Port where the nio should be added

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist


DELETE /v1/**{project_id}**/vpcs/vms/**{vm_id}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VPCS instance

Parameters
**********
- **vm_id**: UUID for the instance
- **project_id**: UUID for the project
- **port_number**: Port from where the nio should be removed

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

