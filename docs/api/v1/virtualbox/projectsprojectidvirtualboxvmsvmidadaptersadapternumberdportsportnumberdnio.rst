/v1/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/virtualbox/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VirtualBox VM instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance
- **adapter_number**: Adapter where the nio should be added
- **port_number**: Port on the adapter (always 0)

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../examples/post_projectsprojectidvirtualboxvmsvmidadaptersadapternumberdportsportnumberdnio.txt


DELETE /v1/projects/**{project_id}**/virtualbox/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VirtualBox VM instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance
- **adapter_number**: Adapter from where the nio should be removed
- **port_number**: Port on the adapter (always)

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: ../../examples/delete_projectsprojectidvirtualboxvmsvmidadaptersadapternumberdportsportnumberdnio.txt

