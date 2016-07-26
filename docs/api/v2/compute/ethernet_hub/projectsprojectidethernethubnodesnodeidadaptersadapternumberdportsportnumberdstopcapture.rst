/v2/compute/projects/{project_id}/ethernet_hub/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/ethernet_hub/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/stop_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on an Ethernet hub instance

Parameters
**********
- **node_id**: Node UUID
- **port_number**: Port on the hub
- **adapter_number**: Adapter on the hub (always 0)
- **project_id**: Project UUID

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Capture stopped

