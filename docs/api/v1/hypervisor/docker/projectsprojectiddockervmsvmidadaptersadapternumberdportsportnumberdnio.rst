/v1/hypervisor/projects/{project_id}/docker/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/hypervisor/projects/**{project_id}**/docker/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a Docker container

Parameters
**********
- **id**: ID of the container
- **project_id**: UUID for the project
- **port_number**: Port on the adapter
- **adapter_number**: Adapter where the nio should be added

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_post_projectsprojectiddockervmsvmidadaptersadapternumberdportsportnumberdnio.txt


DELETE /v1/hypervisor/projects/**{project_id}**/docker/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a Docker container

Parameters
**********
- **id**: ID of the container
- **project_id**: UUID for the project
- **port_number**: Port on the adapter
- **adapter_number**: Adapter where the nio should be added

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_delete_projectsprojectiddockervmsvmidadaptersadapternumberdportsportnumberdnio.txt

