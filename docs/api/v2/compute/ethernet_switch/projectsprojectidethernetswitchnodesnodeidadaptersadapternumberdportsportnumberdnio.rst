/v2/compute/projects/{project_id}/ethernet_switch/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/ethernet_switch/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to an Ethernet switch instance

Parameters
**********
- **adapter_number**: Adapter on the switch (always 0)
- **port_number**: Port on the switch
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist


DELETE /v2/compute/projects/**{project_id}**/ethernet_switch/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from an Ethernet switch instance

Parameters
**********
- **adapter_number**: Adapter on the switch (always 0)
- **port_number**: Port on the switch
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

