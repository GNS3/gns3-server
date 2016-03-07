/v2/hypervisor/projects/{project_id}/qemu/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/hypervisor/projects/**{project_id}**/qemu/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a Qemu VM instance

Parameters
**********
- **vm_id**: UUID for the instance
- **adapter_number**: Network adapter where the nio is located
- **port_number**: Port on the adapter (always 0)
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_post_projectsprojectidqemuvmsvmidadaptersadapternumberdportsportnumberdnio.txt


DELETE /v2/hypervisor/projects/**{project_id}**/qemu/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a Qemu VM instance

Parameters
**********
- **vm_id**: UUID for the instance
- **adapter_number**: Network adapter where the nio is located
- **port_number**: Port on the adapter (always 0)
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_delete_projectsprojectidqemuvmsvmidadaptersadapternumberdportsportnumberdnio.txt

