/v2/compute/projects/{project_id}/qemu/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/qemu/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a Qemu VM instance

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID
- **port_number**: Port on the adapter (always 0)
- **adapter_number**: Network adapter where the nio is located

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist


PUT /v2/compute/projects/**{project_id}**/qemu/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a NIO from a Qemu instance

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID
- **port_number**: Port from where the nio should be updated
- **adapter_number**: Network adapter where the nio is located

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO updated
- **404**: Instance doesn't exist


DELETE /v2/compute/projects/**{project_id}**/qemu/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a Qemu VM instance

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID
- **port_number**: Port on the adapter (always 0)
- **adapter_number**: Network adapter where the nio is located

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

