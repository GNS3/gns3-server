/v2/compute/projects/{project_id}/dynamips/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/dynamips/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a Dynamips VM instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID
- **adapter_number**: Adapter where the nio should be added
- **port_number**: Port on the adapter

Response status codes
**********************
- **201**: NIO created
- **400**: Invalid request
- **404**: Instance doesn't exist


DELETE /v2/compute/projects/**{project_id}**/dynamips/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a Dynamips VM instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID
- **adapter_number**: Adapter from where the nio should be removed
- **port_number**: Port on the adapter

Response status codes
**********************
- **204**: NIO deleted
- **400**: Invalid request
- **404**: Instance doesn't exist

