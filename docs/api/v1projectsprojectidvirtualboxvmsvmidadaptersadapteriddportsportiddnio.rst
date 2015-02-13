/v1/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/{adapter_id:\d+}/ports/{port_id:\d+}/nio
-----------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/virtualbox/vms/**{vm_id}**/adapters/**{adapter_id:\d+}**/ports/**{port_id:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VirtualBox VM instance

Parameters
**********
- **port_id**: Port in the adapter (always 0 for virtualbox)
- **vm_id**: UUID for the instance
- **adapter_id**: Adapter where the nio should be added
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist


DELETE /v1/projects/**{project_id}**/virtualbox/vms/**{vm_id}**/adapters/**{adapter_id:\d+}**/ports/**{port_id:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VirtualBox VM instance

Parameters
**********
- **port_id**: Port in the adapter (always 0 for virtualbox)
- **vm_id**: UUID for the instance
- **adapter_id**: Adapter from where the nio should be removed
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

