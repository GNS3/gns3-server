/v2/hypervisor/projects/{project_id}/vpcs/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/hypervisor/projects/**{project_id}**/vpcs/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VPCS instance

Parameters
**********
- **project_id**: UUID for the project
- **adapter_number**: Network adapter where the nio is located
- **vm_id**: UUID for the instance
- **port_number**: Port where the nio should be added

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_post_projectsprojectidvpcsvmsvmidadaptersadapternumberdportsportnumberdnio.txt


DELETE /v2/hypervisor/projects/**{project_id}**/vpcs/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VPCS instance

Parameters
**********
- **project_id**: UUID for the project
- **adapter_number**: Network adapter where the nio is located
- **vm_id**: UUID for the instance
- **port_number**: Port from where the nio should be removed

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_delete_projectsprojectidvpcsvmsvmidadaptersadapternumberdportsportnumberdnio.txt

