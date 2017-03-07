/v2/compute/projects/{project_id}/ethernet_hub/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/ethernet_hub/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to an Ethernet hub instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID
- **adapter_number**: Adapter on the hub (always 0)
- **port_number**: Port on the hub

Response status codes
**********************
- **201**: NIO created
- **400**: Invalid request
- **404**: Instance doesn't exist


DELETE /v2/compute/projects/**{project_id}**/ethernet_hub/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from an Ethernet hub instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID
- **adapter_number**: Adapter on the hub (always 0)
- **port_number**: Port on the hub

Response status codes
**********************
- **204**: NIO deleted
- **400**: Invalid request
- **404**: Instance doesn't exist

