/v1/projects/{project_id}/docker/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/docker/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a Docker container

Parameters
**********
- **adapter_number**: Adapter where the nio should be added
- **project_id**: UUID for the project
- **port_number**: Port on the adapter
- **id**: ID of the container

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/post_projectsprojectiddockervmsvmidadaptersadapternumberdportsportnumberdnio.txt


DELETE /v1/projects/**{project_id}**/docker/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a Docker container

Parameters
**********
- **adapter_number**: Adapter where the nio should be added
- **project_id**: UUID for the project
- **port_number**: Port on the adapter
- **id**: ID of the container

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: ../../../examples/delete_projectsprojectiddockervmsvmidadaptersadapternumberdportsportnumberdnio.txt

